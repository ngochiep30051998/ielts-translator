package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.vocabulary.VocabEntry;
import jakarta.persistence.*;

import java.time.Instant;
import java.time.LocalDate;

@Entity
@Table(name = "srs_card")
public class SrsCard {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // OneToOne khớp ràng buộc UNIQUE ở tầng schema: một thẻ mỗi từ, chiều EN → VI.
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "vocab_entry_id", nullable = false, unique = true)
    private VocabEntry vocabEntry;

    @Column(name = "ease_factor", nullable = false)
    private double easeFactor = 2.5;

    @Column(name = "interval_days", nullable = false)
    private int intervalDays = 0;

    @Column(nullable = false)
    private int repetitions = 0;

    @Column(nullable = false)
    private int lapses = 0;

    @Column(name = "due_date", nullable = false)
    private LocalDate dueDate;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private CardState state = CardState.NEW;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public VocabEntry getVocabEntry() { return vocabEntry; }
    public void setVocabEntry(VocabEntry vocabEntry) { this.vocabEntry = vocabEntry; }
    public double getEaseFactor() { return easeFactor; }
    public void setEaseFactor(double easeFactor) { this.easeFactor = easeFactor; }
    public int getIntervalDays() { return intervalDays; }
    public void setIntervalDays(int intervalDays) { this.intervalDays = intervalDays; }
    public int getRepetitions() { return repetitions; }
    public void setRepetitions(int repetitions) { this.repetitions = repetitions; }
    public int getLapses() { return lapses; }
    public void setLapses(int lapses) { this.lapses = lapses; }
    public LocalDate getDueDate() { return dueDate; }
    public void setDueDate(LocalDate dueDate) { this.dueDate = dueDate; }
    public CardState getState() { return state; }
    public void setState(CardState state) { this.state = state; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
