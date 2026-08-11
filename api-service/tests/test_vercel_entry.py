"""Lớp khôi phục đường dẫn cho Vercel.

Vercel rewrite `/(.*)` về `/api/index` bằng cách THAY đường dẫn gốc, không phải chỉ định
tuyến tới function. FastAPI vì thế thấy mọi request đều là `/api/index` và trả 404 cho toàn
bộ API — triệu chứng là mọi endpoint cùng hỏng với một thông điệp giống hệt nhau.

Test ở đây gọi thẳng ASGI app của `api/index.py` để chứng minh lớp khôi phục làm đúng việc,
mà không cần deploy.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.index import FUNCTION_PATH, RestoreOriginalPath


class _RecordingApp:
    """Ghi lại scope nhận được thay vì xử lý thật."""

    def __init__(self) -> None:
        self.received_path: str | None = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.received_path = scope.get("path")


def _scope(
    path: str,
    headers: list[tuple[bytes, bytes]] | None = None,
    query_string: bytes = b"",
) -> dict[str, Any]:
    return {
        "type": "http",
        "path": path,
        "headers": headers or [],
        "query_string": query_string,
    }


def call(app: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """Chạy ASGI app một lượt.

    Đồng bộ hoá bằng `asyncio.run` thay vì kéo thêm `pytest-asyncio` vào chỉ cho sáu test
    (ràng buộc #12).
    """
    return asyncio.run(_call_async(app, scope))


async def _call_async(app: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    async def receive() -> dict[str, Any]:  # pragma: no cover - không dùng tới
        return {"type": "http.request"}

    await app(scope, receive, send)
    return sent


class _RecordingScope(_RecordingApp):
    """Giữ nguyên cả scope để soi query string sau khi middleware sửa."""

    def __init__(self) -> None:
        super().__init__()
        self.received_query: bytes | None = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await super().__call__(scope, receive, send)
        self.received_query = scope.get("query_string")


def test_recovers_path_from_query_param() -> None:
    """Cơ chế CHÍNH: `vercel.json` khai `destination: /api/index?__path=/$1`.

    Dùng query string chứ không dò header vì đây là thứ mình tự khai trong `vercel.json` —
    có mặt hay không là chuyện kiểm chứng được, khác hẳn việc đoán xem Vercel để lại header
    nào (thực tế: không cái nào).
    """
    recorder = _RecordingScope()
    call(
        RestoreOriginalPath(recorder),
        _scope(FUNCTION_PATH, query_string=b"__path=/api/auth/google"),
    )

    assert recorder.received_path == "/api/auth/google"


def test_removes_path_param_but_keeps_the_rest_of_the_query() -> None:
    """`__path` phải BIẾN MẤT trước khi tới handler.

    Để lại thì nó lọt vào mọi endpoint như một tham số lạ, và chỗ nào validate query chặt sẽ
    từ chối một request hoàn toàn hợp lệ.
    """
    recorder = _RecordingScope()
    call(
        RestoreOriginalPath(recorder),
        _scope(FUNCTION_PATH, query_string=b"__path=/api/vocab&q=mitigate&page=2"),
    )

    assert recorder.received_path == "/api/vocab"
    assert recorder.received_query == b"q=mitigate&page=2"


def test_decodes_percent_encoded_path() -> None:
    """Đường dẫn đi qua query nên dấu `/` và ký tự lạ có thể bị mã hoá."""
    recorder = _RecordingScope()
    call(
        RestoreOriginalPath(recorder),
        _scope(FUNCTION_PATH, query_string=b"__path=%2Fapi%2Fvocab%2F42"),
    )

    assert recorder.received_path == "/api/vocab/42"


def test_query_param_wins_over_header() -> None:
    """Query là thứ mình khai; header chỉ là đường lui. Hai cái mâu thuẫn thì tin cái mình
    kiểm soát được."""
    recorder = _RecordingScope()
    call(
        RestoreOriginalPath(recorder),
        _scope(
            FUNCTION_PATH,
            headers=[(b"x-forwarded-uri", b"/api/sai")],
            query_string=b"__path=/api/health",
        ),
    )

    assert recorder.received_path == "/api/health"


@pytest.mark.parametrize(
    "header_name",
    [
        b"x-vercel-original-path",
        b"x-original-uri",
        b"x-forwarded-uri",
        b"x-rewrite-url",
    ],
)
def test_recovers_path_from_any_candidate_header(header_name: bytes) -> None:
    """Thử nhiều header chứ không một: Vercel không cam kết header nào, và đoán sai một cái
    là hỏng TOÀN BỘ API chứ không phải một endpoint."""
    recorder = _RecordingApp()
    call(
        RestoreOriginalPath(recorder),
        _scope(FUNCTION_PATH, [(header_name, b"/api/auth/google")]),
    )

    assert recorder.received_path == "/api/auth/google"


def test_strips_query_string_from_path() -> None:
    """`scope["path"]` không bao giờ chứa query string; để lẫn vào là không route nào khớp."""
    recorder = _RecordingApp()
    call(
        RestoreOriginalPath(recorder),
        _scope(FUNCTION_PATH, [(b"x-vercel-original-path", b"/api/vocab?q=mitigate")]),
    )

    assert recorder.received_path == "/api/vocab"


def test_passes_through_when_path_is_already_correct() -> None:
    """Chạy Docker hay `python -m app` thì đường dẫn không bị viết đè — lớp này phải trong
    suốt, không được sửa gì."""
    recorder = _RecordingApp()
    call(RestoreOriginalPath(recorder), _scope("/api/health"))

    assert recorder.received_path == "/api/health"


def test_reports_clearly_instead_of_silent_404_when_unrecoverable() -> None:
    """404 câm là ca tệ nhất: mọi endpoint cùng hỏng với thông điệp giống hệt nhau, không
    phân biệt được "sai cấu hình proxy" với "gõ sai URL"."""
    sent = call(
        RestoreOriginalPath(_RecordingApp()),
        _scope(FUNCTION_PATH, [(b"x-vercel-id", b"hkg1::abc"), (b"host", b"x.vercel.app")]),
    )

    assert sent[0]["status"] == 500
    body = json.loads(sent[1]["body"])
    assert "Không khôi phục được đường dẫn gốc" in body["message"]
    # Liệt kê TÊN header để chẩn đoán được...
    assert "x-vercel-id" in body["message"]


def test_never_leaks_header_values() -> None:
    """...nhưng KHÔNG kèm giá trị: `authorization` và `cookie` nằm trong cùng danh sách đó."""
    sent = call(
        RestoreOriginalPath(_RecordingApp()),
        _scope(
            FUNCTION_PATH,
            [(b"authorization", b"Bearer SIEU-BI-MAT"), (b"cookie", b"phien=BI-MAT")],
        ),
    )

    body = json.loads(sent[1]["body"])
    assert "SIEU-BI-MAT" not in body["message"]
    assert "BI-MAT" not in body["message"]
    assert "authorization" in body["message"]


def test_ignores_header_pointing_back_at_function_path() -> None:
    """Tránh vòng lặp: header trỏ về `/api/index` không khôi phục được gì."""
    sent = call(
        RestoreOriginalPath(_RecordingApp()),
        _scope(FUNCTION_PATH, [(b"x-forwarded-uri", FUNCTION_PATH.encode())]),
    )

    assert sent[0]["status"] == 500
