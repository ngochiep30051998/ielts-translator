package com.hiepnn.ieltstranslator.quiz;

import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Một đề quiz đã sinh. {@code payload} chứa CẢ ĐÁP ÁN — entity này không bao giờ được
 * serialize thẳng ra HTTP. Đường ra duy nhất là QuizItemDto.
 *
 * <p>Thứ tự phần tử trong {@code payload.options} là BẤT BIẾN sau khi lưu: nó đã được xáo
 * đúng một lần lúc sinh, và {@code payload.correct_index} trỏ vào chính thứ tự đó. Sắp xếp
 * lại nó ở bất kỳ đâu là chấm sai toàn bộ câu trắc nghiệm mà không có lỗi nào nổ ra.
 */
@Entity
@Table(name = "quiz_item")
public class QuizItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "vocab_entry_id", nullable = false)
    private VocabEntry vocabEntry;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 24)
    private QuizType type;

    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private Map<String, Object> payload = new LinkedHashMap<>();

    @Column(name = "prompt_version", nullable = false)
    private int promptVersion;

    @Column(name = "created_at", insertable = false, updatable = false)
    private Instant createdAt;

    public Long getId() { return id; }

    public VocabEntry getVocabEntry() { return vocabEntry; }
    public void setVocabEntry(VocabEntry vocabEntry) { this.vocabEntry = vocabEntry; }

    public QuizType getType() { return type; }
    public void setType(QuizType type) { this.type = type; }

    public Map<String, Object> getPayload() { return payload; }
    public void setPayload(Map<String, Object> payload) { this.payload = payload; }

    public int getPromptVersion() { return promptVersion; }
    public void setPromptVersion(int promptVersion) { this.promptVersion = promptVersion; }

    public Instant getCreatedAt() { return createdAt; }
}
