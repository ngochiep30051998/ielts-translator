"""Bản port của `QuizSrsIsolationIT`.

Bất biến quan trọng nhất của Phase 3: **làm quiz KHÔNG được đụng vào lịch ôn SRS.**

Chụp ảnh trước/sau bằng SQL trần chứ không qua ORM — bộ nhớ phiên của ORM có thể trả lại
đúng object cũ và làm phép so xanh giả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.quiz import service as quiz_service
from app.quiz.models import GenerateQuizRequest, QuizType
from tests.conftest import GeminiGia, NguoiDungTest


def _seed(db: Session, user_id: int, term: str, repetitions: int, lapses: int) -> int:
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry "
                "(term, lemma, lang, pos, meaning_vi, user_id, collocations, examples) "
                "VALUES (:t, :t, 'en', 'verb', :m, :u, '[]'::jsonb, '[]'::jsonb) RETURNING id"
            ),
            {"t": term, "m": f"nghĩa của {term}", "u": user_id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses, "
            "                      ease_factor, interval_days) "
            "VALUES (:v, CURRENT_DATE + 3, 'REVIEW', :r, :l, 2.36, 7)"
        ),
        {"v": vocab_id, "r": repetitions, "l": lapses},
    )
    db.commit()
    return vocab_id


def _anh_srs(db: Session) -> list[tuple[Any, ...]]:
    db.expire_all()
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT id, vocab_entry_id, ease_factor, interval_days, repetitions, lapses, "
                "       due_date, state FROM srs_card ORDER BY id"
            )
        )
    ]


def _anh_review_log(db: Session) -> list[tuple[Any, ...]]:
    db.expire_all()
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT id, card_id, rating, prev_interval, new_interval "
                "FROM review_log ORDER BY id"
            )
        )
    ]


def _seed_review_log(db: Session, vocab_entry_id: int) -> None:
    """Gieo sẵn lịch sử ôn để phép so cuối bài có gì để so.

    Không có bước này thì `review_log` rỗng suốt bài và khẳng định "không đổi dòng nào" rút
    về `[] == []` — nó bắt được ca INSERT nhưng bỏ lọt hoàn toàn ca một hồi quy tương lai
    SỬA hoặc XOÁ dòng có sẵn (ví dụ ai đó thêm "làm quiz đúng thì hạ lapses của lượt ôn gần
    nhất").
    """
    card_id = db.execute(
        text("SELECT id FROM srs_card WHERE vocab_entry_id = :v"), {"v": vocab_entry_id}
    ).scalar_one()
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
            "VALUES (:c, 'GOOD', 0, 1), (:c, 'HARD', 1, 2)"
        ),
        {"c": card_id},
    )
    db.commit()


_FILL_BLANK = {
    "items": [
        {
            "term": "mitigate",
            "sentence": "They must ___ it.",
            "answer": "mitigate",
            "hint": "gợi ý",
        },
        {
            "term": "resilient",
            "sentence": "She is ___ enough.",
            "answer": "resilient",
            "hint": "gợi ý",
        },
    ]
}

_COLLOCATION = {
    "items": [
        {
            "term": "mitigate",
            "question": "Cụm nào tự nhiên?",
            "options": ["mitigate risk", "mitigate cake", "mitigate blue", "mitigate loud"],
            "correct_index": 0,
        },
        {
            "term": "resilient",
            "question": "Cụm nào tự nhiên?",
            "options": [
                "resilient economy",
                "resilient cake",
                "resilient blue",
                "resilient loud",
            ],
            "correct_index": 0,
        },
    ]
}

_CHAM_FREE_WRITE = {
    "meaning_ok": True,
    "grammar_ok": False,
    "band_ok": False,
    "score": 55,
    "feedback_vi": "Ngữ pháp còn lỗi.",
    "improved_version": "Better.",
}


def _lam_het_mot_de(
    db: Session, gemini: GeminiGia, user_id: int, loai: QuizType
) -> int:
    """Sinh đề một loại rồi nộp hết, cả câu đúng lẫn câu sai. Trả về số câu đã nộp."""
    if loai is QuizType.FILL_BLANK:
        gemini.tra_json(_FILL_BLANK)
    elif loai is QuizType.COLLOCATION_CHOICE:
        gemini.tra_json(_COLLOCATION)

    de = quiz_service.generate(
        db, user_id, GenerateQuizRequest(count=10, type=loai)
    )
    assert de, f"{loai} phải sinh được đề"

    if loai is QuizType.FREE_WRITE:
        # Mỗi câu FREE_WRITE là một lượt chấm riêng bằng Gemini.
        gemini.tra_json(_CHAM_FREE_WRITE, lap=len(de))

    for i, item in enumerate(de):
        # Xen kẽ đúng/sai để chắc chắn cả hai nhánh chấm đều chạy.
        quiz_service.answer(
            db, user_id, item.id, "0" if i % 2 == 0 else "câu trả lời bất kỳ"
        )
    return len(de)


def test_lam_quiz_khong_bao_gio_dung_vao_srs(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Làm hết một đề cả ba loại xong, `srs_card` và `review_log` không đổi một dòng nào."""
    vocab_dau = _seed(db, owner.id, "mitigate", 3, 1)
    _seed(db, owner.id, "resilient", 5, 0)
    _seed_review_log(db, vocab_dau)

    truoc_srs = _anh_srs(db)
    truoc_log = _anh_review_log(db)
    assert len(truoc_srs) == 2
    # Chốt chống phép so rỗng: có dòng thật thì so snapshot mới có nghĩa.
    assert len(truoc_log) == 2

    da_nop = 0
    da_nop += _lam_het_mot_de(db, gemini, owner.id, QuizType.FILL_BLANK)
    da_nop += _lam_het_mot_de(db, gemini, owner.id, QuizType.COLLOCATION_CHOICE)
    da_nop += _lam_het_mot_de(db, gemini, owner.id, QuizType.FREE_WRITE)

    # Không có điểm này thì test xanh cả khi code chết: "không đổi gì" là hiển nhiên khi
    # chẳng có gì chạy.
    assert da_nop > 0
    so_luot = db.execute(text("SELECT count(*) FROM quiz_attempt")).scalar_one()
    assert so_luot == da_nop

    assert _anh_srs(db) == truoc_srs
    # So snapshot từng cột, không so count(*): count bắt được INSERT/DELETE nhưng không bắt
    # được UPDATE một dòng có sẵn.
    assert _anh_review_log(db) == truoc_log


def test_module_quiz_chi_doc_srs_qua_dung_mot_cua(db: Session) -> None:
    """ACL: `app.quiz` không được import gì từ `app.srs` ngoài `candidates.py`, và file đó
    chỉ được đọc.

    Bên Java, bất biến này chỉ tồn tại trong lời hứa của người viết. Ở đây nó là một phép
    thử chạy được — cùng tinh thần với chính `QuizSrsIsolationIT`.
    """
    import ast
    from pathlib import Path

    quiz_dir = Path(__file__).resolve().parent.parent / "app" / "quiz"
    vi_pham: list[str] = []
    for path in sorted(quiz_dir.glob("*.py")):
        cay = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(cay):
            ten: list[str] = []
            if isinstance(node, ast.Import):
                ten = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                ten = [node.module]
            for t in ten:
                if t.startswith("app.srs") and path.name != "candidates.py":
                    vi_pham.append(f"{path.name} import {t}")

    assert vi_pham == [], (
        "quiz đọc dữ liệu SRS qua ĐÚNG một chỗ là candidates.py và không bao giờ ghi. "
        f"Vi phạm: {vi_pham}"
    )

    nguon = (quiz_dir / "candidates.py").read_text(encoding="utf-8").upper()
    for tu_cam in ("INSERT ", "UPDATE ", "DELETE "):
        assert tu_cam not in nguon, f"candidates.py chỉ được SELECT, thấy {tu_cam.strip()}"
