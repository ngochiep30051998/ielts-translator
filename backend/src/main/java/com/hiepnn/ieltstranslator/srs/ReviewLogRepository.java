package com.hiepnn.ieltstranslator.srs;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;

public interface ReviewLogRepository extends JpaRepository<ReviewLog, Long> {

    /**
     * Số thẻ MỚI đã học kể từ mốc thời gian truyền vào.
     *
     * <p>{@code prevInterval = 0} nhận diện chính xác lượt review đầu đời của một thẻ:
     * thẻ mới có {@code intervalDays = 0}, còn bấm Lại luôn đặt interval về 1 nên mọi
     * lượt sau đó đều có {@code prevInterval >= 1}. Nhờ vậy không cần bảng đếm riêng.
     */
    @Query("select count(l) from ReviewLog l where l.reviewedAt >= :since and l.prevInterval = 0")
    long countIntroducedSince(@Param("since") Instant since);
}
