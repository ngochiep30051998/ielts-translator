package com.hiepnn.ieltstranslator.translation;

public enum Mode {
    WORD,
    SENTENCE;

    /** Từ 3 token trở xuống coi là tra từ; nhiều hơn là tra câu. */
    public static Mode of(String text) {
        if (text == null || text.isBlank()) {
            return WORD;
        }
        int tokens = text.trim().split("\\s+").length;
        return tokens <= 3 ? WORD : SENTENCE;
    }
}
