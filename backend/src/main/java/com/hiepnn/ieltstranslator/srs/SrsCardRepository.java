package com.hiepnn.ieltstranslator.srs;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;

public interface SrsCardRepository extends JpaRepository<SrsCard, Long> {

    boolean existsByVocabEntry_Id(Long vocabEntryId);

    /**
     * Thẻ đã đến hạn. {@code join fetch} một liên kết to-one KHÔNG làm nhân dòng nên
     * phân trang vẫn chạy trong SQL — cảnh báo HHH000104 chỉ áp cho fetch collection.
     */
    @Query("""
            select c from SrsCard c join fetch c.vocabEntry
            where c.state <> :newState and c.dueDate <= :today
            order by c.dueDate asc, c.id asc
            """)
    List<SrsCard> findDue(@Param("today") LocalDate today,
                          @Param("newState") CardState newState,
                          Pageable pageable);

    @Query("""
            select c from SrsCard c join fetch c.vocabEntry v
            where c.state = :newState
            order by v.createdAt asc, c.id asc
            """)
    List<SrsCard> findNewCards(@Param("newState") CardState newState, Pageable pageable);

    @Query("select count(c) from SrsCard c where c.state <> :newState and c.dueDate <= :today")
    long countDue(@Param("today") LocalDate today, @Param("newState") CardState newState);

    long countByState(CardState state);

    @Query("select count(c) from SrsCard c where c.repetitions >= 1")
    long countLearned();
}
