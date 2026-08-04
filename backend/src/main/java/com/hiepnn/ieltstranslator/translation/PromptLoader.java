package com.hiepnn.ieltstranslator.translation;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Đọc prompt từ classpath. Mỗi file có header "version: N", một dòng "---",
 * rồi tới nội dung. Version đi vào cache key nên sửa prompt là cache tự hết hiệu lực.
 */
@Component
public class PromptLoader {

    private final Map<String, PromptTemplate> cache = new ConcurrentHashMap<>();

    public PromptTemplate load(Direction direction, Mode mode) {
        String fileName = fileNameFor(direction, mode);
        return cache.computeIfAbsent(fileName, this::readTemplate);
    }

    private String fileNameFor(Direction direction, Mode mode) {
        String dir = direction == Direction.EN_VI ? "en-vi" : "vi-en";
        String md = mode == Mode.WORD ? "word" : "sentence";
        return "prompts/" + dir + "-" + md + ".md";
    }

    private PromptTemplate readTemplate(String path) {
        String raw;
        try {
            raw = new String(new ClassPathResource(path).getInputStream().readAllBytes(),
                             StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Không đọc được prompt: " + path, e);
        }

        String[] lines = raw.split("\n", -1);
        int delimiterIndex = -1;
        for (int i = 0; i < lines.length; i++) {
            if (lines[i].strip().equals("---")) {
                delimiterIndex = i;
                break;
            }
        }
        if (delimiterIndex < 0) {
            throw new IllegalStateException("Prompt thiếu dòng phân cách '---': " + path);
        }
        String header = String.join("\n", Arrays.copyOfRange(lines, 0, delimiterIndex)).trim();
        String body = String.join("\n", Arrays.copyOfRange(lines, delimiterIndex + 1, lines.length)).trim();

        if (!header.startsWith("version:")) {
            throw new IllegalStateException("Prompt thiếu header 'version:': " + path);
        }
        int version;
        try {
            version = Integer.parseInt(header.substring("version:".length()).trim());
        } catch (NumberFormatException e) {
            throw new IllegalStateException("Prompt có version không phải số: " + path, e);
        }
        return new PromptTemplate(body, version);
    }
}
