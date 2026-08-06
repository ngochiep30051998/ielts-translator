package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import com.hiepnn.ieltstranslator.vocabulary.VocabEntrySavedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

/**
 * Tạo thẻ ôn tập khi một từ mới vào sổ.
 *
 * <p>Chạy đồng bộ trong cùng transaction với lệnh lưu, nên từ và thẻ hoặc cùng có
 * hoặc cùng không — không có trạng thái từ đã lưu mà thiếu thẻ.
 */
@Component
public class SrsCardCreator {

    /** pos của một câu đầy đủ, do service worker đặt khi mode = SENTENCE. */
    private static final String PHRASE_POS = "phrase";

    private final SrsCardRepository cards;

    public SrsCardCreator(SrsCardRepository cards) {
        this.cards = cards;
    }

    @EventListener
    public void onVocabEntrySaved(VocabEntrySavedEvent event) {
        VocabEntry entry = event.entry();
        if (PHRASE_POS.equals(entry.getPos()) || cards.existsByVocabEntry_Id(entry.getId())) {
            return;
        }

        SrsCard card = new SrsCard();
        card.setVocabEntry(entry);
        card.setDueDate(LocalDate.now());
        card.setState(CardState.NEW);
        cards.save(card);
    }
}
