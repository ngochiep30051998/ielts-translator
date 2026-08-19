"""Bản port của `AuthMigrationIT`.

Migration V6 đụng vào bảng chứa sổ từ THẬT của người dùng. Đây là test duy nhất chứng minh
dữ liệu cũ không bốc hơi và không đổi chủ.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import OWNER_EMAIL


def _has_constraint(db: Session, constraint_name: str) -> bool:
    n = db.execute(
        text("SELECT count(*) FROM pg_constraint WHERE conname = :t"), {"t": constraint_name}
    ).scalar_one()
    return int(n) > 0


def test_unique_constraint_is_now_per_user(db: Session) -> None:
    """`uq_vocab_term_pos` toàn cục nghĩa là hai người không cùng lưu được từ "mitigate"."""
    assert _has_constraint(db, "uq_vocab_term_pos") is False
    assert _has_constraint(db, "uq_vocab_user_term_pos") is True


def test_owner_account_is_created_from_bootstrap_email(db: Session) -> None:
    n = db.execute(
        text("SELECT count(*) FROM app_user WHERE email = :e"), {"e": OWNER_EMAIL}
    ).scalar_one()
    assert n == 1


def test_vocab_user_id_is_not_null(db: Session) -> None:
    """Không hàng nào vô chủ lọt qua."""
    nullable = db.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'vocab_entry' AND column_name = 'user_id'"
        )
    ).scalar_one()
    assert nullable == "NO"


def test_deleting_user_also_deletes_their_vocabulary(db: Session) -> None:
    """Không để lại hàng mồ côi."""
    user_id = db.execute(
        text(
            "INSERT INTO app_user (email, display_name) "
            "VALUES ('cascade@test.local', 'x') RETURNING id"
        )
    ).scalar_one()
    db.execute(
        text(
            "INSERT INTO vocab_entry (term, lang, pos, meaning_vi, user_id) "
            "VALUES ('cascadeword', 'en', 'noun', 'x', :uid)"
        ),
        {"uid": user_id},
    )
    db.commit()

    db.execute(text("DELETE FROM app_user WHERE id = :uid"), {"uid": user_id})
    db.commit()

    remaining = db.execute(
        text("SELECT count(*) FROM vocab_entry WHERE term = 'cascadeword'")
    ).scalar_one()
    assert remaining == 0


def test_lookup_cache_intentionally_has_no_user_id(db: Session) -> None:
    """Bất biến ngược chiều mọi test cách ly còn lại, nên phải viết ra: ai đó "sửa cho nhất
    quán" bằng cách thêm `user_id` vào đây là bỏ đi phần tiết kiệm quota Gemini lớn nhất của
    hệ thống (ràng buộc #14)."""
    n = db.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'lookup_cache' AND column_name = 'user_id'"
        )
    ).scalar_one()
    assert n == 0


def test_token_hash_is_varchar_not_bpchar(db: Session) -> None:
    """V7 đổi `CHAR(64)` thành `VARCHAR(64)`.

    `char(n)` trong Postgres mang ngữ nghĩa đệm khoảng trắng tới độ dài cố định. Hash
    SHA-256 hex luôn đúng 64 ký tự nên hôm nay chưa ai thấy hậu quả, nhưng để nguyên là để
    lại một cái bẫy trong schema.
    """
    column_type = db.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'user_session' AND column_name = 'token_hash'"
        )
    ).scalar_one()
    assert column_type == "character varying"


def test_every_learning_data_table_traces_back_to_one_owner(db: Session) -> None:
    """Chủ sở hữu gắn ở ĐÚNG MỘT chỗ — `vocab_entry.user_id`.

    Nhân cột `user_id` ra sáu bảng chỉ tạo cơ hội cho hai nguồn sự thật lệch nhau, mà lệch
    kiểu đó là dữ liệu người này lọt sang người kia, không có lỗi nào nổ ra.
    """
    tables_with_user_id = {
        row[0]
        for row in db.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE column_name = 'user_id' AND table_schema = 'public'"
            )
        )
    }
    assert tables_with_user_id == {"vocab_entry", "user_session", "gemini_usage"}
