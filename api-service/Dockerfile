# Bản Docker cho đường chạy local/VPS. Đường Vercel KHÔNG dùng file này — ở đó preset
# FastAPI của Vercel tự dò entrypoint và nạp `app/main.py` (KHÔNG phải `api/index.py`;
# thư mục `api/` không nằm trong danh sách nó dò).
#
# Hai đường phải phục vụ web app GIỐNG HỆT nhau (ràng buộc #15), nên stage `web` dưới đây
# làm đúng việc mà `scripts/build-web-and-migrate.sh` làm trên Vercel: dựng SPA rồi đặt vào
# `static/` để `app/web_static.py` tìm thấy.

# ── Stage 1: dựng SPA ────────────────────────────────────────────────────────
FROM node:22-slim AS web

WORKDIR /repo
# Chép manifest trước, cài xong rồi mới chép mã nguồn: sửa code không làm mất cache lớp cài.
COPY package.json package-lock.json ./
COPY packages/core/package.json ./packages/core/
COPY apps/web/package.json ./apps/web/
COPY apps/extension/package.json ./apps/extension/
RUN npm ci

COPY packages/core ./packages/core
COPY apps/web ./apps/web
RUN npm run build:web

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Cài phụ thuộc trước, chép mã nguồn sau: sửa code không làm mất cache lớp cài đặt.
COPY api-service/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        "pydantic>=2.9" \
        "pydantic-settings>=2.6" \
        "sqlalchemy>=2.0" \
        "psycopg[binary]>=3.2" \
        "httpx>=0.27"

COPY api-service/app ./app
COPY api-service/migrations ./migrations
COPY api-service/prompts ./prompts
COPY --from=web /repo/apps/web/dist ./static

EXPOSE 8080

# SERVER_ADDRESS mặc định 127.0.0.1 (chạy ngoài container); compose set 0.0.0.0. Đọc từ
# env ngay tại entrypoint để một image dùng được cho cả hai cách chạy.
CMD ["sh", "-c", "python -m app.startup && exec uvicorn app.main:app --host ${SERVER_ADDRESS:-0.0.0.0} --port ${SERVER_PORT:-8080}"]
