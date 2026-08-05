package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.JsonNode;
import io.hypersistence.utils.hibernate.type.array.StringArrayType;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import org.hibernate.annotations.Type;

import java.time.Instant;

@Entity
@Table(name = "vocab_entry")
public class VocabEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String term;

    private String lemma;

    @Column(nullable = false)
    private String lang;

    @Column(nullable = false)
    private String pos = "";

    private String ipa;

    @Column(name = "meaning_vi", nullable = false)
    private String meaningVi;

    @Column(name = "definition_en")
    private String definitionEn;

    private String cefr;

    @Column(name = "band_level")
    private String bandLevel;

    // hypersistence-utils StringArrayType khai báo JDBC type code là OTHER, còn
    // driver Postgres báo cột text[] về là "_text" (tên catalog nội bộ của PG cho
    // kiểu mảng) với type code ARRAY — hai bên không khớp nên Hibernate schema
    // validator (ddl-auto=validate) báo sai lệch cột dù dữ liệu vẫn đúng.
    // columnDefinition = "_text" khớp đúng literal mà JDBC trả về nên qua được
    // bước so khớp chuỗi trong Hibernate; giá trị này KHÔNG dùng để sinh DDL vì
    // bảng đã được Flyway tạo sẵn (ddl-auto chỉ validate, không create).
    @Type(StringArrayType.class)
    @Column(columnDefinition = "_text", nullable = false)
    private String[] tags = new String[0];

    @Column(name = "source_url")
    private String sourceUrl;

    @Column(name = "source_sentence")
    private String sourceSentence;

    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private JsonNode collocations;

    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private JsonNode examples;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public String getTerm() { return term; }
    public void setTerm(String term) { this.term = term; }
    public String getLemma() { return lemma; }
    public void setLemma(String lemma) { this.lemma = lemma; }
    public String getLang() { return lang; }
    public void setLang(String lang) { this.lang = lang; }
    public String getPos() { return pos; }
    public void setPos(String pos) { this.pos = pos == null ? "" : pos; }
    public String getIpa() { return ipa; }
    public void setIpa(String ipa) { this.ipa = ipa; }
    public String getMeaningVi() { return meaningVi; }
    public void setMeaningVi(String meaningVi) { this.meaningVi = meaningVi; }
    public String getDefinitionEn() { return definitionEn; }
    public void setDefinitionEn(String definitionEn) { this.definitionEn = definitionEn; }
    public String getCefr() { return cefr; }
    public void setCefr(String cefr) { this.cefr = cefr; }
    public String getBandLevel() { return bandLevel; }
    public void setBandLevel(String bandLevel) { this.bandLevel = bandLevel; }
    public String[] getTags() { return tags; }
    public void setTags(String[] tags) { this.tags = tags == null ? new String[0] : tags; }
    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }
    public String getSourceSentence() { return sourceSentence; }
    public void setSourceSentence(String s) { this.sourceSentence = s; }
    public JsonNode getCollocations() { return collocations; }
    public void setCollocations(JsonNode collocations) { this.collocations = collocations; }
    public JsonNode getExamples() { return examples; }
    public void setExamples(JsonNode examples) { this.examples = examples; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
