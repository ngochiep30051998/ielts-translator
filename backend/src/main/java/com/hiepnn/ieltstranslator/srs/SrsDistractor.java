package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.Type;

import java.time.Instant;
import java.util.List;

/** Mồi nhử đã cache cho một từ. Một từ đúng một bản ghi (UNIQUE trên vocab_entry_id). */
@Entity
@Table(name = "srs_distractor")
public class SrsDistractor {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "vocab_entry_id", nullable = false, unique = true)
    private VocabEntry vocabEntry;

    @Type(JsonType.class)
    @Column(name = "vi_options", columnDefinition = "jsonb", nullable = false)
    private List<String> viOptions;

    @Type(JsonType.class)
    @Column(name = "en_options", columnDefinition = "jsonb", nullable = false)
    private List<String> enOptions;

    @Column(name = "prompt_version", nullable = false)
    private int promptVersion;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public VocabEntry getVocabEntry() { return vocabEntry; }
    public void setVocabEntry(VocabEntry vocabEntry) { this.vocabEntry = vocabEntry; }
    public List<String> getViOptions() { return viOptions; }
    public void setViOptions(List<String> viOptions) { this.viOptions = viOptions; }
    public List<String> getEnOptions() { return enOptions; }
    public void setEnOptions(List<String> enOptions) { this.enOptions = enOptions; }
    public int getPromptVersion() { return promptVersion; }
    public void setPromptVersion(int promptVersion) { this.promptVersion = promptVersion; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
