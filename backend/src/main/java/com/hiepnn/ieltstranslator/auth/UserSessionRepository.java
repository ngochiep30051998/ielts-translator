package com.hiepnn.ieltstranslator.auth;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.Optional;

public interface UserSessionRepository extends JpaRepository<UserSession, Long> {

    /**
     * Phiên còn sống. Ba điều kiện nằm trong CÂU TRUY VẤN chứ không kiểm ở Java: quên một
     * cái ở tầng service là một token đã thu hồi vẫn dùng được, và không có gì đỏ.
     *
     * <p>{@code join fetch} user vì SessionFilter cần id của user ngay — không có nó là một
     * lượt lazy load nữa trên đường nóng của MỌI request.
     */
    @Query("""
            select s from UserSession s join fetch s.user
            where s.tokenHash = :hash and s.revokedAt is null and s.expiresAt > :now
            """)
    Optional<UserSession> findAlive(@Param("hash") String hash, @Param("now") Instant now);
}
