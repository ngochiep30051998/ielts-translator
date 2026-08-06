package com.hiepnn.ieltstranslator.srs;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "review_log")
public class ReviewLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "card_id", nullable = false)
    private SrsCard card;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 8)
    private Rating rating;

    @Column(name = "reviewed_at", nullable = false)
    private Instant reviewedAt = Instant.now();

    /** Interval TRƯỚC lượt review này. Bằng 0 duy nhất ở lượt đầu đời của thẻ. */
    @Column(name = "prev_interval", nullable = false)
    private int prevInterval;

    @Column(name = "new_interval", nullable = false)
    private int newInterval;

    public Long getId() { return id; }
    public SrsCard getCard() { return card; }
    public void setCard(SrsCard card) { this.card = card; }
    public Rating getRating() { return rating; }
    public void setRating(Rating rating) { this.rating = rating; }
    public Instant getReviewedAt() { return reviewedAt; }
    public void setReviewedAt(Instant reviewedAt) { this.reviewedAt = reviewedAt; }
    public int getPrevInterval() { return prevInterval; }
    public void setPrevInterval(int prevInterval) { this.prevInterval = prevInterval; }
    public int getNewInterval() { return newInterval; }
    public void setNewInterval(int newInterval) { this.newInterval = newInterval; }
}
