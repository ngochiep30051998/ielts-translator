import { describe, it, expect } from 'vitest';
import { pageSlots, MAX_PAGE_SLOTS } from './pagination';

describe('pageSlots', () => {
  it('hiện hết mọi trang khi còn vừa chỗ', () => {
    expect(pageSlots(0, 3)).toEqual([0, 1, 2]);
  });

  it('không chèn dấu … khi số trang vừa đúng sức chứa', () => {
    expect(pageSlots(3, MAX_PAGE_SLOTS)).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it('đang ở gần đầu thì dồn dấu … về phía cuối', () => {
    expect(pageSlots(0, 12)).toEqual([0, 1, 2, 3, 4, 'gap', 11]);
  });

  it('đang ở giữa thì có dấu … cả hai bên', () => {
    expect(pageSlots(5, 12)).toEqual([0, 'gap', 4, 5, 6, 'gap', 11]);
  });

  it('đang ở gần cuối thì dồn dấu … về phía đầu', () => {
    expect(pageSlots(11, 12)).toEqual([0, 'gap', 7, 8, 9, 10, 11]);
  });

  it('luôn kèm trang hiện tại, trang đầu và trang cuối', () => {
    for (let current = 0; current < 200; current += 1) {
      const slots = pageSlots(current, 200);
      expect(slots).toContain(current);
      expect(slots).toContain(0);
      expect(slots).toContain(199);
    }
  });

  it('không bao giờ vượt sức chứa dù sổ từ lớn đến đâu', () => {
    for (let current = 0; current < 200; current += 1) {
      expect(pageSlots(current, 200).length).toBeLessThanOrEqual(MAX_PAGE_SLOTS);
    }
  });

  it('không lặp lại một trang nào', () => {
    for (let current = 0; current < 60; current += 1) {
      const numbers = pageSlots(current, 60).filter((s): s is number => s !== 'gap');
      expect(new Set(numbers).size).toBe(numbers.length);
    }
  });

  it('giữ thứ tự tăng dần', () => {
    for (let current = 0; current < 60; current += 1) {
      const numbers = pageSlots(current, 60).filter((s): s is number => s !== 'gap');
      expect([...numbers].sort((a, b) => a - b)).toEqual(numbers);
    }
  });

  it('trả mảng rỗng khi chưa có trang nào', () => {
    expect(pageSlots(0, 0)).toEqual([]);
  });
});
