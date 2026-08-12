#!/usr/bin/env bash
set -euo pipefail

# Preview deploy KHÔNG được đụng vào DB production.
if [ "${VERCEL_ENV:-}" != "production" ]; then
  echo "Bỏ qua migration: VERCEL_ENV=${VERCEL_ENV:-chưa đặt}"
  exit 0
fi

: "${MIGRATION_DATABASE_URL:?Thiếu MIGRATION_DATABASE_URL (session pooler, cổng 5432)}"
: "${AUTH_BOOTSTRAP_EMAIL:?Thiếu AUTH_BOOTSTRAP_EMAIL — V6 dùng nó để gán chủ sở hữu sổ từ cũ}"

pip3 install --quiet -r requirements.txt
DATABASE_URL="$MIGRATION_DATABASE_URL" python3 -m app.startup