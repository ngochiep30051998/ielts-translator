"""Bản port của `QuizGeneratorIT`.

Trọng tâm là hai bất biến tiết kiệm quota, cả hai đều hỏng im lặng:

* **một lô = một call** — 10 từ FILL_BLANK tốn đúng một lượt gọi Gemini, không phải mười;
* **tái dùng trước, sinh sau** — `find_reusable` + `prompt_version` là cặp quyết định đề cũ
  còn sống hay đã hết hiệu lực.

Ở đây `GeminiGia` mạnh hơn `@MockitoBean` một bậc: gọi Gemini nhiều hơn số phản hồi đã xếp
sẵn thì ném AssertionError ngay tại điểm gọi, nên "cache không ăn" không thể trốn qua được
một khẳng định `times(1)` bị quên.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.common.errors import AppError, ErrorCode
from app.quiz import generator
from app.quiz.models import QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import GeminiGia, NguoiDungTest


def _luu_tu(db: Session, user_id: int, n: int) -> list[int]:
    """n từ w0..w(n-1), mỗi từ mang sẵn nghĩa tiếng Việt để FREE_WRITE có gì mà dựng đề."""
    ids: list[int] = []
    for i in range(n):
        entry = VocabEntry(
            user_id=user_id,
            term=f"w{i}",
            lemma=f"w{i}",
            lang="en",
            pos="verb",
            meaning_vi=f"nghĩa của w{i}",
            collocations=[],
            examples=[],
        )
        db.add(entry)
        db.flush()
        ids.append(entry.id)
    return ids


def _lo_fill_blank(n: int) -> dict[str, Any]:
    """Lô fill-blank HỢP LỆ cho n từ: câu có `___`, đáp án không lộ trong câu lẫn trong gợi ý."""
    return {
        "items": [
            {
                "term": f"w{i}",
                "sentence": "They must ___ the risk.",
                "answer": f"w{i}",
                "hint": f"gợi ý {i}",
            }
            for i in range(n)
        ]
    }


def _dem(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def _ids(built: list[tuple[QuizItem, VocabEntry]]) -> list[int]:
    return [item.id for item, _ in built]


def test_mot_lo_sau_tu_ton_dung_mot_call_gemini(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Sáu từ FILL_BLANK tốn ĐÚNG MỘT call, không phải sáu.

    Đây là lý do tồn tại của `build_items` theo lô. Sinh từng từ một vẫn ra kết quả đúng, chỉ
    đắt gấp sáu lần và chậm gấp sáu lần — không có gì đỏ, hoá đơn Gemini mới là chỗ báo.
    """
    ids = _luu_tu(db, owner.id, 6)
    gemini.tra_json(_lo_fill_blank(6))

    built = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)

    assert len(built) == 6
    assert gemini.so_lan_goi == 1


def test_free_write_khong_ton_call_gemini_nao_luc_sinh_de(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Đề FREE_WRITE dựng thẳng từ sổ từ — không có gì để hỏi Gemini lúc sinh đề.

    Câu hỏi phải mang cả `term` lẫn nghĩa tiếng Việt: thiếu nghĩa thì người học không biết
    đang được yêu cầu dùng từ theo nghĩa nào.
    """
    ids = _luu_tu(db, owner.id, 3)

    built = generator.build_items(db, owner.id, ids, QuizType.FREE_WRITE)

    assert len(built) == 3
    cau_hoi = built[0][0].payload["question"]
    assert "w0" in cau_hoi
    assert "nghĩa của w0" in cau_hoi
    assert gemini.requests == []


def test_lan_sinh_thu_hai_tai_dung_item_chua_lam(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Sinh đề hai lần liên tiếp: lần hai trả về CÙNG id item và không gọi Gemini thêm.

    Chỉ xếp sẵn MỘT phản hồi: lượt gọi thứ hai (nếu có) sẽ nổ AssertionError trong
    `GeminiGia` kèm URL, nên test này không thể xanh giả.
    """
    ids = _luu_tu(db, owner.id, 3)
    gemini.tra_json(_lo_fill_blank(3))

    lan_dau = _ids(generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK))
    lan_hai = _ids(generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK))

    assert lan_hai == lan_dau
    assert gemini.so_lan_goi == 1
    # Và không đẻ thêm bản ghi nào: tái dùng nghĩa là dùng lại, không phải sinh bản sao.
    assert _dem(db, QuizItem) == 3


def test_item_da_co_luot_lam_thi_khong_tai_dung(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Câu đã làm rồi phải được thay bằng câu mới.

    Bỏ điều kiện này là người học mở lại màn quiz và gặp đúng câu vừa trả lời xong — ôn tập
    biến thành đọc lại đáp án vừa nhớ.
    """
    ids = _luu_tu(db, owner.id, 1)
    gemini.tra_json(_lo_fill_blank(1), lap=2)

    dau_tien = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]
    db.add(
        QuizAttempt(
            quiz_item_id=dau_tien.id, user_answer="w0", correct=True, score=100
        )
    )
    db.flush()

    thu_hai = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert thu_hai.id != dau_tien.id
    assert gemini.so_lan_goi == 2


def test_item_sinh_bang_prompt_version_cu_thi_bo_va_sinh_lai(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Đổi `prompt_version` của item cũ thì lần sinh sau phải gọi Gemini lại.

    Đây là NỬA CÒN LẠI của cơ chế tái dùng: sửa nội dung một file prompt rồi tăng `version:`
    ở đầu file là cách DUY NHẤT làm đề cũ hết hiệu lực (ràng buộc #5). Quên tăng version thì
    người dùng nhận đề sinh bằng prompt cũ mãi mãi và không có gì đỏ — nên item mới phải mang
    đúng version đang hiệu lực, không chỉ "khác id".
    """
    ids = _luu_tu(db, owner.id, 1)
    gemini.tra_json(_lo_fill_blank(1), lap=2)

    dau_tien = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]
    db.execute(
        text("UPDATE quiz_item SET prompt_version = 99 WHERE id = :i"), {"i": dau_tien.id}
    )

    thu_hai = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert thu_hai.id != dau_tien.id
    assert thu_hai.prompt_version == generator.prompt_version_for(QuizType.FILL_BLANK)
    assert gemini.so_lan_goi == 2


def test_lo_co_item_hong_thi_loai_dung_item_do(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Câu giữa thiếu `___` → bỏ đúng câu đó, hai câu còn lại vẫn dùng được.

    Khác bộ kiểm mồi nhử của srs một cách CÓ CHỦ Ý (bên đó loại cả lô): người dùng đang đứng
    chờ, bắt họ đợi thêm một lượt Gemini chỉ vì một câu hỏng là đắt vô lý.
    """
    ids = _luu_tu(db, owner.id, 3)
    gemini.tra_json(
        {
            "items": [
                {"term": "w0", "sentence": "We must ___ it.", "answer": "w0", "hint": "x"},
                {"term": "w1", "sentence": "No blank here.", "answer": "w1", "hint": "x"},
                {"term": "w2", "sentence": "They ___ risk.", "answer": "w2", "hint": "x"},
            ]
        }
    )

    built = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)

    assert len(built) == 2
    # Câu hỏng KHÔNG được lưu xuống DB: lưu rồi thì nó lọt `find_reusable` ở lượt sau.
    assert _dem(db, QuizItem) == 2


def test_ca_lo_hong_het_thi_nem_parse_error(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Không dựng nổi câu nào thì ném PARSE_ERROR, KHÔNG trả mảng rỗng.

    Mảng rỗng ở đây là nói dối: nó trùng hình dạng với "sổ chưa có từ nào đủ điều kiện" — một
    trạng thái bình thường — nên UI sẽ báo "chưa có gì để ôn" trong khi Gemini đang trả rác.
    """
    ids = _luu_tu(db, owner.id, 2)
    gemini.tra_json(
        {
            "items": [
                {"term": "w0", "sentence": "No blank.", "answer": "w0", "hint": "x"},
                {"term": "w1", "sentence": "Also no blank.", "answer": "w1", "hint": "x"},
            ]
        }
    )

    with pytest.raises(AppError) as loi:
        generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)
    assert loi.value.code is ErrorCode.PARSE_ERROR


def test_payload_fill_blank_giu_dap_an_va_goi_y(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Đáp án nằm trong `payload`, không nằm trong DTO — đó là chỗ duy nhất giữ nó để chấm
    bài sau này."""
    ids = _luu_tu(db, owner.id, 1)
    gemini.tra_json(_lo_fill_blank(1))

    item = generator.build_items(db, owner.id, ids, QuizType.FILL_BLANK)[0][0]

    assert item.payload["answer"] == "w0"
    assert "sentence" in item.payload
    assert "hint" in item.payload


def test_xao_options_nhung_correct_index_van_tro_dung_dap_an(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Xáo xong thì `correct_index` phải đi theo đáp án, không đứng yên.

    Xáo mà quên dời index là chấm sai TOÀN BỘ câu trắc nghiệm mà không lỗi nào nổ ra: người
    học chọn đúng vẫn bị báo sai.
    """
    ids = _luu_tu(db, owner.id, 1)
    gemini.tra_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["đúng", "sai 1", "sai 2", "sai 3"],
                    "correct_index": 0,
                }
            ]
        }
    )

    item = generator.build_items(db, owner.id, ids, QuizType.COLLOCATION_CHOICE)[0][0]

    options = item.payload["options"]
    correct_index = item.payload["correct_index"]
    assert sorted(options) == sorted(["đúng", "sai 1", "sai 2", "sai 3"])
    assert options[correct_index] == "đúng"


def test_xao_that_su_co_xay_ra(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """40 lần sinh không thể lần nào đáp án cũng rơi vào vị trí 0.

    Gemini có xu hướng đặt đáp án đúng ở vị trí đầu; không xáo thì quiz đoán được mà không
    cần biết từ. Xác suất dương tính giả (xáo thật mà 40 lần đều ra cùng một vị trí) là
    (1/4)^39 — coi như không xảy ra.
    """
    ids = _luu_tu(db, owner.id, 1)
    gemini.tra_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["đúng", "sai 1", "sai 2", "sai 3"],
                    "correct_index": 0,
                }
            ]
        },
        lap=40,
    )

    vi_tri: list[int] = []
    for _ in range(40):
        # Xoá item cũ để lượt sau không rơi vào đường tái dùng.
        db.execute(text("DELETE FROM quiz_item"))
        item = generator.build_items(db, owner.id, ids, QuizType.COLLOCATION_CHOICE)[0][0]
        vi_tri.append(item.payload["correct_index"])

    assert len(set(vi_tri)) > 1, (
        "40 lần sinh mà đáp án luôn ở cùng một vị trí nghĩa là không hề xáo"
    )
