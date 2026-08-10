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

from api.index import FUNCTION_PATH, KhoiPhucDuongDan


class _AppGia:
    """Ghi lại scope nhận được thay vì xử lý thật."""

    def __init__(self) -> None:
        self.duong_dan_nhan_duoc: str | None = None

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.duong_dan_nhan_duoc = scope.get("path")


def _scope(path: str, headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {"type": "http", "path": path, "headers": headers or []}


def _goi(app: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """Chạy ASGI app một lượt. Đồng bộ hoá bằng `asyncio.run` thay vì kéo thêm
    `pytest-asyncio` vào chỉ cho sáu test (ràng buộc #12)."""
    return asyncio.run(_goi_async(app, scope))


async def _goi_async(app: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    gui: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        gui.append(message)

    async def receive() -> dict[str, Any]:  # pragma: no cover - không dùng tới
        return {"type": "http.request"}

    await app(scope, receive, send)
    return gui


@pytest.mark.parametrize(
    "ten_header",
    [
        b"x-vercel-original-path",
        b"x-original-uri",
        b"x-forwarded-uri",
        b"x-rewrite-url",
    ],
)
def test_khoi_phuc_duoc_tu_bat_ky_header_ung_vien_nao(ten_header: bytes) -> None:
    """Thử nhiều header chứ không một: Vercel không cam kết header nào, và đoán sai một cái
    là hỏng TOÀN BỘ API chứ không phải một endpoint."""
    gia = _AppGia()
    _goi(
        KhoiPhucDuongDan(gia),
        _scope(FUNCTION_PATH, [(ten_header, b"/api/auth/google")]),
    )

    assert gia.duong_dan_nhan_duoc == "/api/auth/google"


def test_cat_query_string_khoi_duong_dan() -> None:
    """`scope["path"]` không bao giờ chứa query string; để lẫn vào là không route nào khớp."""
    gia = _AppGia()
    _goi(
        KhoiPhucDuongDan(gia),
        _scope(FUNCTION_PATH, [(b"x-vercel-original-path", b"/api/vocab?q=mitigate")]),
    )

    assert gia.duong_dan_nhan_duoc == "/api/vocab"


def test_khong_dung_toi_khi_duong_dan_da_dung() -> None:
    """Chạy Docker hay `python -m app` thì đường dẫn không bị viết đè — lớp này phải trong
    suốt, không được sửa gì."""
    gia = _AppGia()
    _goi(KhoiPhucDuongDan(gia), _scope("/api/health"))

    assert gia.duong_dan_nhan_duoc == "/api/health"


def test_khong_khoi_phuc_duoc_thi_bao_ro_thay_vi_404_cam() -> None:
    """404 câm là ca tệ nhất: mọi endpoint cùng hỏng với thông điệp giống hệt nhau, không
    phân biệt được "sai cấu hình proxy" với "gõ sai URL"."""
    gui = _goi(
        KhoiPhucDuongDan(_AppGia()),
        _scope(FUNCTION_PATH, [(b"x-vercel-id", b"hkg1::abc"), (b"host", b"x.vercel.app")]),
    )

    assert gui[0]["status"] == 500
    than = json.loads(gui[1]["body"])
    assert "Không khôi phục được đường dẫn gốc" in than["message"]
    # Liệt kê TÊN header để chẩn đoán được...
    assert "x-vercel-id" in than["message"]


def test_khong_bao_gio_lo_gia_tri_header() -> None:
    """...nhưng KHÔNG kèm giá trị: `authorization` và `cookie` nằm trong cùng danh sách đó."""
    gui = _goi(
        KhoiPhucDuongDan(_AppGia()),
        _scope(
            FUNCTION_PATH,
            [(b"authorization", b"Bearer SIEU-BI-MAT"), (b"cookie", b"phien=BI-MAT")],
        ),
    )

    than = json.loads(gui[1]["body"])
    assert "SIEU-BI-MAT" not in than["message"]
    assert "BI-MAT" not in than["message"]
    assert "authorization" in than["message"]


def test_header_tro_lai_chinh_function_path_thi_coi_nhu_khong_co() -> None:
    """Tránh vòng lặp: header trỏ về `/api/index` không khôi phục được gì."""
    gui = _goi(
        KhoiPhucDuongDan(_AppGia()),
        _scope(FUNCTION_PATH, [(b"x-forwarded-uri", FUNCTION_PATH.encode())]),
    )

    assert gui[0]["status"] == 500
