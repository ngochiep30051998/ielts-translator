"""Điểm vào của Vercel.

`vercel.json` rewrite MỌI đường dẫn về file này. Lý do: gói Hobby giới hạn 12 function mỗi
lần deploy, mà API có nhiều endpoint hơn thế — chia theo file là chạm trần ngay.

Migration KHÔNG chạy ở đây: xem ghi chú trong `app/startup.py`. Trên Vercel, schema do
Supabase quản lý (chạy `migrations/V*.sql` một lần bằng tay hoặc bằng Supabase CLI).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Vercel đặt working directory ở gốc project chứ không ở `api/`, nhưng không tự thêm gốc
# vào sys.path. Không có ba dòng này thì `import app.main` chết ngay lúc cold start với
# ModuleNotFoundError — mà log thì chỉ hiện ở dashboard, không hiện khi chạy local.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

__all__ = ["app"]
