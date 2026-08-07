package com.hiepnn.ieltstranslator.quiz;

import com.hiepnn.ieltstranslator.quiz.dto.AnswerQuizRequest;
import com.hiepnn.ieltstranslator.quiz.dto.AnswerResultDto;
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

    public QuizController(QuizService quizService) {
        this.quizService = quizService;
    }

    /**
     * Thiếu {@code @Valid} là toàn bộ ràng buộc của GenerateQuizRequest — kể cả
     * {@code @AssertTrue} một-trong-hai — vô hiệu IM LẶNG, và request méo đi thẳng xuống
     * service để nổ thành 500 thay vì 400.
     */
    @PostMapping("/generate")
    public List<QuizItemDto> generate(@Valid @RequestBody GenerateQuizRequest request) {
        return quizService.generate(request);
    }

    @PostMapping("/answer")
    public AnswerResultDto answer(@Valid @RequestBody AnswerQuizRequest request) {
        return quizService.answer(request.quizItemId(), request.answer());
    }
}
