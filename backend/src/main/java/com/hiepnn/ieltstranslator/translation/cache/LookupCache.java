package com.hiepnn.ieltstranslator.translation.cache;

import com.fasterxml.jackson.databind.JsonNode;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import org.hibernate.annotations.Type;

import java.time.Instant;

@Entity
@Table(name = "lookup_cache")
public class LookupCache {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "source_hash", nullable = false, unique = true)
    private String sourceHash;

    @Column(name = "source_text", nullable = false)
    private String sourceText;

    @Column(nullable = false)
    private String direction;

    @Column(nullable = false)
    private String mode;

    @Column(nullable = false)
    private String model;

    @Column(name = "prompt_version", nullable = false)
    private int promptVersion;

    @Type(JsonType.class)
    @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode response;

    @Column(name = "hit_count", nullable = false)
    private int hitCount;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected LookupCache() {}

    public LookupCache(String sourceHash, String sourceText, String direction, String mode,
                       String model, int promptVersion, JsonNode response) {
        this.sourceHash = sourceHash;
        this.sourceText = sourceText;
        this.direction = direction;
        this.mode = mode;
        this.model = model;
        this.promptVersion = promptVersion;
        this.response = response;
        this.hitCount = 0;
        this.createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public JsonNode getResponse() { return response; }
    public int getHitCount() { return hitCount; }
}
