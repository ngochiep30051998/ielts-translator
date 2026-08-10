package com.hiepnn.ieltstranslator.quiz;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Chọn từ đưa vào đề. Đây là chỗ DUY NHẤT module quiz chạm tới bảng {@code srs_card}, và
 * nó chỉ ĐỌC.
 *
 * <p>Vì sao native query chứ không inject {@code SrsCardRepository}: giữ chiều phụ thuộc
 * sạch. quiz không import gì từ package srs, nên không có đường nào để lỡ tay gọi một
 * method ghi. Bất biến "quiz không tác động tới lịch SRS" được QuizSrsIsolationIT kiểm
 * chứng bằng cách so ảnh chụp trước/sau, không bằng lời hứa.
 *
 * <p>Extends JpaRepository trên QuizItem chỉ để có một repository interface hợp lệ cho
 * Spring Data; nó không dùng method kế thừa nào.
 */
@Repository
public interface QuizCandidateRepository extends JpaRepository<QuizItem, Long> {

    /**
     * Từ đã ôn ít nhất một lượt, ưu tiên từ ít bị hỏi nhất, rồi tới từ hay quên nhất.
     * Từ chưa ôn lần nào (repetitions = 0) KHÔNG được đưa vào quiz — chưa gặp mặt thì
     * hỏi là phạt oan.
     *
     * <p>{@code LIMIT :limit} là cú pháp Postgres, hợp lệ vì {@code nativeQuery = true} và
     * dự án chỉ chạy Postgres (Testcontainers Postgres, không H2). Đừng đổi sang
     * {@code Pageable}: trộn Pageable với native query có GROUP BY sinh count query sai.
     */
    @Query(value = """
            SELECT v.id
            FROM vocab_entry v
            JOIN srs_card c ON c.vocab_entry_id = v.id
            LEFT JOIN quiz_item qi ON qi.vocab_entry_id = v.id
            LEFT JOIN quiz_attempt qa ON qa.quiz_item_id = qi.id
            WHERE v.user_id = :userId AND c.repetitions >= 1
            GROUP BY v.id, c.lapses
            ORDER BY count(qa.id) ASC, c.lapses DESC, v.id ASC
            LIMIT :limit
            """, nativeQuery = true)
    List<Long> findCandidates(@Param("userId") Long userId, @Param("limit") int limit);
}
