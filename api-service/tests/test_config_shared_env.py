"""`config.py`, `.env.example` và `docker-compose.yml` phải nói cùng một bộ cấu hình.

Trước đây file này đối chiếu `config.py` với `application.yml` của backend Spring. Bản Java
đã bị xoá, nhưng cái bẫy thì không mất đi — nó chỉ chuyển chỗ:

1. **Biến khai trong `.env.example` mà `config.py` không đọc** = người dùng đặt giá trị rồi
   tưởng nó có tác dụng. Không có gì đỏ, không có cảnh báo nào.
2. **Default trong `docker-compose.yml` lệch default trong `config.py`** = cùng một `.env`
   thiếu biến đó, chạy Docker ra một hành vi còn chạy `uv run ielts-api` ra hành vi khác.
   Đây là loại lỗi chỉ lộ ra khi so hai môi trường, tức là gần như không bao giờ.
3. **Biến `config.py` khai thêm mà bắt buộc** = `.env` đang chạy tốt bỗng làm app chết lúc
   khởi động.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator

import pytest
from pydantic import AliasChoices
from pydantic.fields import FieldInfo

from app.config import REPO_ROOT, Settings

ENV_EXAMPLE = REPO_ROOT / ".env.example"
COMPOSE_YML = REPO_ROOT / "docker-compose.yml"

#: `KEY=` ở đầu dòng, kể cả khi bị comment (`# KEY=` là mục "tuỳ chọn" trong .env.example).
_KHAI_BAO = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", re.MULTILINE)

#: `${BIEN:-mặc-định}` trong compose. Chỉ bắt dạng CÓ mặc định — `${BIEN}` trần nghĩa là
#: "phải đến từ .env", không có gì để đối chiếu.
_COMPOSE_DEFAULT = re.compile(r"\$\{([A-Z][A-Z0-9_]*):-([^}]*)\}")

#: Chỉ Docker Compose dùng, tiến trình app không bao giờ đọc: cổng publish ra host. Trong
#: mạng compose api-service luôn nghe 8080, nên đây không phải cấu hình của app.
CHI_DANH_CHO_COMPOSE = {"APP_PORT"}

#: Biến `config.py` khai thêm ngoài `.env.example`. Danh sách chốt cứng để thêm biến mới là
#: phải sửa cả test này — và lúc đó nhớ luôn bảng "Biến môi trường" trong README (ràng buộc #6).
NGOAI_ENV_EXAMPLE = {
    # Vercel/Supabase phát một chuỗi kết nối duy nhất thay vì năm mảnh rời.
    "DATABASE_URL",
    # Compose set 0.0.0.0 trong container; ngoài container mặc định 127.0.0.1.
    "SERVER_ADDRESS",
    # Chỉ đổi khi test.
    "AUTH_GOOGLE_TOKEN_URL",
    # Do CHÍNH nền tảng đặt (`VERCEL=1` trong mọi function), không phải thứ người dùng khai.
    "VERCEL",
    # Tên thứ hai của `TZ`, chỉ dùng trên Vercel: dashboard ở đó từ chối biến tên `TZ` (tên bị
    # giữ chỗ) trong khi Lambda bên dưới tự đặt `TZ=:UTC`. Không đưa vào `.env.example` vì
    # đường Docker/local vẫn khai `TZ` như cũ — hai tên trong file mẫu chỉ gây phân vân.
    "APP_TZ",
}


def _bien_env_example() -> set[str]:
    return set(_KHAI_BAO.findall(ENV_EXAMPLE.read_text("utf-8")))


def _bi_danh(f: FieldInfo) -> list[str]:
    """Mọi tên biến môi trường mà một field chấp nhận.

    Không chỉ `f.alias`: một field có thể nhận NHIỀU tên qua `AliasChoices` (`tz` nhận cả
    `APP_TZ` lẫn `TZ`). Chỉ đọc `f.alias` thì các tên còn lại vô hình với mọi test dưới đây —
    tức là chốt chặn "config.py và .env.example nói cùng một bộ biến" thủng đúng ở chỗ vừa
    thêm biến mới.
    """
    va = f.validation_alias
    if isinstance(va, AliasChoices):
        return [chon for chon in va.choices if isinstance(chon, str)]
    if isinstance(va, str):
        return [va]
    return [f.alias] if f.alias else []


def _alias_settings() -> dict[str, str]:
    return {
        bi_danh.upper(): ten
        for ten, f in Settings.model_fields.items()
        for bi_danh in _bi_danh(f)
    }


@pytest.fixture
def env_sach(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Xoá mọi biến môi trường mà `Settings` đọc.

    `conftest.py` đặt sẵn một loạt biến để trỏ test vào Postgres tạm, và biến môi trường
    thắng cả `_env_file=None`. Không dọn thì test "giá trị mặc định" thực chất đang đo cấu
    hình của chính bộ test — xanh mà không chứng minh gì.
    """
    for bien in _alias_settings():
        monkeypatch.delenv(bien, raising=False)
    # `.env` ở thư mục gốc cũng phải bị bỏ qua; các test dưới truyền `_env_file=None`.
    assert not any(b in os.environ for b in _alias_settings())
    yield


def test_moi_bien_trong_env_example_deu_duoc_config_doc() -> None:
    """Thiếu một biến ở đây = app bỏ qua cấu hình người dùng đã đặt, im lặng."""
    thieu = sorted(_bien_env_example() - set(_alias_settings()) - CHI_DANH_CHO_COMPOSE)

    assert thieu == [], (
        f".env.example khai {thieu} mà config.py không đọc. Người dùng sẽ đặt biến đó và "
        "tưởng nó có tác dụng."
    )


def test_default_trong_compose_khop_default_trong_config(env_sach: None) -> None:
    """Lệch một giá trị = chạy Docker và chạy `uv run ielts-api` cư xử khác nhau.

    Người dùng không có cách nào biết, vì cả hai đều khởi động bình thường.
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_settings()

    lech: list[str] = []
    for bien, cua_compose in sorted(set(_COMPOSE_DEFAULT.findall(COMPOSE_YML.read_text("utf-8")))):
        if bien not in alias:
            continue
        cua_config = str(getattr(settings, alias[bien]))
        if cua_config != cua_compose:
            lech.append(f"{bien}: compose={cua_compose!r} config.py={cua_config!r}")

    assert lech == [], "\n".join(lech)


def test_bien_ngoai_env_example_deu_khong_bat_buoc(env_sach: None) -> None:
    """`config.py` được phép khai thêm biến, nhưng chúng PHẢI có mặc định.

    Nếu không thì `.env` đang chạy tốt sẽ làm app chết lúc khởi động chỉ vì nâng cấp code.
    """
    them = set(_alias_settings()) - _bien_env_example()
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_settings()

    for bien in sorted(them):
        # Dựng được Settings rỗng nghĩa là biến này không bắt buộc.
        assert hasattr(settings, alias[bien])

    assert them == NGOAI_ENV_EXAMPLE, (
        f"Biến ngoài dự kiến: {sorted(them ^ NGOAI_ENV_EXAMPLE)}. Thêm biến vào config.py thì "
        "phải thêm cả vào bảng 'Biến môi trường' trong README.md (ràng buộc #6)."
    )


def test_database_url_rong_thi_ghep_tu_cac_manh_db(env_sach: None) -> None:
    """Đường chạy local/Docker: connection string ghép phẳng từ `DB_HOST`/`DB_PORT`/`DB_NAME`."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DB_HOST="localhost",
        DB_PORT=6666,
        DB_NAME="ielts",
        DB_USER="ielts",
        DB_PASSWORD="matkhau",
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://ielts:matkhau@localhost:6666/ielts"


def test_database_url_dat_thi_thang_cac_manh_db(env_sach: None) -> None:
    """Chỉ dùng khi deploy Supabase/Vercel — nơi chỉ có một chuỗi kết nối."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DB_HOST="bo-qua",
        DATABASE_URL="postgres://u:p@db.supabase.co:6543/postgres",
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@db.supabase.co:6543/postgres"
