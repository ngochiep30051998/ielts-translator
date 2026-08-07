package com.hiepnn.ieltstranslator.srs.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.srs.CardState;

import java.time.LocalDate;
import java.util.List;

/**
 * Gộp sẵn dữ liệu vocab để side panel chỉ phải gọi một lượt cho cả xấp thẻ.
 *
 * <p>{@code viDistractors} / {@code enDistractors} rỗng nghĩa là mồi nhử chưa sinh kịp;
 * panel tự bù bằng thẻ khác trong hàng đợi chứ không coi đó là lỗi.
 */
public record CardDto(Long id, Long vocabEntryId, String term, String ipa, String pos,
                      String meaningVi, String definitionEn, String cefr, String bandLevel,
                      JsonNode collocations, JsonNode examples,
                      CardState state, LocalDate dueDate,
                      List<String> viDistractors, List<String> enDistractors) {
}
