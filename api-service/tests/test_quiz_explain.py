"""Bản port của `QuizExplainIT` — endpoint `POST /api/quiz/explain`.

Bên Java, Gemini bị `@MockitoBean` nên test khẳng định được "gọi đúng một lần với tier
QUIZ_GRADE". Ở đây `gemini` chặn tầng vận chuyển httpx: nó không phân biệt được tier, nhưng
bù lại toàn bộ đường đi thật (dựng body, bóc `candidates[0]…text`, map status → ErrorCode)
vẫn được chạy qua. Hệ quả với người đọc test: **hàng đợi phản hồi là FIFO dùng chung cho cả
sinh đề lẫn giải thích**, nên thứ tự `tra_json` trong mỗi test chính là thứ tự các lượt gọi,
và `gemini.so_lan_goi` thay cho `verify(...)`.

Bất biến lớn nhất của file: response ở đây TIẾT LỘ ĐÁP ÁN, nên endpoint chỉ phục vụ item đã
có ít nhất một lượt làm — và chốt chặn đó phải nằm TRƯỚC lượt gọi Gemini.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import GeminiGia, NguoiDungTest

# ── dữ liệu Gemini "sinh ra", chép nguyên từ các stub bên Java ─────────────────

_CAU_FILL_BLANK = "Governments must ___ the impact of flooding."


def _de_fill_blank(sentence: str = _CAU_FILL_BLANK, answer: str = "mitigate") -> dict[str, Any]:
    return {
        "items": [
            {"term": "mitigate", "sentence": sentence, "answer": answer, "hint": "làm nhẹ bớt"}
        ]
    }


_DE_COLLOCATION: dict[str, Any] = {
    "items": [
        {
            "term": "mitigate",
            "question": "Cụm nào đi với «mitigate» là tự nhiên?",
            "options": [
                "mitigate the risk",
                "mitigate a cake",
                "mitigate loudly",
                "mitigate blue",
            ],
            "correct_index": 0,
        }
    ]
}


# ── helper ────────────────────────────────────────────────────────────────────


def _seed_tu_da_on(db: Session, user_id: int, term: str, nghia: str) -> int:
    """Một từ đã ôn ít nhất một lượt — điều kiện để lọt vào danh sách ứng viên.

    `user_id` là NOT NULL từ V6: dựng entry mà quên chủ sở hữu là nổ ngay lúc insert.
    """
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry "
                "(term, lemma, lang, pos, meaning_vi, user_id, collocations, examples) "
                "VALUES (:t, :t, 'en', 'verb', :m, :u, '[]'::jsonb, '[]'::jsonb) RETURNING id"
            ),
            {"t": term, "m": nghia, "u": user_id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions, lapses) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', 3, 1)"
        ),
        {"v": vocab_id},
    )
    db.commit()
    return vocab_id


def _sinh_de(client: Any, owner: NguoiDungTest, loai: str) -> int:
    resp = client.post(
        "/api/quiz/generate", headers=owner.headers, json={"count": 5, "type": loai}
    )
    assert resp.status_code == 200, resp.text
    de = resp.json()
    assert de, f"{loai} phải sinh được ít nhất một câu"
    return int(de[0]["id"])


def _tra_loi(client: Any, owner: NguoiDungTest, quiz_item_id: int, answer: str) -> None:
    resp = client.post(
        "/api/quiz/answer",
        headers=owner.headers,
        json={"quizItemId": quiz_item_id, "answer": answer},
    )
    assert resp.status_code == 200, resp.text


def _giai_thich(client: Any, owner: NguoiDungTest, quiz_item_id: int) -> Any:
    return client.post(
        "/api/quiz/explain", headers=owner.headers, json={"quizItemId": quiz_item_id}
    )


def _vi_tri_lua_chon(db: Session, quiz_item_id: int, option: str) -> int:
    """Vị trí 0-based của một cụm trong `options` ĐÃ XÁO của item đang lưu.

    Không đoán được vị trí: `_collocation_payload` xáo đúng một lần lúc lưu, nên câu trả lời
    hợp lệ chỉ có thể đọc ngược ra từ chính payload trong DB.
    """
    raw = db.execute(
        text("SELECT payload->>'options' FROM quiz_item WHERE id = :i"), {"i": quiz_item_id}
    ).scalar_one()
    options = json.loads(raw)
    assert option in options, f"Không tìm thấy lựa chọn: {option}"
    return int(options.index(option))


def _prompt_cuoi(gemini: GeminiGia) -> str:
    """Prompt của lượt gọi Gemini gần nhất — thay `ArgumentCaptor<String>` bên Java."""
    assert gemini.requests, "Chưa có lượt gọi Gemini nào để đọc prompt"
    body = json.loads(gemini.requests[-1].content)
    return str(body["contents"][0]["parts"][0]["text"])


# ── FILL_BLANK ────────────────────────────────────────────────────────────────


def test_fill_blank_sentence_en_do_backend_tu_ghep(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """`sentenceEn` là câu đề bài ĐÃ điền đáp án, ghép ở backend chứ không nhờ Gemini.

    Gemini CỐ Ý trả `sentence_en` rác: với loại này backend đã cầm sẵn câu tiếng Anh, nên
    chuỗi model trả về phải bị bỏ qua hoàn toàn. Nhờ Gemini chép lại một chuỗi ta đang cầm
    chỉ tạo cơ hội cho nó chép sai.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_de_fill_blank())
    item_id = _sinh_de(client, owner, "FILL_BLANK")
    _tra_loi(client, owner, item_id, "reduce")

    gemini.tra_json(
        {
            "explanation_vi": '"mitigate" đi với impact; "reduce" nhạt hơn.',
            "answer_meaning_vi": "mitigate = giảm nhẹ",
            "sentence_en": "CÂU RÁC GEMINI TỰ BỊA",
            "sentence_vi": "Chính phủ phải giảm nhẹ tác động của lũ lụt.",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] == "Governments must mitigate the impact of flooding."
    assert body["sentenceVi"] == "Chính phủ phải giảm nhẹ tác động của lũ lụt."
    assert body["answerMeaning"] == "mitigate = giảm nhẹ"
    assert "reduce" in body["explanation"]


def test_fill_blank_bo_qua_cau_van_giai_thich_va_van_du_cap_cau(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Bỏ qua câu điền từ vẫn giải thích được, và vẫn đủ cặp câu.

    Khác hẳn FREE_WRITE bị bỏ qua: ở đây câu tiếng Anh vẫn tồn tại (nó là chính đề bài), nên
    cặp `sentenceEn`/`sentenceVi` phải còn nguyên. Gộp hai ca "bỏ qua" làm một là mất một
    khối học liệu mà không ai báo.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_de_fill_blank())
    item_id = _sinh_de(client, owner, "FILL_BLANK")
    _tra_loi(client, owner, item_id, "")

    gemini.tra_json(
        {
            "explanation_vi": '"mitigate" là làm nhẹ tác động tiêu cực.',
            "answer_meaning_vi": "mitigate = giảm nhẹ",
            "sentence_vi": "Chính phủ phải giảm nhẹ tác động của lũ lụt.",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] == "Governments must mitigate the impact of flooding."
    assert body["sentenceVi"] == "Chính phủ phải giảm nhẹ tác động của lũ lụt."
    # Bỏ qua câu KHÔNG gọi Gemini để chấm: đúng 2 lượt (sinh đề + giải thích).
    assert gemini.so_lan_goi == 2


# ── COLLOCATION_CHOICE ────────────────────────────────────────────────────────


def test_collocation_sentence_en_lay_tu_gemini(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Với loại này backend KHÔNG có câu tiếng Anh nào, nên `sentenceEn` lấy từ Gemini.

    Đây là nửa còn lại của bất biến ở test FILL_BLANK: "bỏ qua chuỗi Gemini" chỉ đúng khi
    backend đã biết câu; hiện thực bằng một cờ cứng theo loại sẽ hỏng đúng ở đây.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_DE_COLLOCATION)
    item_id = _sinh_de(client, owner, "COLLOCATION_CHOICE")
    _tra_loi(client, owner, item_id, str(_vi_tri_lua_chon(db, item_id, "mitigate a cake")))

    gemini.tra_json(
        {
            "explanation_vi": "«mitigate the risk» là cách người bản ngữ nói.",
            "answer_meaning_vi": "mitigate the risk = giảm thiểu rủi ro",
            "sentence_en": "Careful planning can mitigate the risk of flooding.",
            "sentence_vi": "Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt.",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] == "Careful planning can mitigate the risk of flooding."
    assert body["sentenceVi"] == "Quy hoạch cẩn thận có thể giảm thiểu rủi ro lũ lụt."
    assert body["answerMeaning"] == "mitigate the risk = giảm thiểu rủi ro"


def test_prompt_collocation_mang_noi_dung_cum_da_chon(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Prompt nhận NỘI DUNG cụm người học chọn, không phải index dạng chuỗi.

    Câu trả lời lưu trong `quiz_attempt` là index ("0".."3"). Đưa thẳng "2" vào prompt thì
    Gemini không có cách nào biết người học đã chọn gì, và yêu cầu "chỉ thẳng chỗ sai" tụt
    về một lời giải thích chung chung mà không có test nào đỏ.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_DE_COLLOCATION)
    item_id = _sinh_de(client, owner, "COLLOCATION_CHOICE")
    _tra_loi(client, owner, item_id, str(_vi_tri_lua_chon(db, item_id, "mitigate a cake")))

    gemini.tra_json(
        {
            "explanation_vi": "x",
            "answer_meaning_vi": "y",
            "sentence_en": "z",
            "sentence_vi": "t",
        }
    )
    assert _giai_thich(client, owner, item_id).status_code == 200

    prompt = _prompt_cuoi(gemini)
    assert "mitigate a cake" in prompt
    assert "mitigate the risk" in prompt
    # Chặt hơn bản Java: cả bốn cụm đều nằm trong khối OPTIONS nên phép `contains` ở trên tự
    # nó chưa chứng minh được gì. Hai dòng dưới mới là thứ bất biến thật sự nói.
    assert "Người học đã chọn: mitigate a cake" in prompt
    assert "Cụm đúng: mitigate the risk" in prompt
    # Đúng hai lượt: sinh đề + giải thích. Chấm collocation là local, không chạm Gemini.
    assert gemini.so_lan_goi == 2


def test_bo_qua_cau_collocation_gui_user_answer_rong(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Bỏ qua câu chọn cụm: prompt nhận USER_ANSWER RỖNG, không phải cụm số 0.

    Chuỗi rỗng KHÔNG được hiểu thành index 0. Nếu `_option_at` trả về `options[0]` thì prompt
    sẽ nói "bạn đã chọn «...»" với người vừa bỏ qua câu — vừa sai sự thật, vừa có xác suất
    trùng đúng đáp án.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_DE_COLLOCATION)
    item_id = _sinh_de(client, owner, "COLLOCATION_CHOICE")
    _tra_loi(client, owner, item_id, "")

    gemini.tra_json(
        {
            "explanation_vi": "x",
            "answer_meaning_vi": "y",
            "sentence_en": "z",
            "sentence_vi": "t",
        }
    )
    assert _giai_thich(client, owner, item_id).status_code == 200

    # Regex chứ không so chuỗi thẳng: dòng đó là "Người học đã chọn: {{USER_ANSWER}}", có một
    # dấu cách trước placeholder. Bất biến cần khẳng định là "không còn gì ngoài khoảng trắng
    # trên dòng đó", chứ không phải số dấu cách.
    assert re.search(r"Người học đã chọn:\s*\n", _prompt_cuoi(gemini)) is not None


# ── FREE_WRITE ────────────────────────────────────────────────────────────────


def test_free_write_sentence_en_la_improved_version(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """`sentenceEn` là câu viết lại của lượt làm — câu mẫu đáng học nhất mà người học có."""
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    # FREE_WRITE dựng thẳng ở Python, KHÔNG gọi Gemini lúc sinh đề.
    item_id = _sinh_de(client, owner, "FREE_WRITE")
    assert gemini.so_lan_goi == 0

    gemini.tra_json(
        {
            "meaning_ok": True,
            "grammar_ok": True,
            "band_ok": True,
            "score": 88,
            "feedback_vi": "Câu dùng từ đúng nghĩa.",
            "improved_version": "Governments must mitigate the impact of flooding.",
        }
    )
    _tra_loi(client, owner, item_id, "We mitigate it.")

    gemini.tra_json(
        {
            "explanation_vi": '"mitigate" đi với danh từ chỉ tác động tiêu cực.',
            "answer_meaning_vi": "mitigate = giảm nhẹ",
            "sentence_vi": "Chính phủ phải giảm nhẹ tác động của lũ lụt.",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] == "Governments must mitigate the impact of flooding."
    assert body["sentenceVi"] == "Chính phủ phải giảm nhẹ tác động của lũ lụt."


def test_free_write_khong_co_improved_version_thi_lay_cau_nguoi_hoc(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Không có câu viết lại thì `sentenceEn` là chính câu người học viết.

    Ca này xảy ra thật khi bài đã tốt — Gemini không đề xuất gì thêm. Bỏ lưới hứng ở đây là
    người viết đúng lại mất luôn khối "Dịch câu".
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    item_id = _sinh_de(client, owner, "FREE_WRITE")

    gemini.tra_json(
        {
            "meaning_ok": True,
            "grammar_ok": True,
            "band_ok": True,
            "score": 92,
            "feedback_vi": "Câu đã tốt.",
        }
    )
    _tra_loi(client, owner, item_id, "We must mitigate the damage.")

    gemini.tra_json(
        {
            "explanation_vi": "Dùng đúng rồi.",
            "answer_meaning_vi": "mitigate = giảm nhẹ",
            "sentence_vi": "Chúng ta phải giảm nhẹ thiệt hại.",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] == "We must mitigate the damage."
    assert body["sentenceVi"] == "Chúng ta phải giảm nhẹ thiệt hại."


def test_free_write_bo_qua_cau_thi_khong_co_cap_cau(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Bỏ qua bài viết: `sentenceEn` và `sentenceVi` CÙNG None.

    Đây là ca DUY NHẤT không tồn tại câu tiếng Anh nào để dịch. Khoá vẫn PHẢI có mặt với giá
    trị null — mirror TypeScript khai `string | null` chứ không phải optional, hai bên chỉ
    khớp khi khoá luôn xuất hiện.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    item_id = _sinh_de(client, owner, "FREE_WRITE")
    _tra_loi(client, owner, item_id, "")  # bỏ qua: không gọi Gemini để chấm

    gemini.tra_json(
        {
            "explanation_vi": '"mitigate" dùng với tác động tiêu cực.',
            "answer_meaning_vi": "mitigate = giảm nhẹ",
            "sentence_vi": "",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "mitigate" in body["explanation"]
    assert "sentenceEn" in body
    assert body["sentenceEn"] is None
    assert "sentenceVi" in body
    assert body["sentenceVi"] is None
    # Đúng một lượt gọi: chấm bài rỗng bị bỏ qua, chỉ còn lượt giải thích.
    assert gemini.so_lan_goi == 1


# ── chốt chặn ─────────────────────────────────────────────────────────────────


def test_chua_tra_loi_thi_404_va_khong_dot_quota(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Chưa trả lời thì 404 và KHÔNG gọi Gemini — không đọc trộm được đáp án.

    Không một lượt gọi nào: vừa là chuyện quota, vừa là bằng chứng chốt chặn nằm TRƯỚC lượt
    gọi Gemini chứ không phải sau nó.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_de_fill_blank("Governments must ___ the impact.", "mitigate"))
    item_id = _sinh_de(client, owner, "FILL_BLANK")

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False
    # Đúng một lượt — lượt sinh đề. Lượt thứ hai nào cũng là chốt chặn nằm sai chỗ.
    assert gemini.so_lan_goi == 1


def test_quiz_item_id_khong_ton_tai_thi_404(
    client: Any, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Id không tồn tại → 404 NOT_FOUND, không phải 500 và cũng không phải 403."""
    resp = _giai_thich(client, owner, 999999)

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False
    assert gemini.requests == []


def test_gemini_chet_thi_truyen_nguyen_gemini_unavailable(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Gemini chết → GEMINI_UNAVAILABLE truyền nguyên, retry được.

    Endpoint này không có cache và không ghi gì, nên "thử lại" đúng là đường hồi phục — nuốt
    lỗi thành 500 ở đây là chỉ sai đường cho người dùng.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_de_fill_blank("Governments must ___ the impact.", "mitigate"))
    item_id = _sinh_de(client, owner, "FILL_BLANK")
    _tra_loi(client, owner, item_id, "reduce")

    # MAX_ATTEMPTS = 2 và 5xx là lỗi tạm thời, nên cả hai lượt đều phải chết.
    gemini.tra_status(503, lap=2)

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 503, resp.text
    assert resp.json()["code"] == "GEMINI_UNAVAILABLE"
    assert resp.json()["retryable"] is True
    # 1 lượt sinh đề + đúng 2 lượt giải thích: retry chạy đúng một lần, không nhiều hơn.
    assert gemini.so_lan_goi == 3


def test_thieu_mot_nua_cap_cau_thi_bo_ca_cap(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Gemini trả `sentence_vi` rỗng → bỏ CẢ CẶP, không trả một nửa.

    `sentenceEn` có giá trị thật nhưng thiếu bản dịch: giữ lại nó là bắt panel render khối
    "Dịch câu" với đúng một dòng tiếng Anh và không có dịch.
    """
    _seed_tu_da_on(db, owner.id, "mitigate", "giảm nhẹ")
    gemini.tra_json(_DE_COLLOCATION)
    item_id = _sinh_de(client, owner, "COLLOCATION_CHOICE")
    _tra_loi(client, owner, item_id, str(_vi_tri_lua_chon(db, item_id, "mitigate the risk")))

    gemini.tra_json(
        {
            "explanation_vi": "Cụm này tự nhiên.",
            "answer_meaning_vi": "= giảm rủi ro",
            "sentence_en": "Careful planning can mitigate the risk.",
            "sentence_vi": "",
        }
    )

    resp = _giai_thich(client, owner, item_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sentenceEn"] is None
    assert body["sentenceVi"] is None
