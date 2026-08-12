"""Bản port của `SrsServiceIT` — nghiệp vụ hàng đợi ôn tập.

Gọi thẳng `app.srs.service`, không qua HTTP: đây là tầng quyết định thứ tự hàng đợi và hạn
mức từ mới, hai thứ dễ port sai nhất và không lộ ra qua hình dạng JSON.

`BackgroundTasks()` truyền vào rồi KHÔNG chạy: `service.due` xếp lượt sinh mồi nhử nền cho
thẻ còn thiếu, nhưng ở tầng này không có ai chạy chúng, nên không có lượt gọi Gemini nào —
đúng vai trò `@MockitoBean GeminiClient` bên Java, mà không cần giả lập gì.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.srs import distractors
from app.srs import service as srs_service
from app.srs.models import CardState, Rating, ReviewLog, SrsCard, SrsDistractor
from app.vocabulary.models import VocabEntry
from tests.conftest import NguoiDungTest

HOM_NAY = date.today


def _card(
    db: Session,
    user_id: int,
    term: str,
    state: CardState,
    due: date,
    repetitions: int,
) -> SrsCard:
    """Một từ trong sổ + thẻ ôn của nó, y hệt helper `card(...)` bên Java.

    `user_id` là NOT NULL từ V6 — dựng entry mà quên chủ sở hữu là nổ ngay lúc insert.
    """
    entry = VocabEntry(
        user_id=user_id,
        term=term,
        lemma=term,
        lang="en",
        pos="verb",
        ipa="/test/",
        meaning_vi=f"nghĩa của {term}",
        collocations=[],
        examples=[],
    )
    db.add(entry)
    # `db` cố ý để autoflush=False, nên phải flush tay: không có id thì khoá ngoại của thẻ
    # vô nghĩa, và câu truy vấn ngay sau đó sẽ không thấy hàng vừa thêm.
    db.flush()

    card = SrsCard(
        vocab_entry_id=entry.id,
        state=state.value,
        due_date=due,
        repetitions=repetitions,
        interval_days=0 if repetitions == 0 else 6,
    )
    db.add(card)
    db.flush()
    return card


def _luu_moi_nhu(db: Session, card: SrsCard, prompt_version: int) -> None:
    db.add(
        SrsDistractor(
            vocab_entry_id=card.vocab_entry_id,
            vi_options=["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
            en_options=["aggravate", "exaggerate", "postpone"],
            prompt_version=prompt_version,
        )
    )
    db.flush()


def _due(db: Session, user_id: int, limit: int, new_limit: int) -> list:
    return srs_service.due(db, user_id, limit, new_limit, BackgroundTasks())


# ── hàng đợi ──────────────────────────────────────────────────────────────────


def test_hang_doi_gop_the_den_han_roi_moi_toi_the_moi(
    db: Session, owner: NguoiDungTest
) -> None:
    """Thẻ đến hạn đứng TRƯỚC thẻ mới trong cùng một hàng đợi.

    Thứ tự này là hợp đồng với side panel: ôn nợ cũ trước rồi mới học từ mới. Đảo lại thì
    người dùng học thêm từ mới trong khi nợ ôn dồn lên, và không có gì báo.
    """
    _card(db, owner.id, "alpha", CardState.REVIEW, date.today() - timedelta(days=1), 3)
    _card(db, owner.id, "bravo", CardState.NEW, date.today(), 0)

    queue = _due(db, owner.id, 50, 30)

    assert len(queue) == 2
    assert queue[0].term == "alpha"
    assert queue[1].term == "bravo"
    # Dữ liệu vocab được gộp sẵn vào DTO — panel không phải gọi thêm lượt nào.
    assert queue[0].meaning_vi == "nghĩa của alpha"


def test_the_chua_toi_han_khong_nam_trong_hang_doi(db: Session, owner: NguoiDungTest) -> None:
    """Thẻ due sau hôm nay không được lôi ra sớm — nếu không thì khoảng lặp SM-2 vô nghĩa."""
    _card(db, owner.id, "later", CardState.REVIEW, date.today() + timedelta(days=3), 2)

    assert _due(db, owner.id, 50, 30) == []


def test_gioi_han_tu_moi_chan_dung_so_the_new_the_den_han_khong_bi_chan(
    db: Session, owner: NguoiDungTest
) -> None:
    """`newLimit` chỉ áp cho thẻ NEW. Thẻ đã đến hạn là nợ phải trả, không có hạn mức."""
    for i in range(5):
        _card(db, owner.id, f"new{i}", CardState.NEW, date.today(), 0)
    for i in range(4):
        _card(db, owner.id, f"due{i}", CardState.REVIEW, date.today(), 3)

    queue = _due(db, owner.id, 50, 2)

    assert len(queue) == 6  # 4 đến hạn (không giới hạn) + 2 thẻ mới
    assert len([c for c in queue if c.state is CardState.NEW]) == 2


def test_so_tu_moi_da_hoc_hom_nay_bi_tru_khoi_han_muc_con_lai(
    db: Session, owner: NguoiDungTest
) -> None:
    """Hạn mức là "mỗi NGÀY", không phải "mỗi lần mở tab".

    Đã học 1 từ mới hôm nay, hạn mức 1 → mở lại tab không được phát thêm từ mới nào. Không
    trừ phần đã học thì người dùng cứ đóng/mở panel là lại được cấp thêm quota.
    """
    learned = _card(db, owner.id, "done", CardState.NEW, date.today(), 0)
    srs_service.review(db, owner.id, learned.id, Rating.GOOD)  # dùng hết 1 suất từ mới

    _card(db, owner.id, "waiting", CardState.NEW, date.today(), 0)

    assert _due(db, owner.id, 50, 1) == []


def test_new_limit_bang_0_la_khong_gioi_han(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`0` là cách người dùng tắt hẳn hạn mức từ ô "Từ mới mỗi ngày" ở Options.

    Trước thay đổi này, `0` nghĩa là "không được học từ mới nào" — đúng nghĩa đen nhưng vô
    dụng, vì không ai đặt hạn mức 0 để tự cấm mình học."""
    for i in range(7):
        _card(db, owner.id, f"word{i}", CardState.NEW, date.today(), 0)

    ra = client.get("/api/srs/due?limit=50&newLimit=0", headers=owner.headers)

    assert ra.status_code == 200
    assert len(ra.json()) == 7


def test_new_limit_duong_van_chan_dung(client: Any, db: Session, owner: NguoiDungTest) -> None:
    for i in range(7):
        _card(db, owner.id, f"word{i}", CardState.NEW, date.today(), 0)

    ra = client.get("/api/srs/due?limit=50&newLimit=3", headers=owner.headers)

    assert len(ra.json()) == 3


def test_luot_practice_khong_tinh_vao_han_muc_tu_moi(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`count_introduced_since` nhận diện lượt đầu đời bằng `prev_interval == 0`. Dòng
    PRACTICE không được lọt vào phép đếm đó, nếu không luyện thêm sẽ ăn mất hạn mức từ mới
    của ngày hôm sau."""
    card = _card(db, owner.id, "mitigate", CardState.REVIEW, date.today(), 2)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
            "VALUES (:c, 'GOOD', 0, 0, 'PRACTICE')"
        ),
        {"c": card.id},
    )
    for i in range(3):
        _card(db, owner.id, f"word{i}", CardState.NEW, date.today(), 0)

    ra = client.get("/api/srs/due?limit=50&newLimit=3", headers=owner.headers)

    # 3 thẻ mới + 1 thẻ đã học nếu nó đến hạn; điều đang kiểm là hạn mức từ mới KHÔNG bị
    # dòng PRACTICE ăn mất, tức vẫn đủ 3 thẻ NEW.
    assert sum(1 for c in ra.json() if c["state"] == "NEW") == 3


# ── review ────────────────────────────────────────────────────────────────────


def test_review_cap_nhat_the_ghi_review_log_va_tra_lich_ke_tiep(
    db: Session, owner: NguoiDungTest
) -> None:
    """Một lượt ôn phải để lại BA dấu vết: response, thẻ đã cập nhật, và một dòng nhật ký.

    Thiếu dòng nhật ký thì `countIntroducedSince` đếm hụt và hạn mức từ mới mỗi ngày hỏng
    theo — mà không có gì đỏ.
    """
    card = _card(db, owner.id, "mitigate", CardState.NEW, date.today(), 0)

    response = srs_service.review(db, owner.id, card.id, Rating.GOOD)

    assert response.interval_days == 1
    assert response.next_due_date == date.today() + timedelta(days=1)

    db.expire_all()
    updated = db.get(SrsCard, card.id)
    assert updated is not None
    assert updated.state == CardState.REVIEW.value
    assert updated.repetitions == 1

    logs = list(db.scalars(select(ReviewLog)).all())
    assert len(logs) == 1
    assert logs[0].prev_interval == 0
    assert logs[0].new_interval == 1
    assert logs[0].rating == Rating.GOOD.value


def test_review_the_khong_ton_tai_nem_not_found(db: Session, owner: NguoiDungTest) -> None:
    """NOT_FOUND kèm chính id đã hỏi — thông điệp mơ hồ ở đây là thứ khiến gỡ lỗi phải mò."""
    with pytest.raises(AppError) as loi:
        srs_service.review(db, owner.id, 999_999, Rating.GOOD)

    assert loi.value.code is ErrorCode.NOT_FOUND
    assert "999999" in loi.value.message


# ── stats ─────────────────────────────────────────────────────────────────────


def test_stats_due_count_khop_dung_do_dai_hang_doi_nguoi_dung_se_thay(
    db: Session, owner: NguoiDungTest
) -> None:
    """Badge và hàng đợi phải nói cùng một con số khi `limit` chưa phải ràng buộc chặn."""
    for i in range(3):
        _card(db, owner.id, f"new{i}", CardState.NEW, date.today(), 0)
    _card(db, owner.id, "due0", CardState.REVIEW, date.today(), 4)

    stats = srs_service.stats(db, owner.id, 2)

    assert stats.due_count == 3  # 1 đến hạn + 2 thẻ mới được phép
    assert stats.due_count == len(_due(db, owner.id, 50, 2))
    assert stats.new_count == 3
    assert stats.learned_count == 1


def test_due_count_dem_theo_han_khong_bi_limit_cat(db: Session, owner: NguoiDungTest) -> None:
    """Ghim lại ranh giới của bất biến "dueCount == độ dài hàng đợi".

    Nó chỉ đúng khi `limit` CHƯA phải ràng buộc chặn. Vượt limit thì badge cố tình báo tổng
    nợ thật (5) trong khi hàng đợi bị cắt còn 2 — nếu sau này ai đó "sửa" stats cho khớp
    hàng đợi thì badge sẽ nói dối người dùng là họ chỉ còn 2 thẻ.
    """
    for i in range(5):
        _card(db, owner.id, f"due{i}", CardState.REVIEW, date.today(), 3)

    assert len(_due(db, owner.id, 2, 0)) == 2
    assert srs_service.stats(db, owner.id, 0).due_count == 5


# ── mồi nhử gộp vào DTO ───────────────────────────────────────────────────────


def test_moi_nhu_da_sinh_di_vao_dung_mang_cua_no(db: Session, owner: NguoiDungTest) -> None:
    """vi ra `viDistractors`, en ra `enDistractors`.

    Ca rỗng ở test router không phân biệt được hai mảng bị map ngược nhau; chỉ ca có dữ liệu
    thật mới ghim được chiều nào ra field nào.
    """
    card = _card(db, owner.id, "mitigate", CardState.REVIEW, date.today(), 3)
    _luu_moi_nhu(db, card, distractors.current_prompt_version())

    dto = _due(db, owner.id, 50, 30)[0]

    assert dto.vi_distractors == ["làm trầm trọng thêm", "phóng đại", "trì hoãn"]
    assert dto.en_distractors == ["aggravate", "exaggerate", "postpone"]


def test_bo_qua_moi_nhu_sinh_bang_version_prompt_cu(db: Session, owner: NguoiDungTest) -> None:
    """Bản ghi version cũ coi như không có, và trả MẢNG RỖNG chứ không phải null.

    Đây là cơ chế duy nhất làm mồi nhử cũ hết hiệu lực khi tăng `version:` trong prompt
    (ràng buộc #5). Trả null thay vì mảng rỗng thì side panel vỡ ngay ở `.length`.
    """
    card = _card(db, owner.id, "mitigate", CardState.REVIEW, date.today(), 3)
    _luu_moi_nhu(db, card, distractors.current_prompt_version() - 1)

    dto = _due(db, owner.id, 50, 30)[0]

    assert dto.vi_distractors == []
    assert dto.en_distractors == []


# ── Ba ca dưới đây KHÔNG có trong bộ test Java ────────────────────────────────
# Chúng canh phần `requestMissing` mà bản Java chỉ chạm gián tiếp qua việc phải
# `@MockitoBean GeminiClient` trong SrsControllerIT.


def test_the_thieu_moi_nhu_duoc_xep_mot_luot_sinh_nen(db: Session, owner: NguoiDungTest) -> None:
    """Thẻ chưa có mồi nhử còn hiệu lực thì `due()` xếp một lượt sinh nền cho nó."""
    _card(db, owner.id, "mitigate", CardState.REVIEW, date.today(), 3)
    tasks = BackgroundTasks()

    srs_service.due(db, owner.id, 50, 30, tasks)

    assert len(tasks.tasks) == 1


def test_the_da_co_moi_nhu_con_hieu_luc_khong_bi_sinh_lai(
    db: Session, owner: NguoiDungTest
) -> None:
    """Sinh lại bộ đã có là đốt quota Gemini cho một kết quả y hệt."""
    card = _card(db, owner.id, "mitigate", CardState.REVIEW, date.today(), 3)
    _luu_moi_nhu(db, card, distractors.current_prompt_version())
    tasks = BackgroundTasks()

    srs_service.due(db, owner.id, 50, 30, tasks)

    assert tasks.tasks == []


def test_so_luot_sinh_nen_chan_o_muc_toi_da_moi_lan_goi(
    db: Session, owner: NguoiDungTest
) -> None:
    """Trần `MAX_BACKFILL_PER_CALL`: một sổ lớn không được bắn cả trăm call mỗi lần mở tab."""
    tong = srs_service.MAX_BACKFILL_PER_CALL + 5
    for i in range(tong):
        _card(db, owner.id, f"due{i}", CardState.REVIEW, date.today(), 3)
    tasks = BackgroundTasks()

    queue = srs_service.due(db, owner.id, 50, 30, tasks)

    assert len(queue) == tong
    assert len(tasks.tasks) == srs_service.MAX_BACKFILL_PER_CALL


def test_hang_doi_chi_chua_the_cua_chinh_minh_khong_can_loc_lai_o_tang_moi_nhu(
    db: Session, owner: NguoiDungTest
) -> None:
    """`find_fresh_distractors` cố ý không lọc `user_id` — an toàn vì id luôn đến từ hàng đợi
    của chính user, không bao giờ từ client.

    Test này ghim tiền đề đó: hàng đợi trả về đúng thẻ của user, nên tập id truyền xuống
    tầng mồi nhử đã sạch.
    """
    nguoi_khac = int(
        db.execute(
            text(
                "INSERT INTO app_user (email, display_name) "
                "VALUES ('nguoi-khac@test.local', 'Người khác') RETURNING id"
            )
        ).scalar_one()
    )
    _card(db, owner.id, "cua-toi", CardState.REVIEW, date.today(), 3)
    _card(db, nguoi_khac, "cua-nguoi-khac", CardState.REVIEW, date.today(), 3)

    queue = _due(db, owner.id, 50, 30)

    assert [c.term for c in queue] == ["cua-toi"]
