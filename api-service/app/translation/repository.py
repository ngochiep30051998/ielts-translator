"""Truy vấn của context translation. Mọi câu chạm `lookup_cache` nằm ở đây.

Không câu nào lọc theo `user_id`, và đó là CỐ Ý (ràng buộc #14): `lookup_cache` là cache bản
dịch của một chuỗi công khai, dùng chung giữa mọi người dùng là phần tiết kiệm quota Gemini
lớn nhất của hệ thống. Đây là ngoại lệ DUY NHẤT của ràng buộc #13 — thêm `user_id` vào đây
"cho nhất quán" là bỏ đi lợi ích chính của bảng.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.translation.models import LookupCache


def find_by_source_hash(db: Session, source_hash: str) -> LookupCache | None:
    return db.scalars(select(LookupCache).where(LookupCache.source_hash == source_hash)).first()


def increment_hit_count(db: Session, cache_id: int) -> None:
    """Tăng bộ đếm bằng một câu UPDATE tại chỗ chứ không đọc-sửa-ghi qua entity: hai lượt
    tra song song cùng một chuỗi sẽ cùng đọc ra một số rồi cùng ghi đè nhau."""
    db.execute(
        update(LookupCache)
        .where(LookupCache.id == cache_id)
        .values(hit_count=LookupCache.hit_count + 1)
    )


def save(db: Session, entry: LookupCache) -> LookupCache:
    """Flush ngay thay vì đợi commit ở cuối request: ràng buộc UNIQUE trên `source_hash` nổ
    ở đây thì còn nằm trong tầm của exception handler."""
    db.add(entry)
    db.flush()
    return entry
