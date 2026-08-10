package com.hiepnn.ieltstranslator.quiz;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface QuizAttemptRepository extends JpaRepository<QuizAttempt, Long> {

    /**
     * Lượt làm gần nhất của một item.
     *
     * <p>Sắp theo {@code id} giảm dần chứ KHÔNG theo {@code created_at}: cột đó mặc định
     * {@code now()}, mà {@code now()} trong Postgres là thời điểm bắt đầu transaction — hai
     * lượt trong cùng một transaction sẽ trùng mốc thời gian và thứ tự thành ngẫu nhiên.
     * {@code id} là BIGSERIAL nên luôn tăng.
     */
    Optional<QuizAttempt> findFirstByQuizItem_IdOrderByIdDesc(Long quizItemId);
}
