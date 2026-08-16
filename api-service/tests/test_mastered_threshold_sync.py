"""Chốt chặn liên ngôn ngữ cho ngưỡng "đã thuộc".

`MASTERED_REPETITIONS` sống ở HAI file, hai ngôn ngữ: `app/srs/models.py` (backend đếm
`mastered` của từng chủ đề ở `GET /api/vocab/tags` và `masteredWords` ở `GET /api/stats`) và
`packages/core/src/vocab-progress.ts` (frontend vẽ số vạch thanh thành thạo và đổi nhãn sang
"đã thuộc" tại đúng ngưỡng đó).

Trước file này hai con số chỉ trỏ nhau bằng comment: đổi backend thành 6 thì TOÀN BỘ test
backend lẫn test JS vẫn xanh, còn người dùng thấy thanh thành thạo đầy kín trong khi chip
chủ đề vẫn báo chưa thuộc — hai kênh nói ngược nhau trên cùng một màn hình.

Đọc file TypeScript bằng regex là cách xấu, và cố ý: ràng buộc này bắc qua hai hệ thống build
không biết gì về nhau, không có chỗ nào khác giữ được nó. Test đọc THẲNG file nguồn chứ không
đọc bản build — bản build có thể cũ hơn file nguồn nhiều commit.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.srs.models import MASTERED_REPETITIONS

#: `tests/` → `api-service/` → gốc repo. Cùng cách lần lên như `test_deploy_readiness.py`,
#: chỉ đi thêm một bậc vì đích nằm ngoài `api-service/`.
GOC_REPO = Path(__file__).resolve().parents[2]
NGUON_TS = GOC_REPO / "packages" / "core" / "src" / "vocab-progress.ts"

#: Neo vào ĐÚNG dòng khai báo (`^export const ... = <số>;`) chứ không bắt mọi chỗ nhắc tên
#: đó: file còn dùng lại `MASTERED_REPETITIONS` ở bốn chỗ khác, và một regex lỏng sẽ bắt
#: nhầm rồi hoặc đỏ vô cớ hoặc xanh vô cớ.
KHAI_BAO_TS = re.compile(r"^export const MASTERED_REPETITIONS\s*=\s*(\d+)\s*;", re.MULTILINE)


def test_nguong_thuoc_bang_nhau_o_backend_va_frontend() -> None:
    assert NGUON_TS.is_file(), (
        f"Không thấy {NGUON_TS}. File này là nguồn duy nhất của ngưỡng thuộc phía frontend — "
        "nếu nó bị đổi chỗ thì phải sửa đường dẫn ở đây, đừng xoá test."
    )

    khop = KHAI_BAO_TS.search(NGUON_TS.read_text(encoding="utf-8"))
    assert khop is not None, (
        f"Không tìm thấy dòng `export const MASTERED_REPETITIONS = <số>;` trong {NGUON_TS}. "
        "Đổi cách khai báo (ví dụ suy từ độ dài một mảng) thì phải cập nhật regex này, "
        "nếu không ràng buộc hai phía mất chốt chặn mà không có gì đỏ."
    )

    nguong_ts = int(khop.group(1))
    assert nguong_ts == MASTERED_REPETITIONS, (
        f"Ngưỡng thuộc lệch nhau: backend `app/srs/models.py` = {MASTERED_REPETITIONS}, "
        f"frontend `packages/core/src/vocab-progress.ts` = {nguong_ts}. Sửa CẢ HAI trong "
        "cùng một thay đổi — lệch nhau thì thanh thành thạo và chip chủ đề nói ngược nhau."
    )
