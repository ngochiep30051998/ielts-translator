"""Bản port của `SrsSchedulerTest`, cộng hai ca bản Java không có (xem cuối file).

Hàm thuần, không chạm DB — chạy trong mili giây.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.srs.models import CardState, Rating, SrsCard
from app.srs.scheduler import _round_half_up, next_schedule

TODAY = date(2026, 8, 6)


def the(
    ease: float, interval: int, repetitions: int, lapses: int, state: CardState
) -> SrsCard:
    card = SrsCard()
    card.ease_factor = ease
    card.interval_days = interval
    card.repetitions = repetitions
    card.lapses = lapses
    card.state = state.value
    return card


@pytest.mark.parametrize(
    ("rating", "ease_mong_doi"),
    [
        (Rating.AGAIN, 2.18),
        (Rating.HARD, 2.36),
        (Rating.GOOD, 2.50),
        (Rating.EASY, 2.60),
    ],
)
def test_delta_ease_factor_dung_cho_tung_rating(rating: Rating, ease_mong_doi: float) -> None:
    """ΔEF = 0.1 − (3−q)·(0.08 + (3−q)·0.02).

    Đây là bảng số chốt trong spec — AGAIN là −0.32, KHÔNG phải −0.20 như design gốc
    2026-08-03 viết nhầm.
    """
    ket_qua = next_schedule(the(2.5, 10, 5, 0, CardState.REVIEW), rating, TODAY)

    assert ket_qua.ease_factor == pytest.approx(ease_mong_doi, abs=1e-4)


def test_ease_factor_khong_bao_gio_tut_duoi_san() -> None:
    """Sàn 1.3, dù bấm Lại liên tục."""
    card = the(1.4, 10, 5, 0, CardState.REVIEW)

    for _ in range(10):
        ket_qua = next_schedule(card, Rating.AGAIN, TODAY)
        card.ease_factor = ket_qua.ease_factor
        card.interval_days = ket_qua.interval_days
        card.repetitions = ket_qua.repetitions
        card.lapses = ket_qua.lapses

    assert card.ease_factor == 1.3


def test_bam_lai() -> None:
    """interval về 1, repetitions về 0, lapses tăng, state RELEARNING."""
    ket_qua = next_schedule(the(2.5, 30, 4, 2, CardState.REVIEW), Rating.AGAIN, TODAY)

    assert ket_qua.interval_days == 1
    assert ket_qua.repetitions == 0
    assert ket_qua.lapses == 3
    assert ket_qua.state is CardState.RELEARNING
    assert ket_qua.due_date == TODAY + timedelta(days=1)


def test_bam_kho() -> None:
    """interval × 1.2, repetitions vẫn tăng, lapses không đổi."""
    ket_qua = next_schedule(the(2.5, 10, 4, 2, CardState.REVIEW), Rating.HARD, TODAY)

    assert ket_qua.interval_days == 12
    assert ket_qua.repetitions == 5
    assert ket_qua.lapses == 2
    assert ket_qua.state is CardState.REVIEW


@pytest.mark.parametrize(
    ("repetitions", "interval", "mong_doi"),
    [
        (0, 0, 1),  # thẻ mới → 1 ngày
        (1, 1, 6),  # lượt thứ hai → 6 ngày
        (2, 6, 15),  # lượt thứ ba trở đi → round(6 × 2.5)
    ],
)
def test_bam_tot(repetitions: int, interval: int, mong_doi: int) -> None:
    """1 ngày → 6 ngày → nhân EF."""
    trang_thai = CardState.NEW if repetitions == 0 else CardState.REVIEW
    ket_qua = next_schedule(
        the(2.5, interval, repetitions, 0, trang_thai), Rating.GOOD, TODAY
    )

    assert ket_qua.interval_days == mong_doi
    assert ket_qua.repetitions == repetitions + 1
    assert ket_qua.state is CardState.REVIEW


def test_bam_de_tren_the_da_on() -> None:
    """Nhân EF MỚI rồi nhân thêm 1.3: EF mới = 2.6 → round(6 × 2.6) = 16 → round(16 × 1.3) = 21."""
    ket_qua = next_schedule(the(2.5, 6, 2, 0, CardState.REVIEW), Rating.EASY, TODAY)

    assert ket_qua.ease_factor == pytest.approx(2.6, abs=1e-4)
    assert ket_qua.interval_days == 21


def test_bam_de_tren_the_moi_van_ra_mot_ngay() -> None:
    """round(1 × 1.3) = 1 — đúng spec, không phải bug."""
    ket_qua = next_schedule(the(2.5, 0, 0, 0, CardState.NEW), Rating.EASY, TODAY)

    assert ket_qua.interval_days == 1


def test_interval_khong_bao_gio_nho_hon_mot() -> None:
    """round(0 × 1.2) = 0 → nâng lên 1."""
    ket_qua = next_schedule(the(2.5, 0, 3, 0, CardState.NEW), Rating.HARD, TODAY)

    assert ket_qua.interval_days == 1


def test_the_relearning_bam_tot_quay_lai_review() -> None:
    ket_qua = next_schedule(the(2.0, 1, 0, 1, CardState.RELEARNING), Rating.GOOD, TODAY)

    assert ket_qua.state is CardState.REVIEW
    assert ket_qua.interval_days == 1  # repetitions về 1 → 1 ngày


# ── Hai ca dưới đây KHÔNG có trong bộ test Java ────────────────────────────────
# Chúng canh một lớp lỗi chỉ tồn tại ở bản Python.


@pytest.mark.parametrize(
    ("gia_tri", "mong_doi"),
    [(0.5, 1), (1.5, 2), (2.5, 3), (12.5, 13), (16.5, 17), (-0.5, 0), (15.4, 15), (15.6, 16)],
)
def test_lam_tron_nua_len_giong_java(gia_tri: float, mong_doi: int) -> None:
    """`Math.round` của Java là `floor(x + 0.5)`; `round()` của Python làm tròn về số CHẴN.

    `round(2.5)` ra 2 ở Python nhưng 3 ở Java. Không ca nào trong bộ test Java chạm đúng
    biên `.5`, nên lỗi này sẽ đi lọt qua toàn bộ bản port và chỉ hiện ra dưới dạng lịch ôn
    lệch dần một ngày so với backend cũ — không có gì đỏ, không ai báo.
    """
    assert _round_half_up(gia_tri) == mong_doi


def test_bien_nua_ngay_trong_cong_thuc_that() -> None:
    """Ca chạm biên đi qua đúng đường tính thật, không chỉ qua hàm làm tròn.

    interval 5 × EF 2.5 = 12.5 → Java cho 13. Python `round()` sẽ cho 12.
    """
    ket_qua = next_schedule(the(2.5, 5, 3, 0, CardState.REVIEW), Rating.GOOD, TODAY)

    assert ket_qua.interval_days == 13
    assert ket_qua.due_date == TODAY + timedelta(days=13)
