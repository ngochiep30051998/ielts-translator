package com.hiepnn.ieltstranslator.srs.dto;

import com.hiepnn.ieltstranslator.srs.Rating;
import jakarta.validation.constraints.NotNull;

public record ReviewRequest(@NotNull Long cardId, @NotNull Rating rating) {
}
