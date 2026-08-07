package com.hiepnn.ieltstranslator.quiz;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.Instant;

/** Một lượt làm bài. Chấm lại cùng một item ghi thêm dòng mới, KHÔNG ghi đè. */
@Entity
@Table(name = "quiz_attempt")
public class QuizAttempt {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "quiz_item_id", nullable = false)
    private QuizItem quizItem;

    @Column(name = "user_answer", nullable = false, columnDefinition = "text")
    private String userAnswer;

    @Column(nullable = false)
    private boolean correct;

    @Column(nullable = false)
    private int score;

    @Column(name = "ai_feedback", columnDefinition = "text")
    private String aiFeedback;

    /** Chỉ FREE_WRITE mới có giá trị. NULL ở hai loại kia là "không có khái niệm đó". */
    @Column(name = "improved_version", columnDefinition = "text")
    private String improvedVersion;

    @Column(name = "created_at", insertable = false, updatable = false)
    private Instant createdAt;

    public Long getId() { return id; }

    public QuizItem getQuizItem() { return quizItem; }
    public void setQuizItem(QuizItem quizItem) { this.quizItem = quizItem; }

    public String getUserAnswer() { return userAnswer; }
    public void setUserAnswer(String userAnswer) { this.userAnswer = userAnswer; }

    public boolean isCorrect() { return correct; }
    public void setCorrect(boolean correct) { this.correct = correct; }

    public int getScore() { return score; }
    public void setScore(int score) { this.score = score; }

    public String getAiFeedback() { return aiFeedback; }
    public void setAiFeedback(String aiFeedback) { this.aiFeedback = aiFeedback; }

    public String getImprovedVersion() { return improvedVersion; }
    public void setImprovedVersion(String improvedVersion) { this.improvedVersion = improvedVersion; }

    public Instant getCreatedAt() { return createdAt; }
}
