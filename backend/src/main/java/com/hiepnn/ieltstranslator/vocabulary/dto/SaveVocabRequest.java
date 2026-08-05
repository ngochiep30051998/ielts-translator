package com.hiepnn.ieltstranslator.vocabulary.dto;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

public record SaveVocabRequest(
        @NotBlank(message = "không được để trống") String term,
        String lemma,
        @NotBlank(message = "không được để trống") String lang,
        String pos,
        String ipa,
        @NotBlank(message = "không được để trống") String meaningVi,
        String definitionEn,
        String cefr,
        String bandLevel,
        List<String> tags,
        String sourceUrl,
        String sourceSentence,
        JsonNode collocations,
        JsonNode examples
) {}
