import { describe, it, expect } from 'vitest';
import {
  dailyGoal, estimateMinutes, formatVietnameseDate, recallPercent, sparkline,
  streakLevel, topicMastery, weakestTopics,
} from './today';
import type { DailyPoint, VocabTag } from './types';

function day(date: string, reviews: number, practice = 0): DailyPoint {
  return { date, reviews, practice };
}

function tag(name: string, count: number, mastered: number): VocabTag {
  return { tag: name, count, mastered };
}

describe('formatVietnameseDate', () => {
  it('chủ nhật gọi đúng tên, không phải "Thứ 1"', () => {
    // 2026-08-16 là Chủ nhật. `new Date(y, m, d)` chứ không chuỗi ISO: chuỗi ISO được đọc
    // theo UTC nên ở múi giờ âm nó lùi một ngày và test đỏ tuỳ máy.
    expect(formatVietnameseDate(new Date(2026, 7, 16))).toBe('Chủ nhật, 16/08');
  });

  it('thứ Năm ra "Thứ 5" và ngày/tháng có số 0 ở đầu', () => {
    expect(formatVietnameseDate(new Date(2026, 7, 6))).toBe('Thứ 5, 06/08');
  });
});

describe('dailyGoal', () => {
  it('mục tiêu = đã xong + còn đến hạn', () => {
    expect(dailyGoal(18, 11)).toMatchObject({ done: 18, remaining: 11, total: 29 });
  });

  it('tỉ lệ nằm trong 0..1', () => {
    expect(dailyGoal(18, 11).ratio).toBeCloseTo(18 / 29);
  });

  it('không còn thẻ nào thì tỉ lệ là 0, KHÔNG phải NaN', () => {
    // 0/0 = NaN, và NaN lọt vào `conic-gradient` làm vòng tròn biến mất hoàn toàn — không
    // lỗi nào nổ ra, chỉ là một khoảng trống.
    const goal = dailyGoal(0, 0);
    expect(goal.total).toBe(0);
    expect(goal.ratio).toBe(0);
  });

  it('ôn xong hết thì tỉ lệ là 1', () => {
    expect(dailyGoal(29, 0).ratio).toBe(1);
  });
});

describe('estimateMinutes', () => {
  it('không còn thẻ thì 0 phút', () => {
    expect(estimateMinutes(0)).toBe(0);
  });

  it('một vài thẻ vẫn làm tròn LÊN 1 phút, không phải 0', () => {
    // "Khoảng 0 phút nữa" đọc như đã xong trong khi vẫn còn thẻ.
    expect(estimateMinutes(2)).toBe(1);
  });

  it('20 thẻ ra khoảng 4 phút', () => {
    expect(estimateMinutes(20)).toBe(4);
  });
});

describe('recallPercent', () => {
  it('tỉ lệ nhớ = 1 − again/tổng', () => {
    expect(recallPercent({ again: 2, hard: 3, good: 4, easy: 1 })).toBe(80);
  });

  it('chưa có lượt tự chấm nào thì null, KHÔNG phải 0%', () => {
    // 0% đọc là "quên sạch", trong khi sự thật là "chưa ôn lần nào".
    expect(recallPercent({ again: 0, hard: 0, good: 0, easy: 0 })).toBeNull();
  });
});

describe('topicMastery', () => {
  it('phần trăm làm tròn từ mastered/count', () => {
    expect(topicMastery(tag('Môi trường', 24, 17)).percent).toBe(71);
  });

  it('chủ đề rỗng không chia cho 0', () => {
    expect(topicMastery(tag('Trống', 0, 0)).percent).toBe(0);
  });

  it('backend cũ chưa trả `mastered` thì coi như 0, không phải NaN', () => {
    // Trước khi backend deploy field mới, JSON thiếu hẳn nó — `undefined/24` là NaN và
    // thanh thành thạo biến mất mà không có lỗi nào.
    const cu = { tag: 'Kinh tế', count: 20 } as VocabTag;
    expect(topicMastery(cu)).toMatchObject({ mastered: 0, percent: 0 });
  });
});

describe('weakestTopics', () => {
  const TAGS = [
    tag('Môi trường', 24, 17),   // 71%
    tag('Giáo dục', 19, 10),     // 53%
    tag('Kinh tế', 17, 6),       // 35%
    tag('Y tế', 8, 8),           // 100%
  ];

  it('lấy chủ đề % thấp nhất trước', () => {
    expect(weakestTopics(TAGS).map((t) => t.tag))
      .toEqual(['Kinh tế', 'Giáo dục', 'Môi trường']);
  });

  it('không lấy quá 3 chủ đề', () => {
    expect(weakestTopics(TAGS)).toHaveLength(3);
  });

  it('sổ chưa có chủ đề nào thì trả mảng rỗng', () => {
    expect(weakestTopics([])).toEqual([]);
  });
});

describe('sparkline', () => {
  const WEEK = [
    day('2026-08-09', 4), day('2026-08-10', 7), day('2026-08-11', 0, 5),
    day('2026-08-12', 8), day('2026-08-13', 6), day('2026-08-14', 10),
    day('2026-08-15', 7),
  ];

  it('lấy 7 ngày CUỐI của mảng 91 ngày', () => {
    const daily = [...Array(84).keys()].map((i) => day(`2026-05-${i}`, 99)).concat(WEEK);
    expect(sparkline(daily)).toHaveLength(7);
    expect(sparkline(daily)[0].date).toBe('2026-08-09');
  });

  it('chiều cao tính theo ngày cao nhất trong tuần', () => {
    const bars = sparkline(WEEK);
    expect(bars[5].height).toBe(100);
    expect(bars[0].height).toBe(40);
  });

  it('đánh dấu ngày đạt đỉnh để tô đậm', () => {
    expect(sparkline(WEEK).filter((b) => b.peak)).toHaveLength(1);
  });

  it('cả tuần không học thì mọi cột cao 0, KHÔNG chia cho 0', () => {
    const nghi = WEEK.map((p) => day(p.date, 0));
    expect(sparkline(nghi).every((b) => b.height === 0)).toBe(true);
  });

  it('cộng cả lượt luyện thêm — cột này là "có học", không phải "có ôn"', () => {
    expect(sparkline(WEEK)[2].total).toBe(5);
  });
});

describe('streakLevel', () => {
  it('có ôn theo lịch là mức đầy', () => {
    expect(streakLevel(day('2026-08-15', 3))).toBe('on');
  });

  it('chỉ luyện thêm là mức nửa — luyện KHÔNG nối chuỗi', () => {
    expect(streakLevel(day('2026-08-15', 0, 4))).toBe('half');
  });

  it('không học gì là mức trống', () => {
    expect(streakLevel(day('2026-08-15', 0))).toBe('off');
  });
});
