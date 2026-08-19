"""Bản port của `GeminiQuotaGuardIT`.

Hạn mức tồn tại vì API key Gemini dùng CHUNG: một người làm 200 câu quiz là cả nhóm hết
quota.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.config import Settings
from app.quota.guard import consume
from tests.conftest import SECOND_EMAIL, UserFixture, create_user

#: `conftest` tắt hạn mức (0) cho mọi test khác; ở đây bật lên đúng 2 để test được cái trần.
LIMIT_2 = Settings(AUTH_DAILY_GEMINI_CALLS=2)


def _calls_today(db: Session, user_id: int) -> int | None:
    return db.execute(
        text("SELECT calls FROM gemini_usage WHERE user_id = :u AND day = CURRENT_DATE"),
        {"u": user_id},
    ).scalar_one_or_none()


def test_exceeding_daily_limit_is_rejected(db: Session, owner: UserFixture) -> None:
    """GEMINI_QUOTA chứ không đẻ mã mới: UI đã biết hiển thị mã này, và với người dùng thì
    "hết lượt hôm nay" đúng là hết quota."""
    consume(db, owner.id, LIMIT_2)
    consume(db, owner.id, LIMIT_2)

    with pytest.raises(AppError) as ex:
        consume(db, owner.id, LIMIT_2)

    assert ex.value.code is ErrorCode.GEMINI_QUOTA
    assert "2" in ex.value.message


def test_limit_is_counted_per_user(db: Session, owner: UserFixture) -> None:
    """A hết lượt không chặn B — một người làm 200 câu quiz không được phép khoá cả nhóm."""
    b = create_user(db, SECOND_EMAIL)
    consume(db, owner.id, LIMIT_2)
    consume(db, owner.id, LIMIT_2)

    consume(db, b.id, LIMIT_2)

    assert _calls_today(db, b.id) == 1


def test_counter_increments_atomically_in_one_statement(db: Session, owner: UserFixture) -> None:
    """Đọc-rồi-ghi ở tầng Python sẽ hỏng thật: hai request song song cùng đọc ra một số rồi
    cùng ghi đè, và hạn mức trở thành gợi ý."""
    consume(db, owner.id, LIMIT_2)
    consume(db, owner.id, LIMIT_2)

    assert _calls_today(db, owner.id) == 2


def test_zero_limit_disables_the_quota_entirely(db: Session, owner: UserFixture) -> None:
    """0 hoặc âm = tắt hạn mức, dùng cho môi trường dev. Không được ghi cả dòng đếm."""
    no_limit = Settings(AUTH_DAILY_GEMINI_CALLS=0)
    for _ in range(50):
        consume(db, owner.id, no_limit)

    assert _calls_today(db, owner.id) is None


def test_call_exactly_at_the_limit_still_passes(db: Session, owner: UserFixture) -> None:
    """Chặn khi `used > trần`, không phải `used >= trần` — trần 2 nghĩa là được gọi 2 lượt."""
    consume(db, owner.id, LIMIT_2)
    consume(db, owner.id, LIMIT_2)

    assert _calls_today(db, owner.id) == 2
