"""Bản port của `TranslationServiceIT`.

Bên Java, `GeminiClient` bị `@MockitoBean` thay thẳng và các khẳng định "gọi mấy lần / gọi
với schema nào" viết bằng `verify(...)`. Ở đây `gemini` chặn thấp hơn một tầng — tại
`httpx.BaseTransport` — nên hai thứ đổi chỗ cho nhau:

* "gọi mấy lần" đọc từ `gemini.requests` (mỗi phần tử là một request HTTP thật đã dựng);
* "gọi với schema/prompt/timeout nào" đọc từ chính body và extensions của request đó, chứ
  không phải từ đối số Java truyền cho mock.

Đổi lại, toàn bộ đường đi thật vẫn chạy: dựng body, gửi, đọc `candidates[0]...text`, parse.
Đó là phần dễ port sai nhất, mock ở tầng cao hơn sẽ giấu nó đi.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text as sql
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.config import get_settings
from app.translation.cache import build_cache_key
from app.translation.models import Direction, Mode, TranslateRequest
from app.translation.prompts import get_prompt_loader
from app.translation.schemas import schema_for
from app.translation.service import MAX_TEXT_LENGTH, TranslationService
from tests.conftest import FakeGemini, UserFixture

#: Payload mà model "sinh ra" — cùng nội dung với bản Java để hai bộ test đọc đối chiếu được.
PAYLOAD: dict[str, Any] = {"meaning_vi": "tái tạo"}


@pytest.fixture
def service(gemini: FakeGemini) -> TranslationService:
    """Dựng SAU `gemini`.

    Thứ tự bắt buộc, không phải chuyện gọn gàng: `TranslationService()` lấy `GeminiClient`
    qua `get_gemini_client()` (có `lru_cache`), và fixture `gemini` chính là chỗ xoá cache
    đó. Dựng trước sẽ bám vào client của test TRƯỚC — cùng với transport giả đã chết của
    test trước.
    """
    return TranslationService()


def _make_request(text: str, context: str | None = None) -> TranslateRequest:
    return TranslateRequest(text=text, context_sentence=context)


def _cache_row_count(db: Session) -> int:
    return int(db.execute(sql("SELECT count(*) FROM lookup_cache")).scalar_one())


def _first_cache_row(db: Session) -> Any:
    return db.execute(
        sql(
            "SELECT source_hash, source_text, direction, mode, model, prompt_version, "
            "response, hit_count FROM lookup_cache ORDER BY id"
        )
    ).first()


def _body_sent_to_gemini(gemini: FakeGemini, index: int = 0) -> Any:
    return json.loads(gemini.requests[index].content)


# ── định tuyến direction × mode ───────────────────────────────────────────────


def test_english_word_takes_en_vi_word_route(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Tuyến mặc định của người dùng chính: bôi đen một từ tiếng Anh trên trang web.

    Ba field `direction`/`mode`/`cached` là thứ extension phân nhánh để chọn hình dạng
    payload — sai một cái là bubble render nhầm template.
    """
    gemini.queue_json(PAYLOAD)

    response = service.translate(
        db, owner.id, _make_request("renewable", "We need renewable energy.")
    )

    assert response.direction is Direction.EN_VI
    assert response.mode is Mode.WORD
    assert response.cached is False
    assert response.payload["meaning_vi"] == "tái tạo"


def test_vietnamese_sentence_takes_vi_en_sentence_route(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Chiều ngược lại, và mode ngược lại — cùng một hàm `translate` phải rẽ được cả hai."""
    gemini.queue_json({"band65_version": "The government should invest more in renewables"})

    response = service.translate(
        db,
        owner.id,
        _make_request("Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo"),
    )

    assert response.direction is Direction.VI_EN
    assert response.mode is Mode.SENTENCE


# ── cache ─────────────────────────────────────────────────────────────────────


def test_first_lookup_calls_gemini_and_writes_cache(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    gemini.queue_json(PAYLOAD)

    service.translate(db, owner.id, _make_request("renewable"))

    assert gemini.call_count == 1
    assert _cache_row_count(db) == 1


def test_cache_row_writes_every_column_correctly(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Không chỉ đếm dòng: đối chiếu TỪNG cột.

    `source_hash` là cột duy nhất quyết định lượt tra sau có ăn cache hay không, và port sai
    nó không gây ra lỗi nào — chỉ là mọi lượt tra đều gọi lại Gemini và hoá đơn quota tăng
    gấp đôi trong im lặng. Tính lại khoá bằng `build_cache_key` ở đây là cách duy nhất bắt
    được `TranslationService` truyền nhầm thành phần (ví dụ quên `context`, hoặc lấy version
    của prompt khác).
    """
    gemini.queue_json(PAYLOAD)
    settings = get_settings()
    template = get_prompt_loader().load(Direction.EN_VI, Mode.WORD)

    service.translate(db, owner.id, _make_request("renewable", "We need renewable energy."))

    cache_row = _first_cache_row(db)
    assert cache_row is not None
    assert cache_row.source_hash == build_cache_key(
        text="renewable",
        context="We need renewable energy.",
        direction=Direction.EN_VI,
        mode=Mode.WORD,
        model=settings.gemini_model,
        prompt_version=template.version,
    )
    assert cache_row.source_text == "renewable"
    assert cache_row.direction == "EN_VI"
    assert cache_row.mode == "WORD"
    assert cache_row.model == settings.gemini_model
    assert cache_row.prompt_version == template.version
    assert cache_row.response == PAYLOAD
    # Lượt ghi là lượt MISS, không phải hit — bắt đầu từ 0.
    assert cache_row.hit_count == 0


def test_second_matching_lookup_hits_cache_and_does_not_call_gemini(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Lý do tồn tại của cả bảng `lookup_cache`.

    Chỉ xếp ĐÚNG MỘT phản hồi: nếu lượt thứ hai vẫn gọi ra ngoài thì transport giả ném
    AssertionError ngay, chứ không lặng lẽ trả thêm một payload nữa rồi để test xanh.
    """
    gemini.queue_json(PAYLOAD)
    request = _make_request("renewable")

    first_response = service.translate(db, owner.id, request)
    second_response = service.translate(db, owner.id, request)

    assert first_response.cached is False
    assert second_response.cached is True
    assert gemini.call_count == 1
    # Payload trả từ cache phải giống hệt payload lượt đầu — đọc từ JSONB ra, không phải
    # dựng lại từ đâu khác.
    assert second_response.payload["meaning_vi"] == "tái tạo"
    assert _cache_row_count(db) == 1


def test_cache_hit_increments_hit_count_counter(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Ba lượt tra = 1 miss + 2 hit. Bộ đếm là 2, không phải 3."""
    gemini.queue_json(PAYLOAD)
    request = _make_request("renewable")

    service.translate(db, owner.id, request)
    service.translate(db, owner.id, request)
    service.translate(db, owner.id, request)

    cache_row = _first_cache_row(db)
    assert cache_row is not None
    assert cache_row.hit_count == 2


def test_different_context_does_not_share_cache_row(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Cùng một từ trong hai câu khác nhau có thể mang hai nghĩa khác nhau. Dùng chung một
    dòng cache là trả nghĩa của câu trước cho câu sau."""
    gemini.queue_json(PAYLOAD, times=2)

    service.translate(db, owner.id, _make_request("renewable", "context A"))
    service.translate(db, owner.id, _make_request("renewable", "context B"))

    assert gemini.call_count == 2
    assert _cache_row_count(db) == 2


def test_cache_key_does_not_collide_when_text_context_boundary_shifts(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """("ab","c") và ("a","bc") — nối chuỗi trần sẽ ra cùng một material.

    Đây chính là lý do `_append_field` có tiền tố độ dài. Bỏ tiền tố đi thì test này đỏ, và
    không có test nào khác đỏ.
    """
    gemini.queue_json(PAYLOAD, times=2)

    service.translate(db, owner.id, _make_request("ab", "c"))
    service.translate(db, owner.id, _make_request("a", "bc"))

    assert _cache_row_count(db) == 2


# ── giới hạn độ dài ───────────────────────────────────────────────────────────


def test_text_over_1500_characters_is_rejected_before_touching_gemini(
    db: Session,
    gemini: FakeGemini,
    service: TranslationService,
    owner: UserFixture,
    assert_no_gemini_call: Callable[[], None],
) -> None:
    """Chặn ở 1500 ký tự (ràng buộc #9), và chặn TRƯỚC Gemini.

    Vế thứ hai là phần đắt: một đoạn 20 nghìn ký tự lọt xuống Gemini vẫn "chạy được", chỉ là
    tốn tiền và chậm. Bản Java khẳng định bằng `verifyNoInteractions`.
    """
    too_long_text = "a" * (MAX_TEXT_LENGTH + 1)

    with pytest.raises(AppError) as ex:
        service.translate(db, owner.id, _make_request(too_long_text))

    assert ex.value.code is ErrorCode.TEXT_TOO_LONG
    assert_no_gemini_call()
    assert _cache_row_count(db) == 0


def test_exactly_1500_characters_still_passes(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Chặn khi `> 1500`, không phải `>= 1500`. Lệch một ký tự ở đây là hai đầu nói hai luật
    khác nhau: extension cho gửi, backend từ chối."""
    gemini.queue_json(PAYLOAD)

    response = service.translate(db, owner.id, _make_request("a" * MAX_TEXT_LENGTH))

    assert response.cached is False


# ── đối số gửi sang Gemini ────────────────────────────────────────────────────


def test_gemini_receives_correct_schema_and_timeout_for_detected_route(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """Schema phải khớp tuyến đã dò ra, không phải một schema mặc định nào đó.

    Gửi nhầm schema thì Gemini vẫn trả JSON hợp lệ — hợp lệ theo schema SAI — nên payload
    lọt xuống cache và ra tới bubble mà không có lỗi nào. Mức timeout kiểm luôn ở đây vì
    `GeminiTimeout` cố ý không có giá trị mặc định: một lượt dịch lỡ chạy ở mức 30 giây
    không làm gì đỏ, chỉ bắt người dùng đợi gấp đôi khi Gemini chậm thật.
    """
    gemini.queue_json(PAYLOAD)

    service.translate(db, owner.id, _make_request("renewable"))

    body = _body_sent_to_gemini(gemini)
    assert body["generationConfig"]["responseSchema"] == schema_for(
        Direction.EN_VI, Mode.WORD
    )
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    read_timeout = gemini.requests[0].extensions["timeout"]["read"]
    assert read_timeout == float(get_settings().gemini_timeout_seconds)


def test_sent_prompt_contains_both_text_and_context(
    db: Session, gemini: FakeGemini, service: TranslationService, owner: UserFixture
) -> None:
    """`{{TEXT}}` và `{{CONTEXT}}` phải được thay thật.

    Quên thay một trong hai vẫn ra một prompt trông bình thường và model vẫn trả JSON đúng
    schema — chỉ là nó đoán nghĩa của một từ mà nó không được cho biết là từ nào.
    """
    gemini.queue_json(PAYLOAD)

    service.translate(db, owner.id, _make_request("renewable", "some context"))

    prompt = _body_sent_to_gemini(gemini)["contents"][0]["parts"][0]["text"]
    assert "renewable" in prompt
    assert "some context" in prompt
    assert "{{" not in prompt
