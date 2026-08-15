import { describe, it, expect } from 'vitest';
import { MASTERED_REPETITIONS, vocabProgress } from './vocab-progress';
import type { VocabEntryDto } from './types';

/** Chỉ ba field SRS — đúng phần mà `vocabProgress` đọc. */
function srs(
  patch: Partial<Pick<VocabEntryDto, 'srsState' | 'srsDueDate' | 'srsRepetitions'>>,
): Pick<VocabEntryDto, 'srsState' | 'srsDueDate' | 'srsRepetitions'> {
  return { srsState: null, srsDueDate: null, srsRepetitions: null, ...patch };
}

const HOM_NAY = new Date(2026, 7, 15);   // 15/08/2026, giờ địa phương

describe('vocabProgress', () => {
  it('cả ba field null là "chưa vào lịch ôn", KHÔNG phải "đang tải"', () => {
    // Từ vừa lưu chưa có thẻ ôn nào. Vẽ nó y hệt một dòng loading là nói dối người dùng.
    const p = vocabProgress(srs({}), HOM_NAY);

    expect(p.level).toBe(0);
    expect(p.label).toBe('chưa vào lịch ôn');
    expect(p.lapsed).toBe(false);
  });

  it('đủ số lần ôn thì báo "đã thuộc" và tô kín 5 vạch', () => {
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-09-20', srsRepetitions: MASTERED_REPETITIONS }),
      HOM_NAY,
    );

    expect(p.level).toBe(5);
    expect(p.label).toBe('đã thuộc');
  });

  it('vượt mốc thuộc vẫn dừng ở 5 vạch, không tràn', () => {
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-12-01', srsRepetitions: 42 }),
      HOM_NAY,
    );

    expect(p.level).toBe(5);
  });

  it('thẻ đang học lại là "hay quên" và được đánh dấu lapsed', () => {
    // SM-2 đặt repetitions về 0 khi quên, nên nếu chỉ nhìn số lần ôn thì thẻ này giống hệt
    // một thẻ mới — mà hai chuyện đó cần hai màu khác nhau.
    const p = vocabProgress(
      srs({ srsState: 'RELEARNING', srsDueDate: '2026-08-15', srsRepetitions: 0 }),
      HOM_NAY,
    );

    expect(p.label).toBe('hay quên');
    expect(p.lapsed).toBe(true);
    // Luôn còn ít nhất một vạch: thanh trống trơn không phân biệt được với "chưa có thẻ".
    expect(p.level).toBe(1);
  });

  it('đang chờ tới hạn thì đếm số ngày còn lại', () => {
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-08-21', srsRepetitions: 3 }),
      HOM_NAY,
    );

    expect(p.label).toBe('ôn sau 6 ngày');
    expect(p.level).toBe(3);
  });

  it('đến hạn hôm nay thì nói "đến hạn", không phải "ôn sau 0 ngày"', () => {
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-08-15', srsRepetitions: 2 }),
      HOM_NAY,
    );

    expect(p.label).toBe('đến hạn');
  });

  it('quá hạn cũng là "đến hạn", không đếm ngày âm', () => {
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-08-01', srsRepetitions: 2 }),
      HOM_NAY,
    );

    expect(p.label).toBe('đến hạn');
  });

  it('thẻ mới chưa ôn lần nào thì thanh trống nhưng vẫn có chữ trạng thái', () => {
    const p = vocabProgress(
      srs({ srsState: 'NEW', srsDueDate: '2026-08-15', srsRepetitions: 0 }),
      HOM_NAY,
    );

    expect(p.level).toBe(0);
    expect(p.label).toBe('đến hạn');
    expect(p.lapsed).toBe(false);
  });

  it('backend cũ thiếu hẳn ba field cũng chỉ là "chưa vào lịch ôn", không nổ', () => {
    // Trong lúc backend chưa deploy bản có ba field SRS, JSON trả về KHÔNG có chúng —
    // `undefined` chứ không `null`. Nổ ở đây là cả tab Sổ từ trắng màn hình.
    const p = vocabProgress({} as Parameters<typeof vocabProgress>[0], HOM_NAY);

    expect(p).toEqual({ level: 0, label: 'chưa vào lịch ôn', lapsed: false });
  });

  it('không lệch một ngày ở múi giờ dương — chuỗi ngày parse theo giờ địa phương', () => {
    // `new Date("2026-08-16")` là nửa đêm UTC; ở UTC+7 nó vẫn là ngày 16 nhưng ở UTC-5 lại
    // thành ngày 15. Sai một ngày ở đây không làm gì đỏ, chỉ khiến mọi mốc hẹn lệch đi một.
    const p = vocabProgress(
      srs({ srsState: 'REVIEW', srsDueDate: '2026-08-16', srsRepetitions: 1 }),
      new Date(2026, 7, 15, 23, 30),
    );

    expect(p.label).toBe('ôn sau 1 ngày');
  });
});
