#!/usr/bin/env bash
set -euo pipefail

# Build command của Vercel. Làm hai việc, theo đúng thứ tự này:
#
#   1. Dựng SPA (apps/web) rồi đặt kết quả vào `api-service/static/` — FastAPI phục vụ nó từ
#      đó (xem `app/web_static.py`).
#   2. Chạy migration như trước.
#
# VÌ SAO `npm ci` nằm TRONG buildCommand chứ không phải `installCommand`:
# Vercel chỉ có MỘT `installCommand` cho một project, và nó đang là bước `pip install` tự
# động của preset FastAPI. Đặt nó thành `npm ci` là xoá mất bước cài Python — deploy sẽ hỏng
# ở chỗ chẳng liên quan gì tới frontend.

GOC_SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GOC_REPO="$(dirname "$GOC_SERVICE")"

echo "==> Dựng web app"

# Root Directory của Vercel là `api-service`, nên `packages/` và `apps/` nằm NGOÀI nó. Chúng
# chỉ có mặt khi bật toggle "Include source files outside of the Root Directory in the Build
# Step" trên dashboard.
#
# Kiểm tường minh và DỪNG HẲN nếu thiếu. Bỏ qua rồi deploy tiếp là kiểu hỏng tệ nhất: build
# xanh, API chạy, chỉ có web là 404 — và không dòng log nào nói vì sao.
if [ ! -f "$GOC_REPO/package.json" ] || [ ! -d "$GOC_REPO/apps/web" ]; then
  echo "LỖI: không thấy monorepo ở $GOC_REPO" >&2
  echo "" >&2
  echo "Trên Vercel: bật 'Include source files outside of the Root Directory in the" >&2
  echo "Build Step' trong Settings -> Build and Deployment. Không có nó thì chỉ thư mục" >&2
  echo "api-service/ được tải lên, và apps/web không tồn tại lúc build." >&2
  exit 1
fi

cd "$GOC_REPO"
npm ci
npm run build:web

echo "==> Chép SPA vào $GOC_SERVICE/static"
# Xoá trước rồi chép: build cũ còn sót lại sẽ để lại asset của lần deploy trước, mà tên asset
# có hash nên chúng không bao giờ bị ghi đè — thư mục phình dần qua từng lần deploy.
rm -rf "$GOC_SERVICE/static"
cp -R "$GOC_REPO/apps/web/dist" "$GOC_SERVICE/static"

# Chốt chặn cuối: `index.html` là thứ `app/web_static.py` dò để quyết định có phục vụ SPA hay
# không. Thiếu nó thì backend lặng lẽ chạy ở chế độ chỉ-API.
if [ ! -f "$GOC_SERVICE/static/index.html" ]; then
  echo "LỖI: build xong nhưng không có static/index.html" >&2
  exit 1
fi
echo "    OK: $(find "$GOC_SERVICE/static" -type f | wc -l | tr -d ' ') file"

echo "==> Migration"
cd "$GOC_SERVICE"
exec bash scripts/migrate-on-deploy.sh
