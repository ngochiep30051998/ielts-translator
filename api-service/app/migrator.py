"""Bộ chạy migration thay Flyway.

Vì sao tự viết thay vì thêm alembic/yoyo: các file `V*.sql` được chép NGUYÊN VĂN từ
`backend/src/main/resources/db/migration/`. Giữ chúng là SQL thuần có nghĩa là hai backend
dựng ra đúng một schema, và ràng buộc #8 (migration append-only) vẫn kiểm chứng được bằng
mắt qua `diff`. Thêm một framework migration sẽ buộc phải viết lại DDL sang DSL của nó —
tức là mở ra một chỗ để hai bên lệch nhau mà không ai thấy.

Tương thích với Flyway: nếu database đã có bảng `flyway_schema_history` (trường hợp chạy
song song với backend Spring trên cùng một Postgres), mọi version đã được Flyway áp dụng
được coi là đã chạy. Không có bước này thì khởi động api-service trên DB thật sẽ chạy lại
V1 và nổ ngay ở `CREATE TABLE lookup_cache`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_FILENAME = re.compile(r"^V(\d+)__(.+)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Đọc `V<số>__<mô tả>.sql`, sắp theo số version tăng dần."""
    found: list[Migration] = []
    for path in sorted(directory.glob("V*.sql")):
        matched = _FILENAME.match(path.name)
        if matched is None:
            raise ValueError(
                f"Tên file migration sai định dạng: {path.name}. "
                "Phải là V<số>__<mô tả>.sql, ví dụ V8__them_cot.sql"
            )
        found.append(Migration(int(matched.group(1)), matched.group(2), path))

    versions = [m.version for m in found]
    trung = {v for v in versions if versions.count(v) > 1}
    if trung:
        raise ValueError(f"Trùng version migration: {sorted(trung)}")
    return sorted(found, key=lambda m: m.version)


def render_all(bootstrap_email: str, directory: Path = MIGRATIONS_DIR) -> str:
    """Gộp mọi migration thành MỘT đoạn SQL đã thay placeholder, để áp bằng tay.

    Dùng khi database không do api-service quản lý — Supabase là ca chính: ở đó schema
    được áp một lần từ ngoài, còn function serverless thì KHÔNG chạy migration lúc cold
    start (nhiều instance cùng `ALTER TABLE` là công thức để khoá lẫn nhau).

    In ra stdout chứ không ghi file: email bootstrap là dữ liệu cá nhân, và một file SQL đã
    thay sẵn email nằm trong repo là thứ sẽ bị commit nhầm.
    """
    if not bootstrap_email or not bootstrap_email.strip():
        raise ValueError(
            "AUTH_BOOTSTRAP_EMAIL rỗng. V6 dùng nó để gán chủ sở hữu cho toàn bộ sổ từ cũ."
        )
    email = bootstrap_email.strip().lower()
    phan: list[str] = [
        "-- Sinh bởi `python -m app.migrator`. KHÔNG sửa tay ở đây —",
        "-- nguồn là api-service/migrations/V*.sql (append-only, ràng buộc #8).",
        "",
    ]
    for mig in discover(directory):
        phan.append(f"-- ═══ V{mig.version}__{mig.description}.sql ═══")
        phan.append(mig.sql.replace("${bootstrap_email}", email))
        phan.append("")
    # Ghi lại lịch sử để api-service biết đừng chạy lại — vai trò của flyway_schema_history.
    phan.append(_SCHEMA_HISTORY.strip() + ";")
    phan.append("")
    gia_tri = ", ".join(
        f"({m.version}, '{m.description}', '{m.checksum()}')" for m in discover(directory)
    )
    phan.append(
        "INSERT INTO api_schema_history (version, description, checksum) VALUES\n"
        f"{gia_tri}\nON CONFLICT (version) DO NOTHING;"
    )
    return "\n".join(phan)


def _cli() -> int:
    import argparse

    from app.config import get_settings

    parser = argparse.ArgumentParser(
        prog="python -m app.migrator",
        description="In toàn bộ SQL migration đã thay placeholder, để áp bằng tay lên Supabase",
    )
    parser.add_argument(
        "--bootstrap-email",
        default=None,
        help="Mặc định: AUTH_BOOTSTRAP_EMAIL trong .env",
    )
    args = parser.parse_args()
    email = args.bootstrap_email or get_settings().auth_bootstrap_email
    try:
        print(render_all(email))
    except ValueError as ex:
        print(f"Lỗi: {ex}", file=__import__("sys").stderr)
        return 1
    return 0


_SCHEMA_HISTORY = """
CREATE TABLE IF NOT EXISTS api_schema_history (
    version     INTEGER      PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    checksum    VARCHAR(64)  NOT NULL,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
)
"""


def _versions_da_chay(engine: Engine) -> set[int]:
    with engine.connect() as conn:
        applied = {
            row[0] for row in conn.execute(text("SELECT version FROM api_schema_history"))
        }

        # Flyway ghi version dạng chuỗi ('1', '2'...). `success` phân biệt lần chạy hỏng.
        flyway_ton_tai = conn.execute(
            text("SELECT to_regclass('public.flyway_schema_history') IS NOT NULL")
        ).scalar()
        if flyway_ton_tai:
            applied |= {
                int(row[0])
                for row in conn.execute(
                    text(
                        "SELECT version FROM flyway_schema_history "
                        "WHERE success AND version ~ '^[0-9]+$'"
                    )
                )
            }
    return applied


def migrate(engine: Engine, *, bootstrap_email: str, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Áp dụng mọi migration chưa chạy. Trả về danh sách version vừa áp dụng.

    `bootstrap_email` thay cho placeholder `${bootstrap_email}` của Flyway trong V6. KHÔNG
    có giá trị mặc định — chạy V6 với một email đoán bừa sẽ gán toàn bộ sổ từ cũ cho một
    tài khoản không ai đăng nhập được, và migration thì không chạy lại.
    """
    if not bootstrap_email or not bootstrap_email.strip():
        raise ValueError(
            "AUTH_BOOTSTRAP_EMAIL rỗng. V6 dùng nó để gán chủ sở hữu cho toàn bộ sổ từ cũ; "
            "chạy với giá trị đoán bừa là mất dữ liệu không lấy lại được."
        )

    with engine.begin() as conn:
        conn.execute(text(_SCHEMA_HISTORY))

    da_chay = _versions_da_chay(engine)
    vua_chay: list[int] = []

    for mig in discover(directory):
        if mig.version in da_chay:
            continue
        sql = mig.sql.replace("${bootstrap_email}", bootstrap_email.strip().lower())
        # Một transaction cho mỗi migration: hỏng ở giữa thì file đó không để lại gì,
        # và không bị ghi vào lịch sử nên lần sau chạy lại được.
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(
                text(
                    "INSERT INTO api_schema_history (version, description, checksum) "
                    "VALUES (:v, :d, :c)"
                ),
                {"v": mig.version, "d": mig.description, "c": mig.checksum()},
            )
        vua_chay.append(mig.version)

    return vua_chay


if __name__ == "__main__":
    import sys

    sys.exit(_cli())
