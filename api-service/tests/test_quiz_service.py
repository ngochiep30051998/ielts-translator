"""Bản port của `QuizServiceIT`.

Ba nhóm khẳng định, đúng theo bản Java:

1. **chọn ứng viên** — ai được đưa vào đề và theo thứ tự nào;
2. **đếm call Gemini** — tái dùng có ăn không, `prompt_version` có làm cũ đi không, FREE_WRITE
   có thật sự miễn phí lúc sinh đề không;
3. **chấm bài** — ranh giới giữa "trả lời sai" (200) và "lỗi" (4xx/5xx).

Chỗ khác bản Java: Mockito đếm được `eq(GeminiTimeout.QUIZ_GENERATE)` vì nó chặn ở chữ ký
hàm, còn `GeminiGia` chặn ở tầng HTTP nên không thấy mức timeout. Fixture `muc_timeout` dưới
đây bù lại đúng phần đó — mức timeout sai không làm gì đỏ, chỉ làm một lượt sinh đề đứt giữa
chừng trên máy người dùng khi Gemini chậm thật.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.common.errors import AppError, ErrorCode
from app.common.gemini import GeminiTimeout
from app.quiz import service
from app.quiz.models import GenerateQuizRequest, QuizAttempt, QuizItem, QuizType
from app.vocabulary.models import VocabEntry
from tests.conftest import GeminiGia, NguoiDungTest


@pytest.fixture
def muc_timeout(
    monkeypatch: pytest.MonkeyPatch, gemini: GeminiGia
) -> Iterator[list[GeminiTimeout]]:
    """Ghi lại MỨC TIMEOUT của từng lượt gọi Gemini, theo đúng thứ tự gọi.

    Bọc `generate_json` chứ không thay thế nó: toàn bộ đường đi thật (dựng body, đọc
    candidate, map status code) vẫn chạy qua `GeminiGia` như mọi test khác.
    """
    from app.common.gemini import GeminiClient

    da_goi: list[GeminiTimeout] = []
    goc = GeminiClient.generate_json

    def _ghi(
        self: GeminiClient, prompt: str, response_schema: dict[str, Any], tier: GeminiTimeout
    ) -> Any:
        da_goi.append(tier)
        return goc(self, prompt, response_schema, tier)

    monkeypatch.setattr(GeminiClient, "generate_json", _ghi)
    yield da_goi


def _luu_tu(db: Session, user_id: int, term: str) -> int:
    entry = VocabEntry(
        user_id=user_id,
        term=term,
        lemma=term,
        lang="en",
        pos="verb",
        meaning_vi=f"nghĩa của {term}",
        collocations=[],
        examples=[],
    )
    db.add(entry)
    db.flush()
    return entry.id


def _the(db: Session, vocab_id: int, repetitions: int, lapses: int) -> None:
    """Thẻ SRS của một từ. `repetitions >= 1` là điều kiện lọt vào danh sách ứng viên."""
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', :r, :l)"
        ),
        {"v": vocab_id, "r": repetitions, "l": lapses},
    )
    db.flush()


def _lo_fill_blank(*terms: str) -> dict[str, Any]:
    return {
        "items": [
            {
                "term": term,
                "sentence": "They must ___ the risk.",
                "answer": term,
                "hint": "gợi ý",
            }
            for term in terms
        ]
    }


def _cham_free_write(
    meaning_ok: bool, grammar_ok: bool, band_ok: bool, score: int
) -> dict[str, Any]:
    return {
        "meaning_ok": meaning_ok,
        "grammar_ok": grammar_ok,
        "band_ok": band_ok,
        "score": score,
        "feedback_vi": "Nhận xét tiếng Việt.",
        "improved_version": "A better sentence.",
    }


def _theo_count(count: int, loai: QuizType) -> GenerateQuizRequest:
    return GenerateQuizRequest(count=count, type=loai)


def _dem(db: Session, model: Any) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


# ── chọn ứng viên ─────────────────────────────────────────────────────────────


def test_tu_chua_on_lan_nao_khong_bi_dua_vao_de(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """`repetitions = 0` nghĩa là người học chưa từng gặp lại từ đó — hỏi là phạt oan.

    Gemini vẫn được xếp sẵn câu cho CẢ HAI từ: nếu câu lọc hỏng thì từ "fresh" sẽ lọt vào đề
    một cách hoàn toàn im lặng, và khẳng định dưới đây là chỗ duy nhất bắt được.
    """
    da_on = _luu_tu(db, owner.id, "reviewed")
    _the(db, da_on, 2, 0)
    chua_on = _luu_tu(db, owner.id, "fresh")
    _the(db, chua_on, 0, 0)
    gemini.tra_json(_lo_fill_blank("reviewed", "fresh"))

    de = service.generate(db, owner.id, _theo_count(10, QuizType.FILL_BLANK))

    assert [item.vocab_entry_id for item in de] == [da_on]


def test_uu_tien_tu_it_bi_hoi_nhat_roi_toi_tu_hay_quen_nhat(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Cùng số lượt bị hỏi thì từ hay quên (lapses cao) đứng trước.

    So THỨ TỰ chứ không so tập hợp: mất `ORDER BY c.lapses DESC` vẫn ra đúng hai từ đó, chỉ
    là người học được ôn thứ mình đã nhớ trước thứ mình hay quên.
    """
    it_quen = _luu_tu(db, owner.id, "low")
    _the(db, it_quen, 3, 0)
    hay_quen = _luu_tu(db, owner.id, "high")
    _the(db, hay_quen, 3, 9)
    gemini.tra_json(_lo_fill_blank("high", "low"))

    de = service.generate(db, owner.id, _theo_count(10, QuizType.FILL_BLANK))

    assert [item.vocab_entry_id for item in de] == [hay_quen, it_quen]


def test_so_chi_co_tu_chua_on_thi_tra_mang_rong_va_khong_goi_gemini(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """"Chưa ôn từ nào đủ điều kiện" là trạng thái BÌNH THƯỜNG, không phải lỗi.

    Ném ở đây sẽ buộc phải đẻ thêm một ErrorCode cho một tình huống hoàn toàn bình thường, và
    UI phải học cách phân biệt nó với lỗi thật.
    """
    _the(db, _luu_tu(db, owner.id, "fresh"), 0, 0)

    assert service.generate(db, owner.id, _theo_count(10, QuizType.FILL_BLANK)) == []
    assert gemini.requests == []


def test_so_rong_thi_tra_mang_rong_khong_nem(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Người dùng mới tinh mở màn quiz — không được nhận lỗi."""
    assert service.generate(db, owner.id, _theo_count(10, QuizType.FILL_BLANK)) == []
    assert gemini.requests == []


def test_vocab_ids_chi_dinh_thang_thi_bo_qua_dieu_kien_repetitions(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Người dùng tự chọn từ thì họ đã quyết định muốn ôn từ đó — điều kiện `repetitions >= 1`
    chỉ áp cho đường chọn TỰ ĐỘNG theo `count`."""
    chua_on = _luu_tu(db, owner.id, "fresh")
    _the(db, chua_on, 0, 0)
    gemini.tra_json(_lo_fill_blank("fresh"))

    de = service.generate(
        db, owner.id, GenerateQuizRequest(vocab_ids=[chua_on], type=QuizType.FILL_BLANK)
    )

    assert len(de) == 1


def test_vocab_ids_toan_id_khong_ton_tai_thi_mang_rong_va_khong_goi_gemini(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Id lạ bị bỏ qua chứ không thành lỗi — và không được đốt một lượt Gemini nào cho một
    request chẳng có từ nào để hỏi."""
    de = service.generate(
        db, owner.id, GenerateQuizRequest(vocab_ids=[999_999], type=QuizType.FILL_BLANK)
    )

    assert de == []
    assert gemini.requests == []


def test_count_lon_hon_so_ung_vien_thi_tra_dung_so_ung_vien(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """[Q1] Xin 10 câu mà chỉ có 4 từ đủ điều kiện → đúng 4 câu, không đệm thêm.

    "Đệm thêm" ở đây nghĩa là hạ điều kiện ứng viên xuống cho đủ số — tức là hỏi từ người học
    chưa từng ôn, đúng thứ mà điều kiện `repetitions >= 1` sinh ra để tránh.
    """
    for i in range(4):
        _the(db, _luu_tu(db, owner.id, f"w{i}"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0", "w1", "w2", "w3"))

    assert len(service.generate(db, owner.id, _theo_count(10, QuizType.FILL_BLANK))) == 4


def test_moi_tu_trong_lo_sinh_dung_mot_cau(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """3 từ ra 3 câu, không nhân bản."""
    for i in range(3):
        _the(db, _luu_tu(db, owner.id, f"w{i}"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0", "w1", "w2"))

    assert len(service.generate(db, owner.id, _theo_count(3, QuizType.FILL_BLANK))) == 3


# ── đếm call Gemini ───────────────────────────────────────────────────────────


def test_sinh_de_hai_lan_lien_tiep_thi_lan_hai_tai_dung(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest, muc_timeout: list[GeminiTimeout]
) -> None:
    """[R4] Lần hai trả về đúng những id cũ và tốn 0 call Gemini thêm.

    Đây là đường người dùng đi nhiều nhất — đóng rồi mở lại màn quiz. Mất cơ chế tái dùng thì
    mỗi lần mở là một lượt Gemini, không có gì đỏ, chỉ có hạn mức bốc hơi.
    """
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0"))

    lan_dau = service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))
    lan_hai = service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))

    assert [i.id for i in lan_hai] == [i.id for i in lan_dau]
    # Lọc theo mức QUIZ_GENERATE chứ không đếm tổng: mức khác là của luồng khác, đếm lẫn vào
    # đây là test đỏ ngẫu nhiên không tái hiện được.
    assert muc_timeout.count(GeminiTimeout.QUIZ_GENERATE) == 1


def test_doi_prompt_version_trong_db_thi_lan_sinh_sau_goi_gemini_lai(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest, muc_timeout: list[GeminiTimeout]
) -> None:
    """Đề sinh bằng prompt cũ phải hết hiệu lực.

    `prompt_version` nằm trong điều kiện của `find_reusable` — đó là cách DUY NHẤT làm đề cũ
    hết hiệu lực sau khi sửa nội dung prompt (ràng buộc #5).
    """
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0"), lap=2)

    service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))
    db.execute(text("UPDATE quiz_item SET prompt_version = 99"))
    service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))

    assert muc_timeout.count(GeminiTimeout.QUIZ_GENERATE) == 2


def test_free_write_ton_khong_call_gemini_luc_sinh_de(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """[Q1] FREE_WRITE dựng đề từ chính sổ từ."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)

    assert len(service.generate(db, owner.id, _theo_count(5, QuizType.FREE_WRITE))) == 1
    assert gemini.requests == []


def test_ca_lo_hong_thi_nem_parse_error(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Câu Gemini trả về không có chỗ trống → không dựng nổi item nào → PARSE_ERROR."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(
        {
            "items": [
                {
                    "term": "w0",
                    "sentence": "Khong co cho trong.",
                    "answer": "w0",
                    "hint": "x",
                }
            ]
        }
    )

    with pytest.raises(AppError) as loi:
        service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))
    assert loi.value.code is ErrorCode.PARSE_ERROR


def test_de_da_sinh_van_nam_lai_db(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Không lưu thì không có gì để tái dùng ở lượt sau."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0"))

    service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))

    assert _dem(db, QuizItem) == 1


# ── chấm bài ──────────────────────────────────────────────────────────────────


def test_cham_cung_mot_item_hai_lan_ghi_hai_dong_lich_su(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """`quiz_attempt` là LỊCH SỬ, không phải trạng thái hiện tại.

    Ghi đè thay vì thêm dòng làm hỏng luôn tiêu chí xếp ưu tiên ứng viên — nó đếm số lượt làm
    của từng từ.
    """
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0"))
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))[0].id

    service.answer(db, owner.id, item_id, "w0")
    service.answer(db, owner.id, item_id, "sai rồi")

    assert _dem(db, QuizAttempt) == 2
    # So từng dòng, không chỉ đếm: hai lượt phải giữ nguyên câu trả lời KHÁC NHAU của chúng.
    dong = [
        tuple(r)
        for r in db.execute(
            text("SELECT user_answer, correct, score FROM quiz_attempt ORDER BY id")
        )
    ]
    assert dong == [("w0", True, 100), ("sai rồi", False, 0)]


def test_cham_free_write_dung_dung_muc_timeout_quiz_grade(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest, muc_timeout: list[GeminiTimeout]
) -> None:
    """Chấm một bài viết trả về nhiều token hơn hẳn một lượt dịch — dùng nhầm mức TRANSLATE
    (15 giây) là lượt chấm đứt giữa chừng trên máy người dùng, còn test thì vẫn xanh."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FREE_WRITE))[0].id
    gemini.tra_json(_cham_free_write(True, True, True, 80))

    service.answer(db, owner.id, item_id, "I will w0 the risk.")

    assert muc_timeout == [GeminiTimeout.QUIZ_GRADE]


def test_band_ok_false_khong_lam_cau_tra_loi_thanh_sai(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Nhãn band là gợi ý tham khảo, không phải sự thật — trượt band mà dùng từ đúng nghĩa,
    đúng ngữ pháp thì vẫn là đúng. Điểm vẫn giữ nguyên con số Gemini trả."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FREE_WRITE))[0].id
    gemini.tra_json(_cham_free_write(True, True, False, 70))

    ket_qua = service.answer(db, owner.id, item_id, "I will w0 the risk.")

    assert ket_qua.correct is True
    assert ket_qua.score == 70


def test_meaning_ok_false_thi_sai_du_ngu_phap_dung(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Dùng từ sai nghĩa là hỏng đúng thứ đang được luyện, dù câu viết trơn tru."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FREE_WRITE))[0].id
    gemini.tra_json(_cham_free_write(False, True, True, 30))

    assert service.answer(db, owner.id, item_id, "I ate a w0.").correct is False


def test_diem_gemini_tra_ngoai_khoang_0_100_bi_kep_lai(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Điểm 250 không được lọt ra API — hợp đồng nói 0..100 và panel vẽ thanh điểm theo đó."""
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FREE_WRITE))[0].id
    gemini.tra_json(_cham_free_write(True, True, True, 250))

    assert service.answer(db, owner.id, item_id, "I will w0 it.").score == 100


def test_answer_khong_parse_duoc_thanh_index_la_tra_loi_sai_khong_phai_loi(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Người dùng gõ bậy không phải sự cố hệ thống — ném ở đây biến nó thành HTTP 500.

    Feedback vẫn phải khác rỗng: đó là kênh DUY NHẤT người học biết đáp án, vì `QuizItemDto`
    cố ý không mang nó.
    """
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(
        {
            "items": [
                {
                    "term": "w0",
                    "question": "Cụm nào tự nhiên?",
                    "options": ["a", "b", "c", "d"],
                    "correct_index": 1,
                }
            ]
        }
    )
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.COLLOCATION_CHOICE))[0].id

    ket_qua = service.answer(db, owner.id, item_id, "hai")

    assert ket_qua.correct is False
    assert ket_qua.score == 0
    assert ket_qua.feedback.strip() != ""


def test_answer_dai_qua_1000_ky_tu_thi_text_too_long_cho_ca_loai_cham_local(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Giới hạn áp cho MỌI loại, kể cả loại chấm tại chỗ không chạm Gemini.

    Và không được ghi dòng lịch sử nào: request bị từ chối thì nó chưa từng là một lượt làm.
    """
    _the(db, _luu_tu(db, owner.id, "w0"), 2, 0)
    gemini.tra_json(_lo_fill_blank("w0"))
    item_id = service.generate(db, owner.id, _theo_count(5, QuizType.FILL_BLANK))[0].id

    with pytest.raises(AppError) as loi:
        service.answer(db, owner.id, item_id, "a" * 1001)
    assert loi.value.code is ErrorCode.TEXT_TOO_LONG
    assert _dem(db, QuizAttempt) == 0


def test_item_khong_ton_tai_thi_not_found(
    db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """NOT_FOUND chứ không FORBIDDEN — 403 xác nhận id đó có tồn tại (ràng buộc #13)."""
    with pytest.raises(AppError) as loi:
        service.answer(db, owner.id, 123_456, "x")
    assert loi.value.code is ErrorCode.NOT_FOUND
