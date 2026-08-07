package com.hiepnn.ieltstranslator.quiz;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface QuizItemRepository extends JpaRepository<QuizItem, Long> {

    /**
     * Đề còn tái dùng được: đúng từ, đúng loại đang hỏi, prompt_version còn hiệu lực,
     * và CHƯA từng có lượt làm nào. Đây là cách hiện thực "không gọi Gemini mỗi lần mở
     * màn quiz".
     *
     * <p>{@code join fetch} vocabEntry vì QuizItemDto cần {@code term}; thiếu nó là
     * N+1 query ngay trên đường nóng.
     */
    @Query("""
            select qi from QuizItem qi join fetch qi.vocabEntry
            where qi.vocabEntry.id in :vocabIds
              and qi.type in :types
              and qi.promptVersion = :promptVersion
              and not exists (select 1 from QuizAttempt qa where qa.quizItem = qi)
            order by qi.id asc
            """)
    List<QuizItem> findReusable(@Param("vocabIds") Collection<Long> vocabIds,
                                @Param("types") Collection<QuizType> types,
                                @Param("promptVersion") int promptVersion);
}
