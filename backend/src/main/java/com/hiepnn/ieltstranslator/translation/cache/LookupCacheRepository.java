package com.hiepnn.ieltstranslator.translation.cache;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface LookupCacheRepository extends JpaRepository<LookupCache, Long> {

    Optional<LookupCache> findBySourceHash(String sourceHash);

    @Modifying
    @Query("UPDATE LookupCache c SET c.hitCount = c.hitCount + 1 WHERE c.id = :id")
    void incrementHitCount(@Param("id") Long id);
}
