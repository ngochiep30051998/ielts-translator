package com.hiepnn.ieltstranslator.translation;

public record PromptTemplate(String body, int version) {

    private static final String NO_CONTEXT = "(không có ngữ cảnh)";

    public String render(String text, String context) {
        String safeContext = (context == null || context.isBlank()) ? NO_CONTEXT : context;
        return body.replace("{{TEXT}}", text == null ? "" : text)
                   .replace("{{CONTEXT}}", safeContext);
    }
}
