"""Nghiệp vụ ôn tập: hàng đợi due, hạn mức từ mới mỗi ngày, ghi nhận một lượt review."""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorCode
from app.srs import distractors
from app.srs import repository as repo
from app.srs.models import (
    CardDto,
    CardState,
    Rating,
    ReviewMode,
    ReviewResponse,
    SrsCard,
    SrsDistractor,
    SrsStatsDto,
)
from app.srs.scheduler import next_schedule
from app.vocabulary.models import VocabEntry

#: Số từ được bù mồi nhử mỗi lần mở tab ôn. Chặn để một sổ lớn không bắn cả trăm call.
MAX_BACKFILL_PER_CALL = 10


def due(
    db: Session, user_id: int, limit: int, new_limit: int, tasks: BackgroundTasks
) -> list[CardDto]:
    """Hàng đợi ôn: TOÀN BỘ thẻ đã đến hạn (không giới hạn), rồi mới tới thẻ mới trong phần
    hạn mức còn lại của ngày. Tổng cắt ở `limit`.
    """
    queue = repo.find_due_cards(db, user_id, date.today(), limit)

    room = min(limit - len(queue), _remaining_new_today(db, user_id, new_limit))
    if room > 0:
        queue = queue + repo.find_new_cards(db, user_id, room)

    by_vocab_id = _load_fresh_distractors(db, queue)
    _request_missing(tasks, db, queue, by_vocab_id)

    return [_to_dto(card, entry, by_vocab_id) for card, entry in queue]


def stats(db: Session, user_id: int, new_limit: int) -> SrsStatsDto:
    due_now = repo.count_due(db, user_id, date.today())
    new_total = repo.count_by_state(db, user_id, CardState.NEW)
    new_allowed = min(new_total, _remaining_new_today(db, user_id, new_limit))
    return SrsStatsDto(
        due_count=due_now + new_allowed,
        new_count=new_total,
        learned_count=repo.count_learned(db, user_id),
    )


def review(db: Session, user_id: int, card_id: int, rating: Rating) -> ReviewResponse:
    # find_owned_card chứ không tra theo id trần: thẻ của người khác trả NOT_FOUND, không
    # phải FORBIDDEN — FORBIDDEN xác nhận id đó có tồn tại, tức là một kênh dò id.
    card = repo.find_owned_card(db, card_id, user_id)
    if card is None:
        raise AppError.of(ErrorCode.NOT_FOUND, f"Không tìm thấy thẻ id={card_id}")

    prev_interval = card.interval_days
    nxt = next_schedule(card, rating, date.today())

    card.ease_factor = nxt.ease_factor
    card.interval_days = nxt.interval_days
    card.repetitions = nxt.repetitions
    card.lapses = nxt.lapses
    card.due_date = nxt.due_date
    card.state = nxt.state.value

    repo.insert_review_log(
        db,
        card_id=card.id,
        rating=rating,
        prev_interval=prev_interval,
        new_interval=nxt.interval_days,
        mode=ReviewMode.SCHEDULED,
    )

    return ReviewResponse(
        next_due_date=nxt.due_date,
        interval_days=nxt.interval_days,
        ease_factor=nxt.ease_factor,
    )


def _load_fresh_distractors(
    db: Session, queue: list[tuple[SrsCard, VocabEntry]]
) -> dict[int, SrsDistractor]:
    """Chỉ lấy mồi nhử còn hiệu lực với version prompt hiện hành."""
    if not queue:
        return {}
    vocab_ids = [entry.id for _, entry in queue]
    rows = repo.find_fresh_distractors(db, vocab_ids, distractors.current_prompt_version())
    return {row.vocab_entry_id: row for row in rows}


def _request_missing(
    tasks: BackgroundTasks,
    db: Session,
    queue: list[tuple[SrsCard, VocabEntry]],
    by_vocab_id: dict[int, SrsDistractor],
) -> None:
    """Xếp lượt sinh nền cho thẻ chưa có mồi nhử rồi trả hàng đợi về NGAY — không chờ.

    Lượt ôn lúc này vẫn chạy được nhờ panel tự bù mồi nhử từ thẻ khác; lượt sau đã có bộ
    thật.

    Đây cũng là đường bù cho từ lưu từ trước khi có tính năng này, và cho mọi từ có mồi nhử
    hết hiệu lực sau khi tăng version prompt.
    """
    requested = 0
    for _, entry in queue:
        if requested >= MAX_BACKFILL_PER_CALL:
            return
        if entry.id not in by_vocab_id:
            distractors.schedule(tasks, db, entry.id)
            requested += 1


def _remaining_new_today(db: Session, user_id: int, new_limit: int) -> int:
    """Hạn mức từ mới còn lại của hôm nay, không bao giờ âm.

    Mốc nửa đêm tính theo giờ HỆ THỐNG (`astimezone()` gắn offset local vào), đúng như
    `LocalDate.now().atStartOfDay(ZoneId.systemDefault())` bên Java — và cùng lý do biến TZ
    được truyền vào container: ngày phải đổi lúc nửa đêm giờ Việt Nam. Gửi một mốc thời gian
    KHÔNG có offset xuống Postgres thì nó tự diễn giải theo timezone của session, lệch mất
    vài giờ mà không có gì báo.
    """
    start_of_day = datetime.combine(date.today(), time.min).astimezone()
    introduced = repo.count_introduced_since(db, user_id, start_of_day)
    return max(0, new_limit - introduced)


def _to_dto(card: SrsCard, entry: VocabEntry, by_vocab_id: dict[int, SrsDistractor]) -> CardDto:
    row = by_vocab_id.get(entry.id)
    return CardDto(
        id=card.id,
        vocab_entry_id=entry.id,
        term=entry.term,
        ipa=entry.ipa,
        pos=entry.pos,
        meaning_vi=entry.meaning_vi,
        definition_en=entry.definition_en,
        cefr=entry.cefr,
        band_level=entry.band_level,
        collocations=entry.collocations,
        examples=entry.examples,
        state=CardState(card.state),
        due_date=card.due_date,
        vi_distractors=[] if row is None else list(row.vi_options),
        en_distractors=[] if row is None else list(row.en_options),
    )
