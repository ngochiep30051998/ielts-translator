package com.hiepnn.ieltstranslator.srs.dto;

import java.time.LocalDate;

public record ReviewResponse(LocalDate nextDueDate, int intervalDays, double easeFactor) {
}
