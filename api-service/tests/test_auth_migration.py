"""Bản port của `AuthMigrationIT`.

Migration V6 đụng vào bảng chứa sổ từ THẬT của người dùng. Đây là test duy nhất chứng minh
dữ liệu cũ không bốc hơi và không đổi chủ.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import OWNER_EMAIL


def _co_rang_buoc(db: Session, ten: str) -> bool:
    n = db.execute(
        text("SELECT count(*) FROM pg_constraint WHERE conname = :t"), {"t": ten}
    ).scalar_one()
    return int(n) > 0


def test_rang_buoc_unique_gio_theo_tung_user(db: Session) -> None:
    """`uq_vocab_term_pos` toàn cục nghĩa là hai người không cùng lưu được từ "mitigate"."""
    assert _co_rang_buoc(db, "uq_vocab_term_pos") is False
    assert _co_rang_buoc(db, "uq_vocab_user_term_pos") is True


def test_tai_khoan_goc_duoc_tao_tu_bootstrap_email(db: Session) -> None:
    n = db.execute(
        text("SELECT count(*) FROM app_user WHERE email = :e"), {"e": OWNER_EMAIL}
    ).scalar_one()
    assert n == 1


def test_vocab_user_id_la_not_null(db: Session) -> None:
    """Không hàng nào vô chủ lọt qua."""
    nullable = db.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'vocab_entry' AND column_name = 'user_id'"
        )
    ).scalar_one()
    assert nullable == "NO"


def test_xoa_user_thi_so_tu_di_theo(db: Session) -> None:
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

    con_lai = db.execute(
        text("SELECT count(*) FROM vocab_entry WHERE term = 'cascadeword'")
    ).scalar_one()
    assert con_lai == 0


def test_lookup_cache_co_y_khong_co_user_id(db: Session) -> None:
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


def test_token_hash_la_varchar_chu_khong_phai_bpchar(db: Session) -> None:
    """V7 đổi `CHAR(64)` thành `VARCHAR(64)`.

    `char(n)` trong Postgres mang ngữ nghĩa đệm khoảng trắng tới độ dài cố định. Hash
    SHA-256 hex luôn đúng 64 ký tự nên hôm nay chưa ai thấy hậu quả, nhưng để nguyên là để
    lại một cái bẫy trong schema.
    """
    kieu = db.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'user_session' AND column_name = 'token_hash'"
        )
    ).scalar_one()
    assert kieu == "character varying"


def test_moi_bang_du_lieu_hoc_deu_truy_duoc_ve_mot_chu_so_huu(db: Session) -> None:
    """Chủ sở hữu gắn ở ĐÚNG MỘT chỗ — `vocab_entry.user_id`.

    Nhân cột `user_id` ra sáu bảng chỉ tạo cơ hội cho hai nguồn sự thật lệch nhau, mà lệch
    kiểu đó là dữ liệu người này lọt sang người kia, không có lỗi nào nổ ra.
    """
    co_user_id = {
        row[0]
        for row in db.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE column_name = 'user_id' AND table_schema = 'public'"
            )
        )
    }
    assert co_user_id == {"vocab_entry", "user_session", "gemini_usage"}
