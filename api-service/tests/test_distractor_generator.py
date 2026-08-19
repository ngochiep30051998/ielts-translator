"""Bản port của `DistractorGeneratorIT` — luồng sinh mồi nhử chạy nền sau khi lưu từ.

Bên Java, việc này là `@TransactionalEventListener(AFTER_COMMIT)` + `@Async`, nên test phải
`await()` tới 5 giây cho thread nền chạy xong. Ở FastAPI vai trò đó do `BackgroundTasks`
đảm nhiệm và `TestClient` chạy chúng ĐỒNG BỘ ngay sau khi response được gửi — nên không có
`await`, không có `sleep`: hễ `client.post(...)` trả về là tác vụ nền đã chạy xong. Đó là
lý do các khẳng định dưới đây đọc thẳng DB mà không cần vòng chờ nào.

Hai điều kiện then chốt của luồng này, cả hai đều được kiểm ở đây:

* tác vụ nền chạy SAU khi session của request đã commit — nếu không, nó mở session riêng và
  không thấy từ vừa lưu, `find_vocab_entry` trả None, không có mồi nhử nào được sinh mà cũng
  chẳng có gì đỏ;
* Gemini hỏng KHÔNG được kéo đổ việc lưu từ.

**Thứ tự fixture có ý nghĩa: `client` phải đứng TRƯỚC `gemini` trong chữ ký test.** Fixture
`gemini` vá `httpx.Client.__init__` cho toàn tiến trình, mà `TestClient` cũng chính là một
`httpx.Client` — dựng nó sau khi vá thì chính TestClient nhận transport giả, `client.post`
không bao giờ chạm tới ứng dụng và vẫn trả về 200. Đó là kiểu hỏng tệ nhất: test xanh mà
chẳng kiểm gì cả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.srs.distractors import current_prompt_version, generate_distractors
from tests.conftest import FakeGemini, UserFixture

VALID_DISTRACTOR_SET: dict[str, list[str]] = {
    "vi_options": ["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
    "en_options": ["aggravate", "exaggerate", "postpone"],
}


def _save_word(client: Any, owner: UserFixture, term: str, pos: str) -> int:
    """Lưu một từ qua API thật, đúng hình dạng `request(term, pos)` bên Java.

    `meaningVi` = "nghĩa của <term>" cũng lấy nguyên từ bản Java: test bộ hỏng dựa vào việc
    Gemini trả về đúng chuỗi này để mô phỏng "mồi nhử trùng đáp án đúng".
    """
    resp = client.post(
        "/api/vocab",
        headers=owner.headers,
        json={
            "term": term,
            "lemma": term,
            "lang": "en",
            "pos": pos,
            "meaningVi": f"nghĩa của {term}",
            "tags": [],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["alreadyExists"] is False
    return int(resp.json()["id"])


def _distractor_row(db: Session, vocab_id: int) -> Any:
    db.rollback()  # kết thúc transaction đọc cũ để thấy commit của tác vụ nền
    return db.execute(
        text(
            "SELECT vi_options, en_options, prompt_version "
            "FROM srs_distractor WHERE vocab_entry_id = :v"
        ),
        {"v": vocab_id},
    ).one_or_none()


def _record_count(db: Session) -> int:
    db.rollback()
    return int(db.execute(text("SELECT count(*) FROM srs_distractor")).scalar_one())


def test_saving_a_single_word_generates_and_stores_distractors_with_prompt_version(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Ca chính: lưu từ → tác vụ nền gọi Gemini → bộ mồi nhử nằm trong DB kèm version prompt.

    `prompt_version` là thứ duy nhất làm mồi nhử cũ hết hiệu lực khi sửa nội dung prompt
    (ràng buộc #5). Ghi thiếu hoặc ghi sai version thì `find_fresh_distractors` lọc trượt và
    hệ thống sinh lại mồi nhử ở MỌI lượt mở tab ôn — đốt quota mà không ai thấy.
    """
    gemini.queue_json(VALID_DISTRACTOR_SET)

    vocab_id = _save_word(client, owner, "mitigate", "verb")

    row = _distractor_row(db, vocab_id)
    assert row is not None, "Tác vụ nền không ghi được mồi nhử nào"
    assert len(row.vi_options) == 3
    # So từng cột, đúng thứ tự — không chỉ đếm: thứ tự sai nghĩa là mồi nhử EN bị gán vào
    # chiều VI, câu hỏi hiện ra bốn từ tiếng Anh cho một đề tiếng Việt.
    assert row.en_options == ["aggravate", "exaggerate", "postpone"]
    assert row.vi_options == ["làm trầm trọng thêm", "phóng đại", "trì hoãn"]
    assert row.prompt_version == current_prompt_version()
    assert gemini.call_count == 1


def test_saving_a_whole_sentence_with_pos_phrase_makes_no_gemini_call(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Câu đầy đủ không làm trắc nghiệm được, nên không có gì để sinh mồi nhử.

    Khẳng định "KHÔNG gọi Gemini" quan trọng hơn khẳng định "không có bản ghi": một lượt gọi
    thừa cho mỗi câu người dùng bôi đen là quota bị đốt lặng lẽ, mà kết quả thì bị vứt đi.
    """
    # Xếp sẵn một phản hồi hợp lệ: nếu code lỡ gọi Gemini thì nó sẽ THÀNH CÔNG và ghi bản
    # ghi, tức là test đỏ ở đúng chỗ cần đỏ chứ không đỏ vì hàng đợi cạn.
    gemini.queue_json(VALID_DISTRACTOR_SET)

    _save_word(client, owner, "Governments must act on climate change.", "phrase")

    assert gemini.requests == []
    assert _record_count(db) == 0


def test_gemini_error_keeps_word_in_the_book_only_without_distractors(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Gemini chết không được kéo đổ việc lưu từ.

    Đây chính là lý do luồng này chạy nền chứ không nằm trong transaction lưu từ: người dùng
    bôi đen một từ và bấm lưu thì từ phải vào sổ, bất kể Gemini có sống hay không. Lần mở tab
    ôn sau sẽ thử lại qua đường `_request_missing`.

    Xếp 503 hai lần vì `GeminiClient` retry đúng một lần với lỗi tạm thời — bản Java mock
    thẳng `generateJson` nên không lộ ra chi tiết đó; ở đây đi qua tầng vận chuyển thật nên
    số lượt gọi là một phần của hành vi được kiểm.
    """
    gemini.queue_status(503, '{"error":"unavailable"}', times=2)

    vocab_id = _save_word(client, owner, "resilient", "adjective")

    assert vocab_id > 0
    db.rollback()
    word_count = db.execute(
        text("SELECT count(*) FROM vocab_entry WHERE id = :v"), {"v": vocab_id}
    ).scalar_one()
    assert word_count == 1, "Gemini lỗi đã kéo đổ luôn việc lưu từ"
    # Thẻ ôn cũng phải còn: nó được tạo ĐỒNG BỘ trong cùng transaction với từ.
    card_count = db.execute(
        text("SELECT count(*) FROM srs_card WHERE vocab_entry_id = :v"), {"v": vocab_id}
    ).scalar_one()
    assert card_count == 1
    assert _distractor_row(db, vocab_id) is None
    assert gemini.call_count == 2


def test_gemini_returns_broken_set_colliding_with_correct_answer_saves_nothing(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """Không lưu gì, để lần sau sinh lại.

    Lưu một bộ hỏng còn tệ hơn không lưu: `find_fresh_distractors` sẽ coi nó là hợp lệ, và
    người học gặp một câu có hai đáp án cùng đúng — chọn đúng vẫn bị chấm sai. Bộ hỏng cũng
    KHÔNG được retry: nó không phải lỗi tạm thời, gọi lại ngay chỉ tốn thêm một lượt quota.
    """
    gemini.queue_json(
        {
            "vi_options": ["nghĩa của mitigate", "phóng đại", "trì hoãn"],
            "en_options": ["aggravate", "exaggerate", "postpone"],
        }
    )

    vocab_id = _save_word(client, owner, "mitigate", "verb")

    assert _distractor_row(db, vocab_id) is None
    assert _record_count(db) == 0
    assert gemini.call_count == 1


def test_regenerating_for_word_with_distractors_overwrites_instead_of_creating_second_record(
    client: Any, db: Session, gemini: FakeGemini, owner: UserFixture
) -> None:
    """`vocab_entry_id` là khoá duy nhất, nên sinh lại phải UPDATE chứ không INSERT.

    Nếu code quên tra bản ghi cũ, lượt thứ hai sẽ đâm vào ràng buộc unique và lỗi bị
    `except Exception` của tác vụ nền nuốt mất — mồi nhử đứng yên ở bản cũ vĩnh viễn, không
    có gì đỏ, và tăng version prompt cũng vô tác dụng.

    Lượt thứ hai gọi thẳng `generate_distractors` (vai của `generator.generateAsync` bên
    Java): đây đúng là đường mà `_request_missing` dùng để bù mồi nhử hết hiệu lực.
    """
    gemini.queue_json(VALID_DISTRACTOR_SET)
    vocab_id = _save_word(client, owner, "mitigate", "verb")
    assert _distractor_row(db, vocab_id) is not None

    before = _distractor_row(db, vocab_id)
    gemini.queue_json({"vi_options": ["một", "hai", "ba"], "en_options": ["one", "two", "three"]})
    generate_distractors(vocab_id)

    assert _record_count(db) == 1
    after = _distractor_row(db, vocab_id)
    assert after is not None
    assert after.en_options == ["one", "two", "three"]
    assert after.vi_options == ["một", "hai", "ba"]
    assert before is not None and before.en_options != after.en_options
    assert gemini.call_count == 2
