"""Kết nối database — engine, session factory, dependency `get_db`.

Hai quyết định cố ý, chép từ spec:

**SQLAlchemy sync, không async.** Serverless mỗi instance phục vụ một request nên async
không mua được gì về thông lượng, mà lại thêm một lớp để sai. FastAPI chạy endpoint `def`
thường trong threadpool — hoàn toàn đủ.

**psycopg v3, không asyncpg.** Cả hai driver đều tự tạo prepared statement, và Supavisor ở
transaction mode (cổng 6543, đúng chế độ dành cho serverless) không chịu được điều đó —
triệu chứng là lỗi rời rạc dưới tải, loại khó lần nhất.

Điểm khác nhau, và là lý do chọn psycopg: nó **tắt được** bằng `prepare_threshold=None`.
Đừng đọc câu này thành "psycopg mặc định đã an toàn" — mặc định của nó là tạo prepared
statement sau 5 lần chạy cùng một câu. Việc tắt nằm ở `get_engine()` bên dưới, và có test
canh (`tests/test_deploy_readiness.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Base khai báo chung cho mọi entity.

    Mọi bảng nằm trong cùng một metadata để `Base.metadata.sort_tables` và các kiểm tra
    schema thấy hết. Schema THẬT do `migrations/V*.sql` dựng, không phải do `create_all` —
    y như `ddl-auto: validate` bên Java: entity phải khớp DDL, không phải sinh ra DDL.
    """


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    engine_kwargs: dict[str, Any] = {"future": True}

    if settings.uses_transaction_pooler:
        # TẮT HẲN prepared statement. psycopg tự tạo prepared statement sau 5 lần chạy cùng
        # một câu; pooler ở transaction mode ghép nhiều client lên chung backend, nên câu
        # thứ sáu có thể rơi vào một backend chưa từng thấy statement đó và chết bằng
        # `prepared statement "_pg3_N" does not exist`.
        #
        # Đây chính là lớp lỗi mà quyết định "dùng psycopg chứ không asyncpg" định né —
        # psycopg né được vì TẮT ĐƯỢC, không phải vì mặc định đã tắt.
        engine_kwargs["connect_args"] = {"prepare_threshold": None}

    if settings.is_serverless:
        # Serverless: mỗi instance sống vài giây và phục vụ một request. Giữ pool phía
        # client chỉ chiếm chỗ trong hạn mức kết nối của Supabase mà không tái dùng được —
        # Supavisor đã là cái pool rồi.
        engine_kwargs["poolclass"] = NullPool
    else:
        # Tiến trình dài: pooler cắt kết nối nhàn rỗi mà không báo. Không có cờ này thì
        # request đầu tiên sau một quãng im lặng chết bằng "server closed the connection
        # unexpectedly". Với NullPool thì thừa, vì mỗi lượt đã là kết nối mới.
        engine_kwargs["pool_pre_ping"] = True

    return create_engine(settings.sqlalchemy_url, **engine_kwargs)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Thay `@Transactional`: commit khi handler trả về bình thường,
    rollback khi có exception bay ra."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Chỉ dùng trong test: buộc dựng lại engine sau khi đổi biến môi trường."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
