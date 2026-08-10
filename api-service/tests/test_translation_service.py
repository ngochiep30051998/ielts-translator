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
from tests.conftest import GeminiGia, NguoiDungTest

#: Payload mà model "sinh ra" — cùng nội dung với bản Java để hai bộ test đọc đối chiếu được.
PAYLOAD: dict[str, Any] = {"meaning_vi": "tái tạo"}


@pytest.fixture
def service(gemini: GeminiGia) -> TranslationService:
    """Dựng SAU `gemini`.

    Thứ tự bắt buộc, không phải chuyện gọn gàng: `TranslationService()` lấy `GeminiClient`
    qua `get_gemini_client()` (có `lru_cache`), và fixture `gemini` chính là chỗ xoá cache
    đó. Dựng trước sẽ bám vào client của test TRƯỚC — cùng với transport giả đã chết của
    test trước.
    """
    return TranslationService()


def _yeu_cau(text: str, context: str | None = None) -> TranslateRequest:
    return TranslateRequest(text=text, context_sentence=context)


def _so_dong_cache(db: Session) -> int:
    return int(db.execute(sql("SELECT count(*) FROM lookup_cache")).scalar_one())


def _dong_cache_dau(db: Session) -> Any:
    return db.execute(
        sql(
            "SELECT source_hash, source_text, direction, mode, model, prompt_version, "
            "response, hit_count FROM lookup_cache ORDER BY id"
        )
    ).first()


def _body_gui_gemini(gemini: GeminiGia, thu_tu: int = 0) -> Any:
    return json.loads(gemini.requests[thu_tu].content)


# ── định tuyến direction × mode ───────────────────────────────────────────────


def test_tu_tieng_anh_di_theo_tuyen_en_vi_word(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Tuyến mặc định của người dùng chính: bôi đen một từ tiếng Anh trên trang web.

    Ba field `direction`/`mode`/`cached` là thứ extension phân nhánh để chọn hình dạng
    payload — sai một cái là bubble render nhầm template.
    """
    gemini.tra_json(PAYLOAD)

    response = service.translate(
        db, owner.id, _yeu_cau("renewable", "We need renewable energy.")
    )

    assert response.direction is Direction.EN_VI
    assert response.mode is Mode.WORD
    assert response.cached is False
    assert response.payload["meaning_vi"] == "tái tạo"


def test_cau_tieng_viet_di_theo_tuyen_vi_en_sentence(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Chiều ngược lại, và mode ngược lại — cùng một hàm `translate` phải rẽ được cả hai."""
    gemini.tra_json({"band65_version": "The government should invest more in renewables"})

    response = service.translate(
        db,
        owner.id,
        _yeu_cau("Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo"),
    )

    assert response.direction is Direction.VI_EN
    assert response.mode is Mode.SENTENCE


# ── cache ─────────────────────────────────────────────────────────────────────


def test_lan_dau_goi_gemini_va_ghi_cache(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    gemini.tra_json(PAYLOAD)

    service.translate(db, owner.id, _yeu_cau("renewable"))

    assert gemini.so_lan_goi == 1
    assert _so_dong_cache(db) == 1


def test_dong_cache_ghi_dung_tung_cot(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Không chỉ đếm dòng: đối chiếu TỪNG cột.

    `source_hash` là cột duy nhất quyết định lượt tra sau có ăn cache hay không, và port sai
    nó không gây ra lỗi nào — chỉ là mọi lượt tra đều gọi lại Gemini và hoá đơn quota tăng
    gấp đôi trong im lặng. Tính lại khoá bằng `build_cache_key` ở đây là cách duy nhất bắt
    được `TranslationService` truyền nhầm thành phần (ví dụ quên `context`, hoặc lấy version
    của prompt khác).
    """
    gemini.tra_json(PAYLOAD)
    cai_dat = get_settings()
    template = get_prompt_loader().load(Direction.EN_VI, Mode.WORD)

    service.translate(db, owner.id, _yeu_cau("renewable", "We need renewable energy."))

    dong = _dong_cache_dau(db)
    assert dong is not None
    assert dong.source_hash == build_cache_key(
        text="renewable",
        context="We need renewable energy.",
        direction=Direction.EN_VI,
        mode=Mode.WORD,
        model=cai_dat.gemini_model,
        prompt_version=template.version,
    )
    assert dong.source_text == "renewable"
    assert dong.direction == "EN_VI"
    assert dong.mode == "WORD"
    assert dong.model == cai_dat.gemini_model
    assert dong.prompt_version == template.version
    assert dong.response == PAYLOAD
    # Lượt ghi là lượt MISS, không phải hit — bắt đầu từ 0.
    assert dong.hit_count == 0


def test_lan_hai_trung_khop_an_cache_va_khong_goi_gemini(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Lý do tồn tại của cả bảng `lookup_cache`.

    Chỉ xếp ĐÚNG MỘT phản hồi: nếu lượt thứ hai vẫn gọi ra ngoài thì transport giả ném
    AssertionError ngay, chứ không lặng lẽ trả thêm một payload nữa rồi để test xanh.
    """
    gemini.tra_json(PAYLOAD)
    yeu_cau = _yeu_cau("renewable")

    dau = service.translate(db, owner.id, yeu_cau)
    sau = service.translate(db, owner.id, yeu_cau)

    assert dau.cached is False
    assert sau.cached is True
    assert gemini.so_lan_goi == 1
    # Payload trả từ cache phải giống hệt payload lượt đầu — đọc từ JSONB ra, không phải
    # dựng lại từ đâu khác.
    assert sau.payload["meaning_vi"] == "tái tạo"
    assert _so_dong_cache(db) == 1


def test_cache_hit_tang_bo_dem_hit_count(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Ba lượt tra = 1 miss + 2 hit. Bộ đếm là 2, không phải 3."""
    gemini.tra_json(PAYLOAD)
    yeu_cau = _yeu_cau("renewable")

    service.translate(db, owner.id, yeu_cau)
    service.translate(db, owner.id, yeu_cau)
    service.translate(db, owner.id, yeu_cau)

    dong = _dong_cache_dau(db)
    assert dong is not None
    assert dong.hit_count == 2


def test_khac_ngu_canh_thi_khong_dung_chung_dong_cache(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Cùng một từ trong hai câu khác nhau có thể mang hai nghĩa khác nhau. Dùng chung một
    dòng cache là trả nghĩa của câu trước cho câu sau."""
    gemini.tra_json(PAYLOAD, lap=2)

    service.translate(db, owner.id, _yeu_cau("renewable", "context A"))
    service.translate(db, owner.id, _yeu_cau("renewable", "context B"))

    assert gemini.so_lan_goi == 2
    assert _so_dong_cache(db) == 2


def test_khoa_cache_khong_dung_do_khi_ranh_gioi_text_ngu_canh_dich_chuyen(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """("ab","c") và ("a","bc") — nối chuỗi trần sẽ ra cùng một material.

    Đây chính là lý do `_append_field` có tiền tố độ dài. Bỏ tiền tố đi thì test này đỏ, và
    không có test nào khác đỏ.
    """
    gemini.tra_json(PAYLOAD, lap=2)

    service.translate(db, owner.id, _yeu_cau("ab", "c"))
    service.translate(db, owner.id, _yeu_cau("a", "bc"))

    assert _so_dong_cache(db) == 2


# ── giới hạn độ dài ───────────────────────────────────────────────────────────


def test_text_vuot_1500_ky_tu_bi_tu_choi_truoc_khi_cham_gemini(
    db: Session,
    gemini: GeminiGia,
    service: TranslationService,
    owner: NguoiDungTest,
    khong_goi_gemini: Callable[[], None],
) -> None:
    """Chặn ở 1500 ký tự (ràng buộc #9), và chặn TRƯỚC Gemini.

    Vế thứ hai là phần đắt: một đoạn 20 nghìn ký tự lọt xuống Gemini vẫn "chạy được", chỉ là
    tốn tiền và chậm. Bản Java khẳng định bằng `verifyNoInteractions`.
    """
    qua_dai = "a" * (MAX_TEXT_LENGTH + 1)

    with pytest.raises(AppError) as ex:
        service.translate(db, owner.id, _yeu_cau(qua_dai))

    assert ex.value.code is ErrorCode.TEXT_TOO_LONG
    khong_goi_gemini()
    assert _so_dong_cache(db) == 0


def test_dung_1500_ky_tu_van_qua(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Chặn khi `> 1500`, không phải `>= 1500`. Lệch một ký tự ở đây là hai đầu nói hai luật
    khác nhau: extension cho gửi, backend từ chối."""
    gemini.tra_json(PAYLOAD)

    response = service.translate(db, owner.id, _yeu_cau("a" * MAX_TEXT_LENGTH))

    assert response.cached is False


# ── đối số gửi sang Gemini ────────────────────────────────────────────────────


def test_gemini_nhan_dung_schema_va_muc_timeout_cua_tuyen_da_do(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """Schema phải khớp tuyến đã dò ra, không phải một schema mặc định nào đó.

    Gửi nhầm schema thì Gemini vẫn trả JSON hợp lệ — hợp lệ theo schema SAI — nên payload
    lọt xuống cache và ra tới bubble mà không có lỗi nào. Mức timeout kiểm luôn ở đây vì
    `GeminiTimeout` cố ý không có giá trị mặc định: một lượt dịch lỡ chạy ở mức 30 giây
    không làm gì đỏ, chỉ bắt người dùng đợi gấp đôi khi Gemini chậm thật.
    """
    gemini.tra_json(PAYLOAD)

    service.translate(db, owner.id, _yeu_cau("renewable"))

    body = _body_gui_gemini(gemini)
    assert body["generationConfig"]["responseSchema"] == schema_for(
        Direction.EN_VI, Mode.WORD
    )
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    doc = gemini.requests[0].extensions["timeout"]["read"]
    assert doc == float(get_settings().gemini_timeout_seconds)


def test_prompt_gui_di_chua_ca_text_lan_ngu_canh(
    db: Session, gemini: GeminiGia, service: TranslationService, owner: NguoiDungTest
) -> None:
    """`{{TEXT}}` và `{{CONTEXT}}` phải được thay thật.

    Quên thay một trong hai vẫn ra một prompt trông bình thường và model vẫn trả JSON đúng
    schema — chỉ là nó đoán nghĩa của một từ mà nó không được cho biết là từ nào.
    """
    gemini.tra_json(PAYLOAD)

    service.translate(db, owner.id, _yeu_cau("renewable", "some context"))

    prompt = _body_gui_gemini(gemini)["contents"][0]["parts"][0]["text"]
    assert "renewable" in prompt
    assert "some context" in prompt
    assert "{{" not in prompt
