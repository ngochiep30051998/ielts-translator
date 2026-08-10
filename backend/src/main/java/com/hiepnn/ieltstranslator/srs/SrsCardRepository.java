package com.hiepnn.ieltstranslator.srs;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * Chủ sở hữu suy ra qua vocabEntry.user — srs_card KHÔNG có cột user_id riêng. Mọi truy vấn
 * ở đây vì thế phải join tới vocabEntry, kể cả các câu đếm.
 */
public interface SrsCardRepository extends JpaRepository<SrsCard, Long> {

    boolean existsByVocabEntry_Id(Long vocabEntryId);

    /** Thẻ của CHÍNH user. Trả Optional rỗng cho thẻ người khác — gọi ở tầng trên thành 404. */
    @Query("select c from SrsCard c where c.id = :cardId and c.vocabEntry.user.id = :userId")
    Optional<SrsCard> findOwned(@Param("cardId") Long cardId, @Param("userId") Long userId);

    /**
     * Thẻ đã đến hạn. {@code join fetch} một liên kết to-one KHÔNG làm nhân dòng nên
     * phân trang vẫn chạy trong SQL — cảnh báo HHH000104 chỉ áp cho fetch collection.
     */
    @Query("""
            select c from SrsCard c join fetch c.vocabEntry v
            where v.user.id = :userId and c.state <> :newState and c.dueDate <= :today
            order by c.dueDate asc, c.id asc
            """)
    List<SrsCard> findDue(@Param("userId") Long userId,
                          @Param("today") LocalDate today,
                          @Param("newState") CardState newState,
                          Pageable pageable);

    @Query("""
            select c from SrsCard c join fetch c.vocabEntry v
            where v.user.id = :userId and c.state = :newState
            order by v.createdAt asc, c.id asc
            """)
    List<SrsCard> findNewCards(@Param("userId") Long userId,
                               @Param("newState") CardState newState, Pageable pageable);

    @Query("""
            select count(c) from SrsCard c
            where c.vocabEntry.user.id = :userId and c.state <> :newState and c.dueDate <= :today
            """)
    long countDue(@Param("userId") Long userId, @Param("today") LocalDate today,
                  @Param("newState") CardState newState);

    /** Derived query cũ (countByState) không join được sang chủ sở hữu, nên viết tường minh. */
    @Query("select count(c) from SrsCard c where c.vocabEntry.user.id = :userId and c.state = :state")
    long countByState(@Param("userId") Long userId, @Param("state") CardState state);

    @Query("select count(c) from SrsCard c where c.vocabEntry.user.id = :userId and c.repetitions >= 1")
    long countLearned(@Param("userId") Long userId);
}
