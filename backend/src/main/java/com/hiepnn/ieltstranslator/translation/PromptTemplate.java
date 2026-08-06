package com.hiepnn.ieltstranslator.translation;

import java.util.Map;

public record PromptTemplate(String body, int version) {

    private static final String NO_CONTEXT = "(không có ngữ cảnh)";

    /** Thay mọi {{KHOÁ}} bằng giá trị tương ứng. Giá trị null coi như chuỗi rỗng. */
    public String render(Map<String, String> vars) {
        String out = body;
        for (Map.Entry<String, String> entry : vars.entrySet()) {
            String value = entry.getValue() == null ? "" : entry.getValue();
            out = out.replace("{{" + entry.getKey() + "}}", value);
        }
        return out;
    }

    public String render(String text, String context) {
        String safeContext = (context == null || context.isBlank()) ? NO_CONTEXT : context;
        return render(Map.of("TEXT", text == null ? "" : text, "CONTEXT", safeContext));
    }
}
