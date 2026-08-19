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
REPO_ROOT = Path(__file__).resolve().parents[2]
TS_SOURCE = REPO_ROOT / "packages" / "core" / "src" / "vocab-progress.ts"

#: Neo vào ĐÚNG dòng khai báo (`^export const ... = <số>;`) chứ không bắt mọi chỗ nhắc tên
#: đó: file còn dùng lại `MASTERED_REPETITIONS` ở bốn chỗ khác, và một regex lỏng sẽ bắt
#: nhầm rồi hoặc đỏ vô cớ hoặc xanh vô cớ.
TS_DECLARATION = re.compile(r"^export const MASTERED_REPETITIONS\s*=\s*(\d+)\s*;", re.MULTILINE)


def test_mastered_threshold_equal_in_backend_and_frontend() -> None:
    assert TS_SOURCE.is_file(), (
        f"Không thấy {TS_SOURCE}. File này là nguồn duy nhất của ngưỡng thuộc phía frontend — "
        "nếu nó bị đổi chỗ thì phải sửa đường dẫn ở đây, đừng xoá test."
    )

    declaration_match = TS_DECLARATION.search(TS_SOURCE.read_text(encoding="utf-8"))
    assert declaration_match is not None, (
        f"Không tìm thấy dòng `export const MASTERED_REPETITIONS = <số>;` trong {TS_SOURCE}. "
        "Đổi cách khai báo (ví dụ suy từ độ dài một mảng) thì phải cập nhật regex này, "
        "nếu không ràng buộc hai phía mất chốt chặn mà không có gì đỏ."
    )

    ts_threshold = int(declaration_match.group(1))
    assert ts_threshold == MASTERED_REPETITIONS, (
        f"Ngưỡng thuộc lệch nhau: backend `app/srs/models.py` = {MASTERED_REPETITIONS}, "
        f"frontend `packages/core/src/vocab-progress.ts` = {ts_threshold}. Sửa CẢ HAI trong "
        "cùng một thay đổi — lệch nhau thì thanh thành thạo và chip chủ đề nói ngược nhau."
    )
