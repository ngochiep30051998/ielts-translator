"""Bản port của `QuizMigrationIT`.

Canh hai thứ mà không test nào khác canh: **schema V5 khớp entity SQLAlchemy** (payload
JSONB ghi xuống rồi đọc lại vẫn nguyên hình), và **`find_reusable` lọc đúng bốn điều kiện**.

`find_reusable` là trái tim của cơ chế tiết kiệm quota: hỏng nó không làm gì đỏ, chỉ làm mỗi
lần mở màn quiz đốt thêm một lượt Gemini (bỏ lọt item cũ) hoặc trả lại câu vừa làm xong (bỏ
lọt điều kiện "chưa có lượt làm").

Đọc lại bằng SQL trần ở những chỗ cần chứng minh dữ liệu THẬT SỰ nằm dưới DB — identity map
của SQLAlchemy trả lại đúng object vừa tạo và làm phép so xanh giả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.quiz import repository
from app.quiz.models import QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import NguoiDungTest


def _tu_da_luu(db: Session, user_id: int) -> VocabEntry:
    """user_id là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ ngay lúc insert."""
    entry = VocabEntry(
        user_id=user_id,
        term="mitigate",
        lemma="mitigate",
        lang="en",
        pos="verb",
        meaning_vi="giảm nhẹ",
        collocations=[],
        examples=[],
    )
    db.add(entry)
    db.flush()
    return entry


def _item_da_luu(db: Session, entry: VocabEntry) -> QuizItem:
    item = QuizItem(
        vocab_entry_id=entry.id,
        type=QuizType.FILL_BLANK.value,
        payload={"sentence": "We must ___ the risk.", "answer": "mitigate"},
        prompt_version=1,
    )
    db.add(item)
    db.flush()
    return item


def _dem(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def test_v5_dung_duoc_bang_va_payload_jsonb_doc_lai_nguyen_ven(
    db: Session, owner: NguoiDungTest
) -> None:
    """V5 dựng được bảng và entity khớp schema — payload JSONB đọc lại nguyên vẹn.

    Đây là chốt "migration và entity không lệch nhau". Bên Java `ddl-auto: validate` bắt được
    lệch cột lúc khởi động; SQLAlchemy không có cơ chế đó, nên phép ghi/đọc thật ở đây là thứ
    duy nhất đứng thay.
    """
    item = _item_da_luu(db, _tu_da_luu(db, owner.id))

    db.add(
        QuizAttempt(
            quiz_item_id=item.id,
            user_answer="mitigate",
            correct=True,
            score=100,
            ai_feedback=None,
            improved_version=None,
        )
    )
    db.commit()

    # expire_all buộc SELECT lại từ DB thay vì trả object đang nằm trong identity map — không
    # có dòng này thì phép so dưới đây chỉ chứng minh Python nhớ được thứ Python vừa tạo.
    db.expire_all()
    doc_lai = db.get(QuizItem, item.id)
    assert doc_lai is not None
    assert doc_lai.payload["answer"] == "mitigate"
    assert doc_lai.payload["sentence"] == "We must ___ the risk."
    assert doc_lai.type == QuizType.FILL_BLANK.value
    assert _dem(db, QuizAttempt) == 1


def test_cot_improved_version_luu_va_doc_lai_duoc(db: Session, owner: NguoiDungTest) -> None:
    """Chỗ DUY NHẤT giữ câu Gemini viết lại.

    Cột này tách khỏi `ai_feedback` vì hợp đồng API trả hai trường khác nhau; nhét chung một
    cột rồi tách bằng chuỗi phân cách sẽ hỏng ở lần đầu Gemini trả đúng dấu phân cách đó.
    """
    item = _item_da_luu(db, _tu_da_luu(db, owner.id))

    attempt = QuizAttempt(
        quiz_item_id=item.id,
        user_answer="We must mitigate it.",
        correct=True,
        score=90,
        ai_feedback="Câu ổn.",
        improved_version="We must mitigate the risk effectively.",
    )
    db.add(attempt)
    db.commit()

    luu_duoi_db = db.execute(
        text("SELECT improved_version FROM quiz_attempt WHERE id = :i"), {"i": attempt.id}
    ).scalar_one()
    assert luu_duoi_db == "We must mitigate the risk effectively."


def test_xoa_tu_trong_so_cascade_sach_quiz_item_va_quiz_attempt(
    db: Session, owner: NguoiDungTest
) -> None:
    """Xoá một từ phải cuốn theo cả đề lẫn lịch sử làm bài của từ đó.

    Không có cascade thì `quiz_item` mồ côi vẫn nằm lại, và khoá ngoại sẽ chặn lệnh xoá —
    người dùng bấm xoá từ và nhận về 500.
    """
    entry = _tu_da_luu(db, owner.id)
    item = _item_da_luu(db, entry)
    db.add(
        QuizAttempt(quiz_item_id=item.id, user_answer="x", correct=False, score=0)
    )
    db.commit()

    db.execute(text("DELETE FROM vocab_entry WHERE id = :v"), {"v": entry.id})
    db.commit()

    assert _dem(db, QuizItem) == 0
    assert _dem(db, QuizAttempt) == 0


def test_find_reusable_bo_qua_item_da_lam_va_item_sai_prompt_version(
    db: Session, owner: NguoiDungTest
) -> None:
    """Ba item cùng từ, cùng loại: một dùng được, một đã có lượt làm, một sai prompt_version.
    Chỉ item đầu được trả về.

    Ba điều kiện hỏng theo ba kiểu riêng và đều IM LẶNG: bỏ "chưa có lượt làm" là câu vừa làm
    xong hiện lại ở đề sau; bỏ `prompt_version` là sửa prompt xong đề cũ vẫn sống mãi.
    """
    entry = _tu_da_luu(db, owner.id)

    dung_duoc = _item_da_luu(db, entry)

    da_lam = _item_da_luu(db, entry)
    db.add(
        QuizAttempt(quiz_item_id=da_lam.id, user_answer="x", correct=False, score=0)
    )

    cu = _item_da_luu(db, entry)
    cu.prompt_version = 99
    db.flush()
    db.commit()

    con_dung_duoc = repository.find_reusable(
        db, owner.id, [entry.id], [QuizType.FILL_BLANK], 1
    )

    assert [item.id for item in con_dung_duoc] == [dung_duoc.id]


def test_find_reusable_khong_tra_de_cua_nguoi_khac(
    db: Session, owner: NguoiDungTest, user_b: NguoiDungTest
) -> None:
    """Điều kiện thứ tư — chủ sở hữu.

    Bản Java không có test riêng cho nhánh này vì `MultiUserIsolationIT` phủ nó ở tầng HTTP.
    Đưa xuống đây vì `find_reusable` nhận `vocab_ids` do người gọi truyền vào: một người gọi
    tương lai quên lọc từ trước khi gọi sẽ không có lưới nào đỡ nếu chính câu truy vấn cũng
    không lọc (ràng buộc #13).
    """
    cua_b = _tu_da_luu(db, user_b.id)
    item_cua_b = _item_da_luu(db, cua_b)
    db.commit()

    # A hỏi thẳng bằng id từ của B — đúng hình dạng của lỗ IDOR.
    assert repository.find_reusable(db, owner.id, [cua_b.id], [QuizType.FILL_BLANK], 1) == []
    # Còn chính B thì vẫn thấy đề của mình: khẳng định trên không xanh vì câu truy vấn chết.
    assert [item.id for item in repository.find_reusable(
        db, user_b.id, [cua_b.id], [QuizType.FILL_BLANK], 1
    )] == [item_cua_b.id]
