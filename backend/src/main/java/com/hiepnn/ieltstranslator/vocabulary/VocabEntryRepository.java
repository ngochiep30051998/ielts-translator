package com.hiepnn.ieltstranslator.vocabulary;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

/**
 * MỌI method ở đây nhận userId. Không có method nào "tìm theo id" trần: tra rồi so chủ sở
 * hữu sau để lại một khe giữa đọc và kiểm, và một chỗ quên so là rò dữ liệu im lặng.
 * MultiUserIsolationIT là chốt chặn.
 */
public interface VocabEntryRepository extends JpaRepository<VocabEntry, Long> {

    Optional<VocabEntry> findByUser_IdAndTermAndPos(Long userId, String term, String pos);

    Optional<VocabEntry> findByIdAndUser_Id(Long id, Long userId);

    List<VocabEntry> findAllByUser_IdOrderByCreatedAtDesc(Long userId);

    /** Lọc danh sách id do CLIENT gửi lên xuống còn những id thật sự thuộc về user. */
    @Query("select v.id from VocabEntry v where v.user.id = :userId and v.id in :ids")
    List<Long> findOwnedIds(@Param("userId") Long userId, @Param("ids") List<Long> ids);

    /**
     * {@code user_id = :userId} phải có mặt ở CẢ value LẪN countQuery. Quên ở countQuery thì
     * danh sách đúng nhưng totalElements đếm cả sổ từ người khác — phân trang sai và lộ
     * kích thước dữ liệu của họ.
     */
    @Query(value = """
            SELECT * FROM vocab_entry
            WHERE user_id = :userId
              AND (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            ORDER BY created_at DESC
            """,
            countQuery = """
            SELECT count(*) FROM vocab_entry
            WHERE user_id = :userId
              AND (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            """,
            nativeQuery = true)
    Page<VocabEntry> search(@Param("userId") Long userId, @Param("q") String q,
                            @Param("tag") String tag, Pageable pageable);
}
