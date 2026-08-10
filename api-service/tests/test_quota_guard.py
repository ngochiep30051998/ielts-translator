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
from tests.conftest import SECOND_EMAIL, NguoiDungTest, tao_nguoi_dung

#: `conftest` tắt hạn mức (0) cho mọi test khác; ở đây bật lên đúng 2 để test được cái trần.
TRAN_2 = Settings(AUTH_DAILY_GEMINI_CALLS=2)


def _so_luot(db: Session, user_id: int) -> int | None:
    return db.execute(
        text("SELECT calls FROM gemini_usage WHERE user_id = :u AND day = CURRENT_DATE"),
        {"u": user_id},
    ).scalar_one_or_none()


def test_vuot_han_muc_ngay_bi_tu_choi(db: Session, owner: NguoiDungTest) -> None:
    """GEMINI_QUOTA chứ không đẻ mã mới: UI đã biết hiển thị mã này, và với người dùng thì
    "hết lượt hôm nay" đúng là hết quota."""
    consume(db, owner.id, TRAN_2)
    consume(db, owner.id, TRAN_2)

    with pytest.raises(AppError) as ex:
        consume(db, owner.id, TRAN_2)

    assert ex.value.code is ErrorCode.GEMINI_QUOTA
    assert "2" in ex.value.message


def test_han_muc_tinh_rieng_tung_nguoi(db: Session, owner: NguoiDungTest) -> None:
    """A hết lượt không chặn B — một người làm 200 câu quiz không được phép khoá cả nhóm."""
    b = tao_nguoi_dung(db, SECOND_EMAIL)
    consume(db, owner.id, TRAN_2)
    consume(db, owner.id, TRAN_2)

    consume(db, b.id, TRAN_2)

    assert _so_luot(db, b.id) == 1


def test_bo_dem_tang_atomic_trong_mot_cau_lenh(db: Session, owner: NguoiDungTest) -> None:
    """Đọc-rồi-ghi ở tầng Python sẽ hỏng thật: hai request song song cùng đọc ra một số rồi
    cùng ghi đè, và hạn mức trở thành gợi ý."""
    consume(db, owner.id, TRAN_2)
    consume(db, owner.id, TRAN_2)

    assert _so_luot(db, owner.id) == 2


def test_han_muc_bang_khong_la_tat_han(db: Session, owner: NguoiDungTest) -> None:
    """0 hoặc âm = tắt hạn mức, dùng cho môi trường dev. Không được ghi cả dòng đếm."""
    tat = Settings(AUTH_DAILY_GEMINI_CALLS=0)
    for _ in range(50):
        consume(db, owner.id, tat)

    assert _so_luot(db, owner.id) is None


def test_lan_goi_dung_bang_tran_van_qua(db: Session, owner: NguoiDungTest) -> None:
    """Chặn khi `used > trần`, không phải `used >= trần` — trần 2 nghĩa là được gọi 2 lượt."""
    consume(db, owner.id, TRAN_2)
    consume(db, owner.id, TRAN_2)

    assert _so_luot(db, owner.id) == 2
