package com.hiepnn.ieltstranslator.translation.dto;

import jakarta.validation.constraints.NotBlank;

public record TranslateRequest(
        @NotBlank String text,
        String contextSentence,
        String sourceUrl,
        String pageTitle
) {}
