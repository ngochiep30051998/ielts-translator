"""FastAPI tự phục vụ web app (SPA).

Đây là cơ chế DUY NHẤT chạy giống hệt nhau ở cả đường Vercel lẫn đường Docker — xem
docstring của `app/web_static.py` để biết vì sao không dùng `rewrites` của Vercel.

Rủi ro lớn nhất của việc này là catch-all nuốt mất `/api/*`: lúc đó mọi lỗi gõ sai URL của
API trả về một trang HTML với status 200, client cố parse JSON rồi báo "backend trả phản hồi
không đọc được" — một thông điệp trỏ đi hoàn toàn sai hướng.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

HTML = "<!doctype html><html><body><div id='root'></div></body></html>"


@pytest.fixture
def spa_client(tmp_path: Path, db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """TestClient của một app CÓ SPA đã build, đặt trong thư mục tạm."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import get_db
    from app.main import create_app

    (tmp_path / "index.html").write_text(HTML, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "manifest.webmanifest").write_text('{"name":"x"}', encoding="utf-8")
    (tmp_path / "sw.js").write_text("self.addEventListener('install', () => {});", encoding="utf-8")

    monkeypatch.setenv("WEB_STATIC_DIR", str(tmp_path))
    # `get_settings` có lru_cache nên phải dọn TRƯỚC khi dựng app, và dọn lại sau — bỏ bước
    # sau thì mọi test chạy tiếp đọc nhầm thư mục tạm đã bị xoá.
    get_settings.cache_clear()
    try:
        application = create_app()

        def _get_db_test() -> Iterator[Session]:
            yield db

        application.dependency_overrides[get_db] = _get_db_test
        with TestClient(application, base_url="https://testserver") as tc:
            yield tc
    finally:
        get_settings.cache_clear()


# ── khi CHƯA build SPA ───────────────────────────────────────────────────────


@pytest.fixture
def client_without_spa(
    tmp_path: Path, db: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """App CHƯA build web — trỏ tường minh vào một thư mục rỗng.

    KHÔNG dùng fixture `client` mặc định cho việc này. Mặc định là `api-service/static`, và
    thư mục đó CÓ hay KHÔNG tuỳ máy: ai vừa chạy `scripts/build-web-and-migrate.sh` là có.
    Test sẽ xanh trên CI, đỏ trên máy vừa build — hoặc tệ hơn, ngược lại.
    """
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import get_db
    from app.main import create_app

    empty_dir = tmp_path / "chua-build"
    empty_dir.mkdir()
    monkeypatch.setenv("WEB_STATIC_DIR", str(empty_dir))
    get_settings.cache_clear()
    try:
        application = create_app()

        def _get_db_test() -> Iterator[Session]:
            yield db

        application.dependency_overrides[get_db] = _get_db_test
        with TestClient(application, base_url="https://testserver") as tc:
            yield tc
    finally:
        get_settings.cache_clear()


def test_app_still_starts_without_spa(client_without_spa: Any) -> None:
    """Trạng thái của `uv run ielts-api` khi chạy backend-only, và của mọi lần chạy pytest
    trên máy chưa build web."""
    assert client_without_spa.get("/api/health").status_code == 200


def test_without_spa_unknown_path_still_returns_404_with_correct_shape(
    client_without_spa: Any,
) -> None:
    resp = client_without_spa.get("/mot-duong-dan-la")

    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


# ── khi ĐÃ build SPA ─────────────────────────────────────────────────────────


def test_home_page_returns_index_html(spa_client: Any) -> None:
    resp = spa_client.get("/")

    assert resp.status_code == 200
    assert "<div id='root'></div>" in resp.text


def test_unknown_path_returns_index_html_so_spa_routes_itself(spa_client: Any) -> None:
    resp = spa_client.get("/share")

    assert resp.status_code == 200
    assert "<div id='root'></div>" in resp.text


def test_API_is_not_swallowed_by_catch_all(spa_client: Any) -> None:
    """Chốt chặn quan trọng nhất của cả file này."""
    resp = spa_client.get("/api/khong-co-endpoint-nay")

    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_real_api_still_works_normally(spa_client: Any) -> None:
    resp = spa_client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "UP"


def test_api_requiring_login_still_returns_401_not_html(spa_client: Any) -> None:
    # Nếu catch-all nuốt nhầm, endpoint này trả HTML 200 và client tưởng đã đăng nhập.
    resp = spa_client.get("/api/vocab")

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_hashed_asset_is_served(spa_client: Any) -> None:
    resp = spa_client.get("/assets/index-abc123.js")

    assert resp.status_code == 200
    assert "console.log(1)" in resp.text


def test_real_file_outside_assets_is_also_served(spa_client: Any) -> None:
    # manifest.webmanifest và sw.js nằm ở gốc build, không có hash trong tên.
    resp = spa_client.get("/manifest.webmanifest")

    assert resp.status_code == 200
    assert resp.json() == {"name": "x"}


def test_HEAD_does_not_return_405(spa_client: Any) -> None:
    """`APIRoute` của FastAPI KHÔNG tự thêm HEAD khi khai `@app.get` — khác `Route` của
    Starlette. Thiếu nó thì health check, monitor và trình thu thập liên kết đều nhận 405 ở
    mọi đường dẫn của web app, kể cả `/sw.js`."""
    for url_path in ("/", "/sw.js", "/manifest.webmanifest", "/mot-duong-dan-la"):
        resp = spa_client.head(url_path)
        assert resp.status_code == 200, f"{url_path} -> {resp.status_code}"


def test_HEAD_on_wrong_api_path_still_returns_404(spa_client: Any) -> None:
    assert spa_client.head("/api/khong-co").status_code == 404


def test_index_html_is_not_cached(spa_client: Any) -> None:
    """Cache index.html là cách chắc chắn nhất để người dùng chạy mã cũ trỏ vào asset đã bị
    xoá sau một lần deploy — trang trắng, không lỗi nào giải thích."""
    resp = spa_client.get("/")

    assert "no-cache" in resp.headers.get("cache-control", "")


def test_service_worker_is_not_cached(spa_client: Any) -> None:
    """`sw.js` là thứ trình duyệt tải về để BIẾT có bản mới hay không.

    Nó không có hash trong tên, nên nếu trình duyệt phục vụ lại bản đã cache thì lượt kiểm
    tra bản mới so bản cũ với chính bản cũ — luôn thấy giống nhau, và banner "đã có bản mới"
    không bao giờ hiện. Không có header này, FastAPI chỉ gửi ETag/Last-Modified và trình
    duyệt được tự quyết cache bao lâu.
    """
    resp = spa_client.get("/sw.js")

    assert resp.status_code == 200
    assert "self.addEventListener" in resp.text
    assert "no-cache" in resp.headers.get("cache-control", "")


def test_cannot_escape_outside_build_directory(spa_client: Any) -> None:
    """Path traversal: `..` phải không lấy được file ngoài thư mục build."""
    resp = spa_client.get("/../../../etc/passwd")

    # Dù trả index.html hay 404 đều chấp nhận được; điều KHÔNG chấp nhận được là lộ file.
    assert "root:" not in resp.text
