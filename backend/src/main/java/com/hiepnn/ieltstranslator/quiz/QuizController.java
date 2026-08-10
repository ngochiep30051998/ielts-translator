package com.hiepnn.ieltstranslator.quiz;

import com.hiepnn.ieltstranslator.quiz.dto.AnswerQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.AnswerResultDto;
import com.hiepnn.ieltstranslator.quiz.dto.ExplainQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.ExplanationDto;
import com.hiepnn.ieltstranslator.quiz.dto.GenerateQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.QuizItemDto;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/quiz")
public class QuizController {

    private final QuizService quizService;
    private final com.hiepnn.ieltstranslator.auth.AuthContext auth;

    public QuizController(QuizService quizService,
                          com.hiepnn.ieltstranslator.auth.AuthContext auth) {
        this.quizService = quizService;
        this.auth = auth;
    }

    /**
     * Thiếu {@code @Valid} là toàn bộ ràng buộc của GenerateQuizRequest — kể cả
     * {@code @AssertTrue} một-trong-hai — vô hiệu IM LẶNG, và request méo đi thẳng xuống
     * service để nổ thành 500 thay vì 400.
     */
    @PostMapping("/generate")
    public List<QuizItemDto> generate(@Valid @RequestBody GenerateQuizRequest request) {
        return quizService.generate(auth.requireUserId(), request);
    }

    @PostMapping("/answer")
    public AnswerResultDto answer(@Valid @RequestBody AnswerQuizRequest request) {
        return quizService.answer(auth.requireUserId(), request.quizItemId(), request.answer());
    }

    /**
     * Giải thích một câu ĐÃ trả lời. Response chứa đáp án, nên endpoint chỉ phục vụ item đã
     * có lượt làm — chốt chặn đó nằm trong QuizService.explain().
     */
    @PostMapping("/explain")
    public ExplanationDto explain(@Valid @RequestBody ExplainQuizRequest request) {
        return quizService.explain(auth.requireUserId(), request.quizItemId());
    }
}
