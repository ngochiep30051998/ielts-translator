package com.hiepnn.ieltstranslator.vocabulary;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface VocabEntryRepository extends JpaRepository<VocabEntry, Long> {

    Optional<VocabEntry> findByTermAndPos(String term, String pos);

    List<VocabEntry> findAllByOrderByCreatedAtDesc();

    @Query(value = """
            SELECT * FROM vocab_entry
            WHERE (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            ORDER BY created_at DESC
            """,
            countQuery = """
            SELECT count(*) FROM vocab_entry
            WHERE (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            """,
            nativeQuery = true)
    Page<VocabEntry> search(@Param("q") String q, @Param("tag") String tag, Pageable pageable);
}
