# Bản Docker cho đường chạy local/VPS. Đường Vercel KHÔNG dùng file này — Vercel dựng
# runtime Python riêng từ `api/index.py` và `requirements.txt`.
FROM python:3.12-slim

WORKDIR /app

# Cài phụ thuộc trước, chép mã nguồn sau: sửa code không làm mất cache lớp cài đặt.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        "pydantic>=2.9" \
        "pydantic-settings>=2.6" \
        "sqlalchemy>=2.0" \
        "psycopg[binary]>=3.2" \
        "httpx>=0.27"

COPY app ./app
COPY migrations ./migrations
COPY prompts ./prompts

EXPOSE 8080

# SERVER_ADDRESS mặc định 127.0.0.1 (chạy ngoài container); compose set 0.0.0.0. Đọc từ
# env ngay tại entrypoint để một image dùng được cho cả hai cách chạy.
CMD ["sh", "-c", "python -m app.startup && exec uvicorn app.main:app --host ${SERVER_ADDRESS:-0.0.0.0} --port ${SERVER_PORT:-8080}"]
