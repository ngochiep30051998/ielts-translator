"""Bản port của `SrsMigrationIT` + `SrsDistractorMigrationIT` gộp lại.

Hai file Java tách nhau vì V3 và V4 là hai migration; ở đây gộp vì cùng một loại khẳng
định — schema thật có đúng ràng buộc mình tưởng nó có.

Dùng SQL trần chứ không qua ORM: thứ đang được kiểm là DDL do `migrations/V*.sql` dựng,
không phải cách ORM ánh xạ nó.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.srs import repository as repo
from tests.conftest import NguoiDungTest


def _tu(db: Session, user_id: int, term: str, pos: str = "verb") -> int:
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry "
                "(term, lemma, lang, pos, meaning_vi, user_id, collocations, examples) "
                "VALUES (:t, :t, 'en', :p, :m, :u, '[]'::jsonb, '[]'::jsonb) RETURNING id"
            ),
            {"t": term, "p": pos, "m": f"nghĩa của {term}", "u": user_id},
        ).scalar_one()
    )
    db.commit()
    return vocab_id


def _the(db: Session, vocab_id: int) -> int:
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state) "
                "VALUES (:v, CURRENT_DATE, 'NEW') RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    db.commit()
    return card_id


def _dem(db: Session, sql: str) -> int:
    return int(db.execute(text(sql)).scalar_one())


def test_xoa_tu_thi_the_va_lich_su_review_bien_mat_theo(
    db: Session, owner: NguoiDungTest
) -> None:
    """ON DELETE CASCADE — không để lại hàng mồ côi."""
    vocab_id = _tu(db, owner.id, "mitigate")
    card_id = _the(db, vocab_id)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 0, 1)"
        ),
        {"c": card_id},
    )
    db.commit()

    db.execute(text("DELETE FROM vocab_entry WHERE id = :v"), {"v": vocab_id})
    db.commit()

    assert _dem(db, "SELECT count(*) FROM srs_card") == 0
    assert _dem(db, "SELECT count(*) FROM review_log") == 0


def test_mot_tu_chi_duoc_co_dung_mot_the(db: Session, owner: NguoiDungTest) -> None:
    """Ràng buộc UNIQUE ở tầng schema, không phải ở tầng service.

    Ở tầng service thì hai request song song vẫn chèn được hai thẻ cho cùng một từ; UNIQUE
    trên `vocab_entry_id` là thứ duy nhất chặn thật.
    """
    import psycopg
    import pytest

    vocab_id = _tu(db, owner.id, "resilient", "adjective")
    _the(db, vocab_id)

    with pytest.raises(Exception) as ex:
        _the(db, vocab_id)
    assert isinstance(ex.value.orig, psycopg.errors.UniqueViolation)  # type: ignore[attr-defined]
    db.rollback()

    assert _dem(db, f"SELECT count(*) FROM srs_card WHERE vocab_entry_id = {vocab_id}") == 1


def test_cau_lenh_backfill_bo_qua_pos_phrase(db: Session, owner: NguoiDungTest) -> None:
    """V3 backfill chỉ tạo thẻ cho từ đơn — câu (`pos = 'phrase'`) không làm flashcard được.

    Migration chạy lúc `vocab_entry` còn rỗng, nên chạy lại ĐÚNG câu lệnh của V3 trên dữ
    liệu vừa gieo là cách duy nhất kiểm chứng chính logic lọc đó.
    """
    _tu(db, owner.id, "mitigate", "verb")
    _tu(db, owner.id, "resilient", "adjective")
    _tu(db, owner.id, "Governments must act now.", "phrase")

    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state) "
            "SELECT id, CURRENT_DATE, 'NEW' FROM vocab_entry WHERE pos <> 'phrase'"
        )
    )
    db.commit()

    assert _dem(db, "SELECT count(*) FROM srs_card") == 2
    assert (
        _dem(
            db,
            "SELECT count(*) FROM srs_card c JOIN vocab_entry v ON v.id = c.vocab_entry_id "
            "WHERE v.pos = 'phrase'",
        )
        == 0
    )


def test_chi_dem_luot_review_dau_doi_cua_the(db: Session, owner: NguoiDungTest) -> None:
    """`prev_interval = 0` nhận diện chính xác lượt đầu đời của một thẻ.

    Đây là thứ hạn mức "từ mới mỗi ngày" dựa vào. Đếm cả lượt sau là hạn mức bị tiêu hết bởi
    những thẻ vốn đã học từ tuần trước.
    """
    card_id = _the(db, _tu(db, owner.id, "substantial", "adjective"))
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 0, 1), (:c, 'GOOD', 1, 6)"
        ),
        {"c": card_id},
    )
    db.commit()

    assert repo.count_introduced_since(db, owner.id, datetime(1970, 1, 1, tzinfo=UTC)) == 1


def test_moi_nhu_luu_va_doc_lai_duoc_hai_mang_jsonb(
    db: Session, owner: NguoiDungTest
) -> None:
    vocab_id = _tu(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO srs_distractor (vocab_entry_id, vi_options, en_options, prompt_version) "
            "VALUES (:v, :vi, :en, 1)"
        ),
        {
            "v": vocab_id,
            "vi": '["làm trầm trọng thêm", "phóng đại", "trì hoãn"]',
            "en": '["aggravate", "exaggerate", "postpone"]',
        },
    )
    db.commit()

    hang = db.execute(
        text("SELECT vi_options, en_options, prompt_version FROM srs_distractor")
    ).one()
    assert hang[0] == ["làm trầm trọng thêm", "phóng đại", "trì hoãn"]
    assert hang[1] == ["aggravate", "exaggerate", "postpone"]
    assert hang[2] == 1


def test_moi_nhu_cascade_khi_xoa_tu(db: Session, owner: NguoiDungTest) -> None:
    vocab_id = _tu(db, owner.id, "scrutinise")
    db.execute(
        text(
            "INSERT INTO srs_distractor (vocab_entry_id, vi_options, en_options, prompt_version) "
            "VALUES (:v, '[\"a\"]'::jsonb, '[\"x\"]'::jsonb, 1)"
        ),
        {"v": vocab_id},
    )
    db.commit()

    db.execute(text("DELETE FROM vocab_entry WHERE id = :v"), {"v": vocab_id})
    db.commit()

    assert _dem(db, "SELECT count(*) FROM srs_distractor") == 0


def test_moi_tu_chi_co_mot_bo_moi_nhu(db: Session, owner: NguoiDungTest) -> None:
    """UNIQUE trên `vocab_entry_id` là thứ làm việc ghi đè bộ mồi nhử trở thành idempotent —
    hai instance serverless cùng sinh một lúc không đẻ ra hai hàng."""
    thong_tin = db.execute(
        text(
            "SELECT count(*) FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = 'srs_distractor' AND c.contype = 'u'"
        )
    ).scalar_one()
    assert thong_tin >= 1


def test_v8_them_cot_mode_va_backfill_dong_cu(db: Session, owner: NguoiDungTest) -> None:
    """`DEFAULT 'SCHEDULED'` không phải cho tiện: mọi dòng `review_log` đang có ĐỀU đúng là
    lượt ôn theo lịch, nên default đó backfill chính xác toàn bộ lịch sử mà không cần câu
    `UPDATE` nào. Sai chỗ này là thống kê cũ đổi số."""
    kieu, mac_dinh, cho_null = db.execute(
        text(
            "SELECT data_type, column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'review_log' AND column_name = 'mode'"
        )
    ).one()

    assert kieu == "character varying"
    assert "SCHEDULED" in mac_dinh
    assert cho_null == "NO"


def test_v8_dong_review_log_khong_ghi_mode_nhan_scheduled(
    db: Session, owner: NguoiDungTest
) -> None:
    """Chèn thẳng bằng SQL không nêu `mode` — mô phỏng đúng dòng có từ trước V8."""
    vocab_id = _tu(db, owner.id, "mitigate")
    card_id = _the(db, vocab_id)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 1, 6)"
        ),
        {"c": card_id},
    )
    db.commit()

    mode = db.execute(
        text("SELECT mode FROM review_log WHERE card_id = :c"), {"c": card_id}
    ).scalar_one()
    assert mode == "SCHEDULED"
