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
_DECLARATION = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", re.MULTILINE)

#: `${BIEN:-mặc-định}` trong compose. Chỉ bắt dạng CÓ mặc định — `${BIEN}` trần nghĩa là
#: "phải đến từ .env", không có gì để đối chiếu.
_COMPOSE_DEFAULT = re.compile(r"\$\{([A-Z][A-Z0-9_]*):-([^}]*)\}")

#: Chỉ Docker Compose dùng, tiến trình app không bao giờ đọc: cổng publish ra host. Trong
#: mạng compose api-service luôn nghe 8080, nên đây không phải cấu hình của app.
COMPOSE_ONLY_VARS = {"APP_PORT"}

#: Biến `config.py` khai thêm ngoài `.env.example`. Danh sách chốt cứng để thêm biến mới là
#: phải sửa cả test này — và lúc đó nhớ luôn bảng "Biến môi trường" trong README (ràng buộc #6).
NOT_IN_ENV_EXAMPLE = {
    # Vercel/Supabase phát một chuỗi kết nối duy nhất thay vì năm mảnh rời.
    "DATABASE_URL",
    # Compose set 0.0.0.0 trong container; ngoài container mặc định 127.0.0.1.
    "SERVER_ADDRESS",
    # Chỉ đổi khi test.
    "AUTH_GOOGLE_TOKEN_URL",
    # Cùng lý do: authorization endpoint của Google là hằng số của nền tảng, không phải thứ
    # người dùng khai. Chỉ đổi khi test.
    "AUTH_GOOGLE_AUTH_URL",
    # Đường dẫn của một artifact build, không phải cấu hình người dùng chỉnh. Cả đường Docker
    # lẫn đường Vercel đều đặt SPA vào `api-service/static`; biến này tồn tại để test trỏ
    # được vào thư mục tạm.
    "WEB_STATIC_DIR",
    # Do CHÍNH nền tảng đặt (`VERCEL=1` trong mọi function), không phải thứ người dùng khai.
    "VERCEL",
    # Tên thứ hai của `TZ`, chỉ dùng trên Vercel: dashboard ở đó từ chối biến tên `TZ` (tên bị
    # giữ chỗ) trong khi Lambda bên dưới tự đặt `TZ=:UTC`. Không đưa vào `.env.example` vì
    # đường Docker/local vẫn khai `TZ` như cũ — hai tên trong file mẫu chỉ gây phân vân.
    "APP_TZ",
}


def _env_example_vars() -> set[str]:
    return set(_DECLARATION.findall(ENV_EXAMPLE.read_text("utf-8")))


def _aliases(f: FieldInfo) -> list[str]:
    """Mọi tên biến môi trường mà một field chấp nhận.

    Không chỉ `f.alias`: một field có thể nhận NHIỀU tên qua `AliasChoices` (`tz` nhận cả
    `APP_TZ` lẫn `TZ`). Chỉ đọc `f.alias` thì các tên còn lại vô hình với mọi test dưới đây —
    tức là chốt chặn "config.py và .env.example nói cùng một bộ biến" thủng đúng ở chỗ vừa
    thêm biến mới.
    """
    alias_spec = f.validation_alias
    if isinstance(alias_spec, AliasChoices):
        return [choice for choice in alias_spec.choices if isinstance(choice, str)]
    if isinstance(alias_spec, str):
        return [alias_spec]
    return [f.alias] if f.alias else []


def _alias_settings() -> dict[str, str]:
    return {
        alias_name.upper(): field_name
        for field_name, f in Settings.model_fields.items()
        for alias_name in _aliases(f)
    }


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Xoá mọi biến môi trường mà `Settings` đọc.

    `conftest.py` đặt sẵn một loạt biến để trỏ test vào Postgres tạm, và biến môi trường
    thắng cả `_env_file=None`. Không dọn thì test "giá trị mặc định" thực chất đang đo cấu
    hình của chính bộ test — xanh mà không chứng minh gì.
    """
    for env_var in _alias_settings():
        monkeypatch.delenv(env_var, raising=False)
    # `.env` ở thư mục gốc cũng phải bị bỏ qua; các test dưới truyền `_env_file=None`.
    assert not any(b in os.environ for b in _alias_settings())
    yield


def test_every_var_in_env_example_is_read_by_config() -> None:
    """Thiếu một biến ở đây = app bỏ qua cấu hình người dùng đã đặt, im lặng."""
    missing = sorted(_env_example_vars() - set(_alias_settings()) - COMPOSE_ONLY_VARS)

    assert missing == [], (
        f".env.example khai {missing} mà config.py không đọc. Người dùng sẽ đặt biến đó và "
        "tưởng nó có tác dụng."
    )


def test_defaults_in_compose_match_defaults_in_config(clean_env: None) -> None:
    """Lệch một giá trị = chạy Docker và chạy `uv run ielts-api` cư xử khác nhau.

    Người dùng không có cách nào biết, vì cả hai đều khởi động bình thường.
    """
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_settings()

    mismatches: list[str] = []
    for env_var, compose_value in sorted(
        set(_COMPOSE_DEFAULT.findall(COMPOSE_YML.read_text("utf-8")))
    ):
        if env_var not in alias:
            continue
        config_value = str(getattr(settings, alias[env_var]))
        if config_value != compose_value:
            mismatches.append(f"{env_var}: compose={compose_value!r} config.py={config_value!r}")

    assert mismatches == [], "\n".join(mismatches)


def test_vars_outside_env_example_are_all_optional(clean_env: None) -> None:
    """`config.py` được phép khai thêm biến, nhưng chúng PHẢI có mặc định.

    Nếu không thì `.env` đang chạy tốt sẽ làm app chết lúc khởi động chỉ vì nâng cấp code.
    """
    extra_vars = set(_alias_settings()) - _env_example_vars()
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    alias = _alias_settings()

    for env_var in sorted(extra_vars):
        # Dựng được Settings rỗng nghĩa là biến này không bắt buộc.
        assert hasattr(settings, alias[env_var])

    assert extra_vars == NOT_IN_ENV_EXAMPLE, (
        f"Biến ngoài dự kiến: {sorted(extra_vars ^ NOT_IN_ENV_EXAMPLE)}. "
        "Thêm biến vào config.py thì "
        "phải thêm cả vào bảng 'Biến môi trường' trong README.md (ràng buộc #6)."
    )


def test_database_url_empty_is_built_from_db_parts(clean_env: None) -> None:
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


def test_database_url_set_wins_over_db_parts(clean_env: None) -> None:
    """Chỉ dùng khi deploy Supabase/Vercel — nơi chỉ có một chuỗi kết nối."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DB_HOST="bo-qua",
        DATABASE_URL="postgres://u:p@db.supabase.co:6543/postgres",
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@db.supabase.co:6543/postgres"
