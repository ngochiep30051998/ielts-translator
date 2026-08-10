"""Những thứ chỉ hỏng KHI ĐÃ DEPLOY.

Mỗi test ở đây canh một lớp lỗi không bao giờ xuất hiện lúc chạy local: cấu hình đúng cho
Docker nhưng sai cho serverless, hoặc file khai phụ thuộc lệch nhau. Chúng chạy được ở local
vì đều là kiểm cấu hình, không cần chạm Vercel hay Supabase.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.pool import NullPool

from app.config import Settings

GOC = Path(__file__).resolve().parent.parent


def _tham_so_engine(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Bắt đúng bộ tham số mà `get_engine()` truyền cho `create_engine`.

    Bắt ở đây chứ không soi engine đã dựng: `connect_args` bị SQLAlchemy nuốt vào closure
    tạo kết nối, `dialect.create_connect_args()` chỉ trả phần suy từ URL — nên soi engine
    sẽ báo "chưa đặt" kể cả khi đã đặt đúng.

    Vá `app.db.get_settings` chứ không phải `app.config.get_settings`: `app/db.py` đã
    `from app.config import get_settings`, nên tên đó nằm trong namespace của `app.db` ngay
    lúc import — sửa ở `app.config` không tới được nó.
    """
    import app.db as db_mod

    bat: dict[str, Any] = {}

    def _gia(url: str, **kwargs: Any) -> Any:
        bat.update(kwargs)
        bat["url"] = url
        return sqlalchemy_create_engine(url, **kwargs)

    monkeypatch.setattr(db_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(db_mod, "create_engine", _gia)
    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()
    db_mod.get_engine()
    return bat


@pytest.fixture(autouse=True)
def _don_bo_nho_dem_engine() -> Iterator[None]:
    """`get_engine` có `lru_cache`; không dọn thì engine giả rò sang test khác."""
    import app.db as db_mod

    yield
    db_mod.get_engine.cache_clear()
    db_mod.get_session_factory.cache_clear()


# ── psycopg × Supavisor transaction mode ──────────────────────────────────────


def test_serverless_thi_tat_han_prepared_statement(monkeypatch: pytest.MonkeyPatch) -> None:
    """psycopg tạo prepared statement sau 5 lần chạy cùng một câu.

    Supavisor ở transaction mode ghép nhiều client lên chung một backend, nên câu thứ sáu
    có thể rơi vào backend chưa từng thấy statement đó → `prepared statement "_pg3_N" does
    not exist`. Nổ RỜI RẠC DƯỚI TẢI, không bao giờ thấy khi test tay.
    """
    settings = Settings(_env_file=None, VERCEL="1", DATABASE_URL="postgresql://u:p@h:5432/d")  # type: ignore[call-arg]

    assert settings.qua_pooler_transaction is True
    tham_so = _tham_so_engine(settings, monkeypatch)
    assert tham_so["connect_args"] == {"prepare_threshold": None}


def test_cong_6543_thi_tat_prepared_statement_ke_ca_khi_khong_serverless() -> None:
    """Chạy container dài hạn trỏ vào Supavisor transaction mode vẫn dính đúng lỗi đó.

    Supabase dùng 5432 cho session mode và 6543 cho transaction mode; nhận diện theo cổng
    là cách duy nhất biết được mà không bắt người dùng khai thêm biến.
    """
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, DATABASE_URL="postgresql://u:p@aws.pooler.supabase.com:6543/postgres"
    )

    assert settings.is_serverless is False
    assert settings.qua_pooler_transaction is True


def test_ket_noi_truc_tiep_thi_giu_prepared_statement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không có pooler thì prepared statement là thứ tốt — đừng tắt vô cớ."""
    settings = Settings(_env_file=None, DB_HOST="localhost", DB_PORT=5432)  # type: ignore[call-arg]

    assert settings.qua_pooler_transaction is False
    assert "connect_args" not in _tham_so_engine(settings, monkeypatch)


def test_serverless_dung_nullpool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mỗi instance sống vài giây và phục vụ một request. Giữ pool phía client chỉ chiếm chỗ
    trong hạn mức kết nối của Supabase mà không tái dùng được."""
    settings = Settings(_env_file=None, VERCEL="1")  # type: ignore[call-arg]

    assert _tham_so_engine(settings, monkeypatch)["poolclass"] is NullPool


def test_tien_trinh_dai_thi_khong_dung_nullpool(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, DB_HOST="localhost")  # type: ignore[call-arg]

    tham_so = _tham_so_engine(settings, monkeypatch)
    assert "poolclass" not in tham_so
    assert tham_so["pool_pre_ping"] is True


# ── file khai phụ thuộc ───────────────────────────────────────────────────────


def _ten_goi(spec: str) -> str:
    return re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()


def test_requirements_txt_phu_du_phu_thuoc_runtime() -> None:
    """Vercel dựng runtime từ `requirements.txt`, KHÔNG đọc `pyproject.toml`.

    Thêm một gói vào `pyproject.toml` mà quên file này thì local chạy ngon còn deploy lên
    chết bằng `ModuleNotFoundError` — và log chỉ hiện ở dashboard, không hiện ở đâu khác.
    """
    pyproject = tomllib.loads((GOC / "pyproject.toml").read_text("utf-8"))
    runtime = {_ten_goi(d) for d in pyproject["project"]["dependencies"]}
    reqs = {
        _ten_goi(dong)
        for dong in (GOC / "requirements.txt").read_text("utf-8").splitlines()
        if dong.strip() and not dong.lstrip().startswith("#")
    }

    # uvicorn cố ý vắng mặt: Vercel tự cung cấp lớp ASGI, cài thêm chỉ làm phình bundle.
    thieu = runtime - reqs - {"uvicorn"}
    assert thieu == set(), (
        f"requirements.txt thiếu {sorted(thieu)} so với pyproject.toml. "
        "Deploy sẽ chết bằng ModuleNotFoundError."
    )

    thua = reqs - runtime
    assert thua == set(), f"requirements.txt có {sorted(thua)} mà pyproject.toml không khai."


# ── đóng gói cho Vercel ───────────────────────────────────────────────────────


def test_vercel_json_dong_goi_prompts_va_migrations() -> None:
    """`includeFiles` là BẮT BUỘC. Không có nó thì `prompts/*.md` không lên bundle, chạy
    local ngon mà deploy lên là MỌI lượt dịch chết."""
    import json

    cfg = json.loads((GOC / "vercel.json").read_text("utf-8"))
    include = cfg["functions"]["api/index.py"]["includeFiles"]

    assert "prompts" in include
    assert "migrations" in include


#: Trần `maxDuration` của gói Vercel Hobby. Đặt cao hơn thì deploy bị từ chối.
MAX_DURATION_HOBBY = 60


def timeout_sinh_quiz_toi_da(max_duration: int) -> int:
    """Giá trị `GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS` lớn nhất còn an toàn trên serverless.

    Một lượt sinh quiz xấu nhất tốn `MAX_ATTEMPTS × timeout + backoff`. Vượt `maxDuration`
    thì Vercel giết function GIỮA lượt gọi Gemini: người dùng thấy request treo rồi đứt,
    quota Gemini vẫn bị trừ, và log chỉ có một dòng timeout không nói được nguyên nhân.
    """
    from app.common.gemini import MAX_ATTEMPTS

    return (max_duration - 1) // MAX_ATTEMPTS


def test_max_duration_khai_tuong_minh_va_du_cho_mot_timeout_dung_duoc() -> None:
    """Mặc định 30s của `.env` (hợp cho Docker) KHÔNG vừa trên Hobby: 2×30+1 = 61 > 60.

    Nên đây không phải là chuyện nâng `maxDuration` — 60 đã là trần Hobby — mà là chuyện
    trên Vercel phải hạ timeout xuống. Test canh rằng `maxDuration` đủ lớn để còn tồn tại
    một giá trị timeout dùng được; con số cụ thể nằm trong `DEPLOY.md`.
    """
    import json

    cfg = json.loads((GOC / "vercel.json").read_text("utf-8"))
    max_duration = cfg["functions"]["api/index.py"].get("maxDuration")

    assert max_duration is not None, "Phải khai maxDuration, đừng dựa vào mặc định của gói"
    assert max_duration <= MAX_DURATION_HOBBY, (
        f"maxDuration={max_duration}s vượt trần Hobby {MAX_DURATION_HOBBY}s — deploy sẽ bị từ chối."
    )

    cho_phep = timeout_sinh_quiz_toi_da(max_duration)
    mac_dinh = Settings(_env_file=None).gemini_quiz_generate_timeout_seconds  # type: ignore[call-arg]
    assert cho_phep >= 20, f"maxDuration={max_duration}s chỉ cho timeout {cho_phep}s — quá ngắn."
    assert mac_dinh > cho_phep, (
        "Mặc định giờ đã vừa maxDuration — cập nhật DEPLOY.md, phần dặn hạ "
        "GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS trên Vercel không còn cần nữa."
    )


def test_moi_duong_dan_deu_rewrite_ve_mot_function() -> None:
    """Gói Hobby giới hạn 12 function mỗi lần deploy; API có 16 endpoint. Chia theo file là
    chạm trần ngay."""
    import json

    cfg = json.loads((GOC / "vercel.json").read_text("utf-8"))

    assert cfg["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]


def test_entry_point_vercel_import_duoc_app() -> None:
    """`api/index.py` phải import được KHI CHẠY TỪ THƯ MỤC GỐC PROJECT — Vercel đặt working
    directory ở đó chứ không ở `api/`."""
    nguon = (GOC / "api" / "index.py").read_text("utf-8")

    assert "sys.path.insert" in nguon, (
        "Vercel không tự thêm thư mục gốc vào sys.path; thiếu bước này thì cold start chết "
        "bằng ModuleNotFoundError và log chỉ hiện ở dashboard."
    )
    assert "from app.main import app" in nguon
