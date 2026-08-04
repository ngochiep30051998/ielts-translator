package com.hiepnn.ieltstranslator.translation;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
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

        int separator = raw.indexOf("\n---");
        if (separator < 0) {
            throw new IllegalStateException("Prompt thiếu dòng phân cách '---': " + path);
        }
        String header = raw.substring(0, separator).trim();
        String body = raw.substring(raw.indexOf('\n', separator + 1) + 1).trim();

        if (!header.startsWith("version:")) {
            throw new IllegalStateException("Prompt thiếu header 'version:': " + path);
        }
        int version = Integer.parseInt(header.substring("version:".length()).trim());
        return new PromptTemplate(body, version);
    }
}
