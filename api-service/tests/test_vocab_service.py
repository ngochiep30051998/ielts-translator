"""Bản port của `VocabServiceIT` — nghiệp vụ sổ từ, gọi thẳng tầng service.

Bên Java, `@BeforeEach reset()` xoá sạch `vocab_entry`; ở đây fixture `_don_sach` của
`conftest.py` đã TRUNCATE trước MỖI test nên không cần lặp lại.

Hai chi tiết khác bản Java, không phải tuỳ tiện:

* Session test dựng với `autoflush=False`, nên chỗ nào khẳng định dữ liệu ĐÃ XUỐNG bảng mà
  đường code không tự flush (nhánh gộp tag, nhánh xoá) thì test gọi `db.flush()` trước khi
  đọc. Trong production `get_db` commit ở cuối request nên chuyện này không lộ ra.
* Java so `repository.count()`; ở đây đếm bằng SQL thô để khẳng định đúng thứ nằm trong
  bảng chứ không phải thứ đang nằm trong identity map của SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import models as _auth_models  # noqa: F401  (đăng ký bảng app_user vào metadata)
from app.common.errors import AppError, ErrorCode
from app.vocabulary import service
from app.vocabulary.models import SaveVocabRequest, SaveVocabResponse
from tests.conftest import NguoiDungTest


def _request(
    term: str, pos: str, nghia: str, tags: Sequence[str] = ()
) -> SaveVocabRequest:
    """Đúng bộ dữ liệu mà `VocabServiceIT.request(...)` dựng."""
    return SaveVocabRequest(
        term=term,
        lemma=term,
        lang="en",
        pos=pos,
        ipa="/test/",
        meaning_vi=nghia,
        definition_en="an English definition",
        cefr="B2",
        band_level="6.5",
        tags=list(tags),
        source_url="https://example.com",
        source_sentence="A source sentence.",
        collocations=["renewable energy"],
        examples=[],
    )


def _so_tu(db: Session) -> int:
    db.flush()
    return int(db.execute(text("SELECT count(*) FROM vocab_entry")).scalar_one())


def _luu(
    db: Session,
    user_id: int,
    request: SaveVocabRequest,
    tasks: BackgroundTasks | None = None,
) -> SaveVocabResponse:
    """Gọi `service.save` với một hàng đợi tác vụ nền RỖNG.

    `BackgroundTasks` do FastAPI cấp cho handler; ngoài request nó chỉ là một cái danh sách.
    Không ai chạy nó ở đây, nên lượt sinh mồi nhử không bao giờ khởi động và test service
    không phụ thuộc vào Gemini — đúng ranh giới mà `DistractorGenerator` bên Java giữ nhờ
    `@Async`.
    """
    return service.save(db, user_id, request, tasks or BackgroundTasks())


# ── lưu ───────────────────────────────────────────────────────────────────────


def test_luu_tu_moi(db: Session, owner: NguoiDungTest) -> None:
    """Lưu lần đầu: có id, `alreadyExists=false`, đúng một hàng trong bảng."""
    response = _luu(db, owner.id, _request("renewable", "adj", "tái tạo"))

    assert response.id is not None
    assert response.already_exists is False
    assert _so_tu(db) == 1


def test_luu_tu_moi_ghi_dung_tung_cot(db: Session, owner: NguoiDungTest) -> None:
    """Chốt CẢ hàng vừa ghi, không chỉ số lượng.

    `save()` map 14 field bằng tay; hoán vị hai cột cùng kiểu chuỗi — `lemma` với `lang`,
    `cefr` với `band_level` — không làm test nào bên Java đỏ, nhưng làm sổ từ của người
    dùng sai vĩnh viễn.
    """
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo", ["environment"]))
    db.flush()

    hang = db.execute(
        text(
            "SELECT user_id, term, lemma, lang, pos, ipa, meaning_vi, definition_en, "
            "cefr, band_level, tags, source_url, source_sentence, collocations, examples "
            "FROM vocab_entry"
        )
    ).one()

    assert tuple(hang) == (
        owner.id,
        "renewable",
        "renewable",
        "en",
        "adj",
        "/test/",
        "tái tạo",
        "an English definition",
        "B2",
        "6.5",
        ["environment"],
        "https://example.com",
        "A source sentence.",
        ["renewable energy"],
        [],
    )


def test_luu_lai_cung_term_va_pos_bao_da_ton_tai_va_khong_nhan_ban(
    db: Session, owner: NguoiDungTest
) -> None:
    """Lưu trùng trả `alreadyExists=true` CHỨ KHÔNG nổ lỗi — và trả về đúng id cũ để UI
    còn mở được từ đó."""
    first = _luu(db, owner.id, _request("renewable", "adj", "tái tạo"))
    second = _luu(db, owner.id, _request("renewable", "adj", "nghĩa khác"))

    assert second.already_exists is True
    assert second.id == first.id
    assert _so_tu(db) == 1


def test_tu_da_co_giu_nguyen_nghia_cu(db: Session, owner: NguoiDungTest) -> None:
    """Nội dung cũ KHÔNG bị ghi đè.

    Người dùng có thể đã sửa tay nghĩa của từ; lưu lại cùng từ đó từ một trang khác không
    được phép xoá công sức đó bằng bản dịch máy mới.
    """
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo"))
    _luu(db, owner.id, _request("renewable", "adj", "nghĩa bị ghi đè"))
    db.flush()

    assert db.execute(text("SELECT meaning_vi FROM vocab_entry")).scalar_one() == "tái tạo"


def test_luu_lai_gop_them_tag_moi(db: Session, owner: NguoiDungTest) -> None:
    """Tag thì NGƯỢC LẠI: tag mới được gộp vào tag cũ, bỏ trùng.

    Thứ tự khẳng định ở đây chặt hơn bản Java (`containsExactlyInAnyOrder`) vì
    `LinkedHashSet` bên Java — và `dict.fromkeys` bên này — đều giữ thứ tự xuất hiện.
    """
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo", ["environment"]))
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo", ["environment", "writing"]))
    db.flush()

    assert db.execute(text("SELECT tags FROM vocab_entry")).scalar_one() == [
        "environment",
        "writing",
    ]


def test_chi_nhanh_luu_moi_xep_viec_chay_sau(db: Session, owner: NguoiDungTest) -> None:
    """Bản Java chỉ phát `VocabEntrySavedEvent` ở nhánh lưu MỚI. Bất biến đó phải giữ.

    Phát cả ở nhánh trùng thì mỗi lần người dùng bấm lưu lại một từ cũ là một lượt gọi
    Gemini nữa để sinh mồi nhử — âm thầm đốt hạn mức mà chẳng thêm dữ liệu gì.
    """
    tasks = BackgroundTasks()
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo"), tasks)
    assert len(tasks.tasks) == 1

    lan_hai = BackgroundTasks()
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo"), lan_hai)
    assert lan_hai.tasks == []

    # Và thẻ ôn cũng không bị tạo lần hai (lịch ôn không bị đặt lại từ đầu).
    db.flush()
    assert db.execute(text("SELECT count(*) FROM srs_card")).scalar_one() == 1


def test_cung_term_khac_pos_la_hai_muc_rieng(db: Session, owner: NguoiDungTest) -> None:
    """"run" (động từ) và "run" (danh từ) là hai từ khác nhau với người học — khoá trùng
    là (user, term, pos) chứ không phải (user, term)."""
    _luu(db, owner.id, _request("run", "v", "chạy"))
    _luu(db, owner.id, _request("run", "n", "lượt chạy"))

    assert _so_tu(db) == 2


# ── tìm kiếm ──────────────────────────────────────────────────────────────────


def test_tim_theo_term_khong_phan_biet_hoa_thuong(
    db: Session, owner: NguoiDungTest
) -> None:
    """Khớp CHUỖI CON và bỏ qua hoa/thường: gõ "RENEW" phải ra "renewable"."""
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo"))
    _luu(db, owner.id, _request("mitigate", "v", "giảm nhẹ"))

    found = service.search(db, owner.id, "RENEW", None, untagged=False, page=0, size=20).content

    assert len(found) == 1
    assert found[0].term == "renewable"


def test_tim_theo_nghia_tieng_viet(db: Session, owner: NguoiDungTest) -> None:
    """Ô tìm kiếm quét cả `meaning_vi`, không chỉ `term` — người học thường nhớ nghĩa
    trước khi nhớ mặt chữ."""
    _luu(db, owner.id, _request("mitigate", "v", "giảm nhẹ"))

    trang = service.search(db, owner.id, "giảm", None, untagged=False, page=0, size=20)

    assert len(trang.content) == 1


def test_loc_theo_tag(db: Session, owner: NguoiDungTest) -> None:
    _luu(db, owner.id, _request("renewable", "adj", "tái tạo", ["environment"]))
    _luu(db, owner.id, _request("mitigate", "v", "giảm nhẹ", ["writing"]))

    found = service.search(db, owner.id, None, "writing", untagged=False, page=0, size=20).content

    assert len(found) == 1
    assert found[0].term == "mitigate"


def test_khong_loc_gi_tra_tat_ca_moi_nhat_truoc(db: Session, owner: NguoiDungTest) -> None:
    """Từ vừa lưu phải đứng đầu danh sách — đó là thứ người dùng vừa làm và muốn thấy ngay.

    Đây cũng là chỗ tiêu chí phụ `id DESC` kiếm được tiền: `created_at` là `DEFAULT now()`
    của Postgres, tức thời điểm BẮT ĐẦU TRANSACTION, nên hai hàng thêm trong cùng một
    transaction có mốc thời gian GIỐNG HỆT nhau. Không có tiêu chí phụ thì thứ tự là tuỳ
    hứng và test này đỏ lúc xanh lúc.
    """
    _luu(db, owner.id, _request("first", "n", "một"))
    _luu(db, owner.id, _request("second", "n", "hai"))

    found = service.search(db, owner.id, None, None, untagged=False, page=0, size=20).content

    assert [e.term for e in found] == ["second", "first"]


# ── đọc một từ · xoá ──────────────────────────────────────────────────────────


def test_find_by_id_tra_ve_tu(db: Session, owner: NguoiDungTest) -> None:
    entry_id = _luu(db, owner.id, _request("renewable", "adj", "tái tạo")).id

    assert service.find_by_id(db, owner.id, entry_id).term == "renewable"


def test_xoa_tu(db: Session, owner: NguoiDungTest) -> None:
    entry_id = _luu(db, owner.id, _request("renewable", "adj", "tái tạo")).id

    service.delete(db, owner.id, entry_id)

    assert _so_tu(db) == 0


def test_xoa_id_khong_ton_tai_nem_not_found(db: Session, owner: NguoiDungTest) -> None:
    """NOT_FOUND, không phải một `Exception` trần: `GlobalExceptionHandler` map mã này
    sang 404 và extension phân biệt lỗi vĩnh viễn với lỗi retry được nhờ chính nó."""
    with pytest.raises(AppError) as loi:
        service.delete(db, owner.id, 999999)

    assert loi.value.code is ErrorCode.NOT_FOUND
    assert loi.value.status() == 404
    assert loi.value.retryable is False
