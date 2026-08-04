package com.hiepnn.ieltstranslator.translation;

import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.Set;
import java.util.regex.Pattern;

@Component
public class LanguageDetector {

    /** Ký tự chỉ xuất hiện trong tiếng Việt — thấy một cái là chắc chắn tiếng Việt. */
    private static final Pattern VIETNAMESE_CHARS = Pattern.compile(
            "[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);

    /** Stopword tiếng Việt dạng KHÔNG dấu — dùng khi người dùng gõ không dấu. */
    private static final Set<String> VI_STOPWORDS = Set.of(
            "cua", "va", "la", "khong", "cho", "nhung", "duoc", "co", "nay", "voi",
            "tren", "trong", "mot", "cac", "nguoi", "den", "tu", "ra", "khi", "nhu",
            "se", "da", "cung", "phai", "the", "nao", "gi", "ai", "toi", "ban",
            "chung", "minh", "can", "lam", "viec", "tot", "cai");

    private static final Set<String> EN_STOPWORDS = Set.of(
            "the", "and", "is", "of", "to", "in", "that", "it", "for", "on",
            "with", "as", "this", "are", "was", "be", "have", "has", "not", "but",
            "they", "from", "which", "you", "we", "should", "a", "an");

    public Direction detect(String text) {
        if (text == null || text.isBlank()) {
            return Direction.EN_VI;
        }
        if (VIETNAMESE_CHARS.matcher(text).find()) {
            return Direction.VI_EN;
        }
        String[] tokens = text.toLowerCase().split("[^a-z]+");
        long viHits = Arrays.stream(tokens).filter(VI_STOPWORDS::contains).count();
        long enHits = Arrays.stream(tokens).filter(EN_STOPWORDS::contains).count();
        return viHits > enHits ? Direction.VI_EN : Direction.EN_VI;
    }
}
