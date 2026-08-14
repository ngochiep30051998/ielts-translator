"""Nền test — bản thay `AbstractPostgresIT`.

Bên Java, mọi test tích hợp kế thừa `AbstractPostgresIT` để dùng chung MỘT container
Postgres. Ở đây vai trò đó do `pgserver` đảm nhiệm: nó bung sẵn nhị phân PostgreSQL 16 và
chạy trên unix socket, nên **không cần Docker** và khởi động nhanh hơn Testcontainers một
bậc. Cùng major version với production (Postgres 16) là điều kiện bắt buộc — hành vi
`TEXT[]`, `JSONB` và `ON CONFLICT` phải giống hệt, test trên SQLite là tự lừa mình.

Giữ nguyên quy ước đặt tên của bản Java để hai bộ test đọc đối chiếu được:
`OWNER_EMAIL`, `IT_TOKEN`, `second@test.local`.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

#: Email của tài khoản mà migration V6 tạo ra và gán toàn bộ dữ liệu cũ cho.
#: Test một-người-dùng dùng chính tài khoản này.
OWNER_EMAIL = "owner@test.local"
SECOND_EMAIL = "second@test.local"

#: Token cố định cho mọi test một-người-dùng. Cố định chứ không sinh ngẫu nhiên để test chỉ
#: cần gắn một hằng vào header, không phải thread một biến qua từng helper.
IT_TOKEN = "it-token-owner"

# Đặt TRƯỚC khi import bất cứ thứ gì thuộc `app`: Settings đọc env ngay lúc dựng, và
# `get_settings` có lru_cache nên giá trị đặt muộn sẽ không bao giờ được nhìn thấy.
os.environ["AUTH_BOOTSTRAP_EMAIL"] = OWNER_EMAIL
os.environ["EXTENSION_ID"] = "testextensionid"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_RETRY_BACKOFF_MS"] = "10"
# Cổng chết trên loopback: mọi đường gọi Gemini KHÔNG được giả lập (ví dụ sinh mồi nhử chạy
# nền khi test lưu từ) sẽ bị từ chối kết nối ngay lập tức, thay vì bay ra
# generativelanguage.googleapis.com thật bằng "test-key". Không test nào được phép phụ
# thuộc mạng.
os.environ["GEMINI_BASE_URL"] = "http://127.0.0.1:1"
os.environ["AUTH_GOOGLE_TOKEN_URL"] = "http://127.0.0.1:1"
os.environ["AUTH_GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["AUTH_GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["AUTH_ALLOWED_EMAILS"] = f"{OWNER_EMAIL},{SECOND_EMAIL}"
# https chứ không localhost: `AUTH_COOKIE_SECURE=auto` suy cờ Secure từ đây, và cờ đó
# quyết định luôn tên cookie (`__Host-` cấm cookie không-Secure). Để mặc định localhost
# thì toàn bộ test cookie chạy nhánh KHÔNG dùng ở production — đúng nhánh không cần canh.
os.environ["WEB_BASE_URL"] = "https://ielts.test"
# Tắt hạn mức trong test: nó không phải thứ đang được kiểm ở đây, và một test dài vô tình
# chạm trần sẽ đỏ vì lý do chẳng liên quan gì tới nó. Test quota tự bật lại.
os.environ["AUTH_DAILY_GEMINI_CALLS"] = "0"


def sha256(raw: str) -> str:
    """Phải khớp bit-for-bit với `app.auth.service._sha256` — hai chỗ tính hash khác nhau
    thì mọi test gọi API sẽ nhận 401 mà không nói được vì sao."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    import pgserver

    from app.migrator import migrate

    # PYTEST_PG_DIR cho phép tái dùng một data directory giữa các lần chạy — lần chạy đầu
    # tốn ~10 giây để `initdb`, những lần sau gần như tức thì.
    chi_dinh = os.environ.get("PYTEST_PG_DIR", "").strip()
    data_dir = Path(chi_dinh) if chi_dinh else Path(tempfile.mkdtemp(prefix="ielts-pgtest-"))
    server = pgserver.get_server(str(data_dir))
    uri = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(uri, future=True, pool_pre_ping=True)
    migrate(engine, bootstrap_email=OWNER_EMAIL)

    # Trỏ app vào chính Postgres này. Đặt sau `migrate` để lỗi migration không bị che bởi
    # lỗi kết nối.
    os.environ["DATABASE_URL"] = uri
    import app.config
    import app.db

    app.config.get_settings.cache_clear()
    app.db.reset_engine_cache()

    try:
        yield engine
    finally:
        engine.dispose()
        server.cleanup()


#: Mọi bảng có dữ liệu, xếp theo thứ tự xoá được. `app_user` NẰM TRONG danh sách và được
#: dựng lại ngay sau đó — như vậy mỗi test khởi đầu từ đúng một trạng thái, kể cả test đăng
#: nhập vốn tạo thêm tài khoản.
_BANG = [
    "quiz_attempt",
    "quiz_item",
    "review_log",
    "srs_distractor",
    "srs_card",
    "vocab_entry",
    "gemini_usage",
    "user_session",
    "app_user",
    "lookup_cache",
]


@pytest.fixture(autouse=True)
def _don_sach(db_engine: Engine) -> Iterator[None]:
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(_BANG) + " RESTART IDENTITY CASCADE"))
        # Dựng lại tài khoản gốc + phiên của nó, đúng vai trò `ensureOwnerSession` bên Java.
        owner_id = conn.execute(
            text(
                "INSERT INTO app_user (email, display_name) "
                "VALUES (:email, 'Chủ sở hữu dữ liệu cũ') RETURNING id"
            ),
            {"email": OWNER_EMAIL},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO user_session (user_id, token_hash, expires_at) "
                "VALUES (:uid, :hash, now() + interval '60 days')"
            ),
            {"uid": owner_id, "hash": sha256(IT_TOKEN)},
        )
    yield


@dataclass
class NguoiDungTest:
    id: int
    email: str
    token: str
    #: `"bearer"` (extension) hoặc `"cookie"` (web app). Xem `headers`.
    che_do: str = "bearer"

    @property
    def headers(self) -> dict[str, str]:
        """Cách request này mang danh tính.

        Hai đường, và `test_multi_user_isolation.py` chạy TOÀN BỘ bộ test của nó qua cả hai
        (fixture `hai_nguoi` được parametrize). Lý do: cookie là đường xác thực THỨ HAI cho
        mọi endpoint chạm dữ liệu học, và ràng buộc #13 nói rõ endpoint chưa có mặt trong
        file đó là endpoint chưa được chứng minh an toàn — một đường xác thực mới cũng vậy.

        Cookie gửi bằng header `Cookie` thô chứ không qua cookie jar của client: như vậy nó
        vẫn chỉ là một dict header, và mọi test hiện có dùng lại được không sửa một dòng.
        `X-IELTS-Web` là bắt buộc — xem `deps.cookie_token`.
        """
        if self.che_do == "cookie":
            from app.auth.cookies import session_cookie_name
            from app.config import get_settings

            return {
                "Cookie": f"{session_cookie_name(get_settings())}={self.token}",
                "X-IELTS-Web": "1",
            }
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def tao_nguoi_dung(db: Session, email: str) -> NguoiDungTest:
    """Tạo tài khoản + phiên, trả về token THÔ để gắn vào header Authorization."""
    uid = int(
        db.execute(
            text(
                "INSERT INTO app_user (google_sub, email, display_name) "
                "VALUES (:sub, :email, :ten) "
                "ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name "
                "RETURNING id"
            ),
            {"sub": f"sub-{email}", "email": email.lower(), "ten": email},
        ).scalar_one()
    )
    token = f"test-token-{uid}-{email}"
    db.execute(
        text(
            "INSERT INTO user_session (user_id, token_hash, expires_at) "
            "VALUES (:uid, :hash, now() + interval '60 days')"
        ),
        {"uid": uid, "hash": sha256(token)},
    )
    db.commit()
    return NguoiDungTest(uid, email.lower(), token)


@pytest.fixture
def owner(db: Session) -> NguoiDungTest:
    """Tài khoản gốc do V6 tạo — chủ của mọi dữ liệu trong test một-người-dùng."""
    uid = db.execute(
        text("SELECT id FROM app_user WHERE email = :e"), {"e": OWNER_EMAIL}
    ).scalar_one()
    return NguoiDungTest(int(uid), OWNER_EMAIL, IT_TOKEN)


@pytest.fixture
def user_a(owner: NguoiDungTest) -> NguoiDungTest:
    """Người dùng thứ nhất trong test hai-người-dùng — chính là tài khoản gốc."""
    return owner


@pytest.fixture
def user_b(db: Session) -> NguoiDungTest:
    return tao_nguoi_dung(db, SECOND_EMAIL)


@pytest.fixture
def client(db: Session) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import create_app

    application = create_app()

    def _get_db_test() -> Iterator[Session]:
        # KHÔNG đóng session ở đây: fixture `db` sở hữu vòng đời của nó, và test thường đọc
        # lại DB sau khi gọi API. Vẫn commit như production để test thấy đúng thứ đã được
        # ghi xuống thật.
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    application.dependency_overrides[get_db] = _get_db_test
    # https chứ không http mặc định: cookie phiên của web mang cờ `Secure`, và httpx KHÔNG
    # gửi lại cookie Secure qua http. Để `http://testserver` thì mọi test đường cookie hỏng
    # theo kiểu "state không khớp" — một triệu chứng trỏ đi hoàn toàn sai hướng.
    # Production cũng luôn là https (Caddy terminate TLS, Vercel mặc định).
    with TestClient(application, base_url="https://testserver") as tc:
        yield tc
    application.dependency_overrides.clear()


@dataclass
class GeminiGia:
    """Thay WireMock: chặn tầng vận chuyển của httpx và trả sẵn payload.

    Chặn ở `httpx.BaseTransport` chứ không thay thẳng `GeminiClient`: như vậy toàn bộ đường
    đi thật — dựng body, đọc `candidates[0].content.parts[0].text`, map status code sang
    ErrorCode — vẫn được test chạy qua. Giả lập ở tầng cao hơn là bỏ qua đúng phần dễ port
    sai nhất.
    """

    phan_hoi: list[httpx.Response] = field(default_factory=list)
    requests: list[httpx.Request] = field(default_factory=list)
    #: Phản hồi dùng khi hàng đợi cạn. None = cạn thì báo lỗi test.
    mac_dinh: httpx.Response | None = None

    def tra_json(self, payload: Any, lap: int = 1) -> None:
        """Xếp hàng phản hồi thành công. `payload` là JSON mà model 'sinh ra'."""
        for _ in range(lap):
            self.phan_hoi.append(_boc_candidate(payload))

    def tra_text(self, inner: str) -> None:
        """Xếp hàng phản hồi mà phần model sinh ra KHÔNG phải JSON hợp lệ."""
        self.phan_hoi.append(
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": inner}]}}]})
        )

    def tra_status(self, status: int, body: str = "{}", lap: int = 1) -> None:
        """Xếp hàng phản hồi lỗi HTTP thô (429 quota, 503 chết, 401 sai key...)."""
        for _ in range(lap):
            self.phan_hoi.append(httpx.Response(status, text=body))

    def tra_raw(self, response: httpx.Response) -> None:
        self.phan_hoi.append(response)

    @property
    def so_lan_goi(self) -> int:
        return len(self.requests)


def _boc_candidate(payload: Any) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}
            ]
        },
    )


class _TransportGia(httpx.BaseTransport):
    def __init__(self, gia: GeminiGia) -> None:
        self._gia = gia

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._gia.requests.append(request)
        if self._gia.phan_hoi:
            return self._gia.phan_hoi.pop(0)
        if self._gia.mac_dinh is not None:
            return self._gia.mac_dinh
        raise AssertionError(
            f"Bị gọi ra ngoài {len(self._gia.requests) - 1} phản hồi đã xếp sẵn "
            f"(URL: {request.url}). Gần như luôn là dấu hiệu code gọi Gemini nhiều hơn dự "
            "kiến — ví dụ cache không ăn, hoặc retry chạy khi lẽ ra không được retry."
        )


@pytest.fixture
def gemini(monkeypatch: pytest.MonkeyPatch) -> Iterator[GeminiGia]:
    gia = GeminiGia()
    goc = httpx.Client.__init__

    def _init(self: httpx.Client, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = _TransportGia(gia)
        goc(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.Client, "__init__", _init)

    from app.auth import google as google_mod
    from app.common import gemini as gemini_mod

    gemini_mod.reset_gemini_client_cache()
    google_mod.reset_google_client_cache()
    try:
        yield gia
    finally:
        gemini_mod.reset_gemini_client_cache()
        google_mod.reset_google_client_cache()


@pytest.fixture
def khong_goi_gemini(gemini: GeminiGia) -> Callable[[], None]:
    """Khẳng định không có lượt gọi ra ngoài nào — dùng cho test cache hit."""

    def kiem_tra() -> None:
        assert gemini.requests == [], f"Không được gọi Gemini nhưng đã gọi {gemini.so_lan_goi} lần"

    return kiem_tra
