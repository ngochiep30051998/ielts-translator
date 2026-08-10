"""api-service dùng CHUNG `.env` ở thư mục gốc với backend Spring.

Đây không phải chuyện tiện tay: hai file `.env` song song là hai bản sao của cùng một bộ
bí mật, và chúng sẽ lệch nhau — thường là lúc đổi `EXTENSION_ID` hoặc xoay khoá Gemini, và
triệu chứng là một backend chạy ngon còn backend kia chết vì CORS.

File test này canh ba thứ:

1. Mọi biến `application.yml` đọc đều được `config.py` khai — thiếu một cái là nó lặng lẽ
   rơi về mặc định, không có gì đỏ.
2. Giá trị mặc định của hai bên KHỚP — lệch nghĩa là khi `.env` thiếu biến, hai backend cư
   xử khác nhau.
3. Biến api-service khai thêm đều KHÔNG bắt buộc — `.env` đang chạy tốt cho Spring phải
   chạy được luôn cho api-service, không phải thêm dòng nào.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings

APPLICATION_YML = (
    Path(__file__).resolve().parent.parent.parent
    / "backend/src/main/resources/application.yml"
)

_PLACEHOLDER = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::([^}]*))?\}")


def _bien_spring() -> dict[str, str | None]:
    return {
        m.group(1): m.group(2) for m in _PLACEHOLDER.finditer(APPLICATION_YML.read_text("utf-8"))
    }


def _alias_fastapi() -> dict[str, str]:
    return {f.alias.upper(): ten for ten, f in Settings.model_fields.items() if f.alias}


@pytest.fixture
def env_sach(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Xoá mọi biến môi trường mà `Settings` đọc.

    `conftest.py` đặt sẵn một loạt biến để trỏ test vào Postgres tạm, và biến môi trường
    thắng cả `_env_file=None`. Không dọn thì test "giá trị mặc định" thực chất đang đo cấu
    hình của chính bộ test — xanh mà không chứng minh gì.
    """
    for bien in _alias_fastapi():
        monkeypatch.delenv(bien, raising=False)
    # `.env` ở thư mục gốc cũng phải bị bỏ qua; các test dưới truyền `_env_file=None`.
    assert not any(b in os.environ for b in _alias_fastapi())
    yield


def test_moi_bien_spring_doc_deu_duoc_fastapi_khai() -> None:
    """Thiếu một biến ở đây = api-service bỏ qua cấu hình người dùng đã đặt, im lặng."""
    thieu = sorted(set(_bien_spring()) - set(_alias_fastapi()))

    assert thieu == [], (
        f"application.yml đọc {thieu} mà config.py không khai. Dùng chung .env nghĩa là "
        "người dùng đặt biến đó và tưởng nó có tác dụng cho cả hai backend."
    )


def test_gia_tri_mac_dinh_khop_ban_java(env_sach: None) -> None:
    """Mặc định trong file CHÍNH LÀ cấu hình chạy local (ràng buộc #6).

    Lệch một giá trị nghĩa là khi `.env` thiếu biến đó, hai backend chạy bằng hai cấu hình
    khác nhau — và người dùng không có cách nào biết.
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_fastapi()

    lech: list[str] = []
    for bien, mac_dinh in sorted(_bien_spring().items()):
        if bien not in alias:
            continue
        cua_python = str(getattr(settings, alias[bien]))
        cua_java = "" if mac_dinh is None else mac_dinh
        if cua_python != cua_java:
            lech.append(f"{bien}: spring={cua_java!r} fastapi={cua_python!r}")

    assert lech == [], "\n".join(lech)


def test_bien_them_deu_khong_bat_buoc(env_sach: None) -> None:
    """`config.py` được phép khai thêm biến Spring không có, nhưng chúng PHẢI có mặc định.

    Nếu không thì `.env` đang chạy tốt cho backend Spring sẽ làm api-service chết lúc khởi
    động — tức là dùng chung `.env` không còn đúng nữa.
    """
    them = sorted(set(_alias_fastapi()) - set(_bien_spring()))
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_fastapi()

    for bien in them:
        # Dựng được Settings rỗng nghĩa là biến này không bắt buộc.
        assert hasattr(settings, alias[bien])
    # VERCEL do CHÍNH nền tảng đặt (`VERCEL=1` trong mọi function), không phải thứ người
    # dùng khai trong `.env` — nhưng vẫn phải có mặc định, vì ở local nó luôn vắng.
    assert them == ["DATABASE_URL", "TZ", "VERCEL"], (
        f"Có biến mới ngoài dự kiến: {them}. Thêm biến vào api-service thì phải thêm cả vào "
        "bảng 'Biến môi trường' trong README.md (ràng buộc #6)."
    )


def test_database_url_rong_thi_ghep_tu_cac_manh_db(env_sach: None) -> None:
    """Đường dùng chung `.env`: backend Spring ghép JDBC URL từ `DB_HOST`/`DB_PORT`/`DB_NAME`,
    và api-service phải ra đúng cùng một database."""
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
