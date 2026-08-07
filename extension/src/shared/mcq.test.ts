import { describe, it, expect } from 'vitest';
import { buildQuestion, ratingFor } from './mcq';
import type { CardDto } from './types';

function card(id: number, term: string, vi: string[] = [], en: string[] = []): CardDto {
  return {
    id, vocabEntryId: id * 10, term, ipa: '/test/', pos: 'verb',
    meaningVi: `nghĩa của ${term}`, definitionEn: null, cefr: null, bandLevel: null,
    collocations: [], examples: [], state: 'NEW', dueDate: '2026-08-06',
    viDistractors: vi, enDistractors: en,
  };
}

/** random() trả cùng một giá trị mỗi lần gọi — đủ để test tất định, không cần seed thật. */
const fixedRandom = (value: number) => () => value;

const FULL = card(1, 'mitigate',
  ['làm trầm trọng thêm', 'phóng đại', 'trì hoãn'],
  ['aggravate', 'exaggerate', 'postpone']);

describe('ratingFor', () => {
  it('sai thì luôn là AGAIN, bất kể nhanh chậm', () => {
    expect(ratingFor(false, 1_000)).toBe('AGAIN');
    expect(ratingFor(false, 90_000)).toBe('AGAIN');
  });

  it('đúng dưới 5s là EASY', () => {
    expect(ratingFor(true, 4_999)).toBe('EASY');
  });

  it('đúng từ 5s tới dưới 15s là GOOD', () => {
    expect(ratingFor(true, 5_000)).toBe('GOOD');
    expect(ratingFor(true, 14_999)).toBe('GOOD');
  });

  it('đúng từ 15s tới 60s là HARD', () => {
    expect(ratingFor(true, 15_000)).toBe('HARD');
    expect(ratingFor(true, 60_000)).toBe('HARD');
  });

  it('đúng trên 60s quay lại GOOD — quá lâu là rời máy, không phải nhớ chật vật', () => {
    expect(ratingFor(true, 60_001)).toBe('GOOD');
  });
});

describe('buildQuestion', () => {
  it('chiều EN_VI hỏi nghĩa: đáp án đúng là meaningVi, mồi nhử là viDistractors', () => {
    const q = buildQuestion(FULL, [], fixedRandom(0));

    expect(q).not.toBeNull();
    expect(q!.direction).toBe('EN_VI');
    expect(q!.options).toHaveLength(4);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
    expect(q!.options).toEqual(expect.arrayContaining(['phóng đại']));
  });

  it('chiều VI_EN hỏi từ: đáp án đúng là term, mồi nhử là enDistractors', () => {
    const q = buildQuestion(FULL, [], fixedRandom(0.99));

    expect(q!.direction).toBe('VI_EN');
    expect(q!.options[q!.correctIndex]).toBe('mitigate');
    expect(q!.options).toEqual(expect.arrayContaining(['aggravate']));
  });

  it('thiếu mồi nhử thì bù bằng thẻ khác trong hàng đợi', () => {
    const bare = card(1, 'mitigate');
    const pool = [bare, card(2, 'resilient'), card(3, 'scrutinise'), card(4, 'coherent')];

    const q = buildQuestion(bare, pool, fixedRandom(0));

    expect(q!.options).toHaveLength(4);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
  });

  it('không lựa chọn nào trùng đáp án đúng', () => {
    const trap = card(1, 'mitigate', ['nghĩa của mitigate', 'phóng đại', 'trì hoãn']);
    const pool = [trap, card(2, 'resilient'), card(3, 'scrutinise')];

    const q = buildQuestion(trap, pool, fixedRandom(0));

    const correct = q!.options[q!.correctIndex];
    expect(q!.options.filter((o) => o === correct)).toHaveLength(1);
  });

  it('không có mồi nhử và hàng đợi chỉ có chính nó thì trả null', () => {
    const lonely = card(1, 'mitigate');

    expect(buildQuestion(lonely, [lonely], fixedRandom(0))).toBeNull();
  });

  it('chỉ bù được 1 mồi nhử thì vẫn dựng được câu 2 lựa chọn', () => {
    const bare = card(1, 'mitigate');
    const pool = [bare, card(2, 'resilient')];

    const q = buildQuestion(bare, pool, fixedRandom(0));

    expect(q!.options).toHaveLength(2);
    expect(q!.options[q!.correctIndex]).toBe('nghĩa của mitigate');
  });

  it('correctIndex luôn trỏ đúng vào đáp án đúng dù trộn kiểu gì', () => {
    for (const r of [0, 0.25, 0.5, 0.75, 0.99]) {
      const q = buildQuestion(FULL, [], fixedRandom(r));
      const expected = q!.direction === 'EN_VI' ? 'nghĩa của mitigate' : 'mitigate';
      expect(q!.options[q!.correctIndex]).toBe(expected);
    }
  });
});
