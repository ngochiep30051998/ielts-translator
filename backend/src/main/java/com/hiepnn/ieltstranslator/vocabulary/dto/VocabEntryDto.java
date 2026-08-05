package com.hiepnn.ieltstranslator.vocabulary.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.time.Instant;
import java.util.List;

public record VocabEntryDto(
        Long id, String term, String lemma, String lang, String pos, String ipa,
        String meaningVi, String definitionEn, String cefr, String bandLevel,
        List<String> tags, String sourceUrl, String sourceSentence,
        JsonNode collocations, JsonNode examples, Instant createdAt
) {}
