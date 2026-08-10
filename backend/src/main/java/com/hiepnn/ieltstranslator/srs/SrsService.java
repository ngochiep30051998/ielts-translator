package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.srs.dto.CardDto;
import com.hiepnn.ieltstranslator.srs.dto.ReviewResponse;
import com.hiepnn.ieltstranslator.srs.dto.SrsStatsDto;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class SrsService {

    /** Số từ được bù mồi nhử mỗi lần mở tab ôn. Chặn để một sổ lớn không bắn cả trăm call. */
    private static final int MAX_BACKFILL_PER_CALL = 10;

    private final SrsCardRepository cards;
    private final ReviewLogRepository logs;
    private final SrsScheduler scheduler;
    private final SrsDistractorRepository distractors;
    private final DistractorGenerator generator;

    public SrsService(SrsCardRepository cards, ReviewLogRepository logs, SrsScheduler scheduler,
                      SrsDistractorRepository distractors, DistractorGenerator generator) {
        this.cards = cards;
        this.logs = logs;
        this.scheduler = scheduler;
        this.distractors = distractors;
        this.generator = generator;
    }

    /**
     * Hàng đợi ôn: TOÀN BỘ thẻ đã đến hạn (không giới hạn), rồi mới tới thẻ mới trong
     * phần hạn mức còn lại của ngày. Tổng cắt ở {@code limit}.
     */
    @Transactional(readOnly = true)
    public List<CardDto> due(Long userId, int limit, int newLimit) {
        List<SrsCard> dueCards = cards.findDue(
                userId, LocalDate.now(), CardState.NEW, PageRequest.of(0, limit));

        List<SrsCard> queue = new ArrayList<>(dueCards);
        int room = Math.min(limit - dueCards.size(), remainingNewToday(userId, newLimit));
        if (room > 0) {
            queue.addAll(cards.findNewCards(userId, CardState.NEW, PageRequest.of(0, room)));
        }

        Map<Long, SrsDistractor> byVocabId = loadFreshDistractors(queue);
        requestMissing(queue, byVocabId);

        return queue.stream().map(card -> toDto(card, byVocabId)).toList();
    }

    @Transactional(readOnly = true)
    public SrsStatsDto stats(Long userId, int newLimit) {
        long dueNow = cards.countDue(userId, LocalDate.now(), CardState.NEW);
        long newTotal = cards.countByState(userId, CardState.NEW);
        long newAllowed = Math.min(newTotal, remainingNewToday(userId, newLimit));
        return new SrsStatsDto(dueNow + newAllowed, newTotal, cards.countLearned(userId));
    }

    @Transactional
    public ReviewResponse review(Long userId, Long cardId, Rating rating) {
        // findOwned chứ không findById: thẻ của người khác trả NOT_FOUND, không phải
        // FORBIDDEN — FORBIDDEN xác nhận id đó có tồn tại, tức là một kênh dò id.
        SrsCard card = cards.findOwned(cardId, userId).orElseThrow(
                () -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy thẻ id=" + cardId));

        int prevInterval = card.getIntervalDays();
        Schedule next = scheduler.next(card, rating, LocalDate.now());

        card.setEaseFactor(next.easeFactor());
        card.setIntervalDays(next.intervalDays());
        card.setRepetitions(next.repetitions());
        card.setLapses(next.lapses());
        card.setDueDate(next.dueDate());
        card.setState(next.state());

        ReviewLog log = new ReviewLog();
        log.setCard(card);
        log.setRating(rating);
        log.setPrevInterval(prevInterval);
        log.setNewInterval(next.intervalDays());
        logs.save(log);

        return new ReviewResponse(next.dueDate(), next.intervalDays(), next.easeFactor());
    }

    /** Chỉ lấy mồi nhử còn hiệu lực với version prompt hiện hành. */
    private Map<Long, SrsDistractor> loadFreshDistractors(List<SrsCard> queue) {
        if (queue.isEmpty()) {
            return Map.of();
        }
        List<Long> vocabIds = queue.stream().map(c -> c.getVocabEntry().getId()).toList();
        Map<Long, SrsDistractor> byVocabId = new HashMap<>();
        for (SrsDistractor d : distractors.findByVocabEntry_IdInAndPromptVersion(
                vocabIds, generator.currentPromptVersion())) {
            byVocabId.put(d.getVocabEntry().getId(), d);
        }
        return byVocabId;
    }

    /**
     * Bắn sinh nền cho thẻ chưa có mồi nhử rồi trả hàng đợi về NGAY — không chờ. Lượt ôn
     * lúc này vẫn chạy được nhờ panel tự bù mồi nhử từ thẻ khác; lượt sau đã có bộ thật.
     *
     * <p>Đây cũng là đường bù cho từ lưu từ trước khi có tính năng này, và cho mọi từ có
     * mồi nhử hết hiệu lực sau khi tăng version prompt.
     */
    private void requestMissing(List<SrsCard> queue, Map<Long, SrsDistractor> byVocabId) {
        int requested = 0;
        for (SrsCard card : queue) {
            if (requested >= MAX_BACKFILL_PER_CALL) {
                return;
            }
            Long vocabId = card.getVocabEntry().getId();
            if (!byVocabId.containsKey(vocabId)) {
                generator.generateAsync(vocabId);
                requested++;
            }
        }
    }

    /** Hạn mức từ mới còn lại của hôm nay, không bao giờ âm. */
    private int remainingNewToday(Long userId, int newLimit) {
        Instant startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant();
        long introduced = logs.countIntroducedSince(userId, startOfDay);
        return (int) Math.max(0L, newLimit - introduced);
    }

    private CardDto toDto(SrsCard card, Map<Long, SrsDistractor> byVocabId) {
        VocabEntry v = card.getVocabEntry();
        SrsDistractor d = byVocabId.get(v.getId());
        List<String> vi = d == null ? List.of() : d.getViOptions();
        List<String> en = d == null ? List.of() : d.getEnOptions();
        return new CardDto(card.getId(), v.getId(), v.getTerm(), v.getIpa(), v.getPos(),
                v.getMeaningVi(), v.getDefinitionEn(), v.getCefr(), v.getBandLevel(),
                v.getCollocations(), v.getExamples(), card.getState(), card.getDueDate(),
                vi, en);
    }
}
