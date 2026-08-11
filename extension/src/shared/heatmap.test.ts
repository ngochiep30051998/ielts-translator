import { describe, it, expect } from 'vitest';
import { buildHeatmap, levelFor, parseDay } from './heatmap';
import type { DailyPoint } from './types';

/** `n` ngày liên tục kết thúc ở `endDate`, số lượt do `reviewsFor` quyết định. */
function daily(endDate: string, n: number, reviewsFor: (i: number) => number = () => 0): DailyPoint[] {
  const lastDay = parseDay(endDate);
  const points: DailyPoint[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(lastDay.getFullYear(), lastDay.getMonth(), lastDay.getDate() - i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    points.push({ date: iso, reviews: reviewsFor(n - 1 - i), practice: 0 });
  }
  return points;
}

describe('parseDay', () => {
  it('trả đúng ngày địa phương, không lệch vì UTC', () => {
    // Đây là chốt chặn quan trọng nhất của module. `new Date("2026-08-11")` được JS hiểu là
    // NỬA ĐÊM UTC, nên ở múi giờ âm (ví dụ America/New_York) nó lùi về ngày 10 — cả lưới
    // lệch một ô và không có gì báo.
    //
    // Ba assert này đúng ở MỌI múi giờ khi cài đặt đúng, và sai ở múi giờ âm khi cài đặt
    // dùng `new Date(iso)`. Chạy `TZ=America/New_York npm test -- src/shared/heatmap.test.ts`
    // để thấy nó bắt được lỗi.
    const d = parseDay('2026-08-11');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(7);
    expect(d.getDate()).toBe(11);
  });
});

describe('levelFor', () => {
  it('thang cố định, không co theo giá trị lớn nhất', () => {
    expect(levelFor(0)).toBe(0);
    expect(levelFor(1)).toBe(1);
    expect(levelFor(4)).toBe(1);
    expect(levelFor(5)).toBe(2);
    expect(levelFor(14)).toBe(2);
    expect(levelFor(15)).toBe(3);
    expect(levelFor(29)).toBe(3);
    expect(levelFor(30)).toBe(4);
    expect(levelFor(500)).toBe(4);
  });
});

describe('buildHeatmap', () => {
  it('mảng rỗng cho lưới rỗng', () => {
    expect(buildHeatmap([])).toEqual([]);
  });

  it('mỗi cột đúng 7 ô', () => {
    const columns = buildHeatmap(daily('2026-08-11', 91));
    expect(columns.length).toBeGreaterThanOrEqual(13);
    expect(columns.length).toBeLessThanOrEqual(14);
    for (const c of columns) expect(c).toHaveLength(7);
  });

  it('ô đầu tiên nằm đúng hàng thứ trong tuần của nó', () => {
    // 2026-08-11 là thứ Ba → index 1 (0 = T2). Một ngày duy nhất thì cột đầu có 1 ô đệm
    // ở trên và 5 ô đệm ở dưới.
    const columns = buildHeatmap(daily('2026-08-11', 1));
    expect(columns).toHaveLength(1);
    expect(columns[0][0]).toBeNull();
    expect(columns[0][1]).toEqual({ date: '2026-08-11', reviews: 0, level: 0 });
    expect(columns[0][2]).toBeNull();
  });

  it('giữ nguyên số lượt và gắn đúng mức', () => {
    const columns = buildHeatmap(daily('2026-08-11', 2, (i) => (i === 0 ? 7 : 40)));
    const cells = columns.flat().filter((c): c is NonNullable<typeof c> => c !== null);
    expect(cells).toEqual([
      { date: '2026-08-10', reviews: 7, level: 2 },
      { date: '2026-08-11', reviews: 40, level: 4 },
    ]);
  });

  it('không mất ô nào khi qua nhiều tuần', () => {
    const columns = buildHeatmap(daily('2026-08-11', 91, () => 1));
    const cells = columns.flat().filter((c) => c !== null);
    expect(cells).toHaveLength(91);
  });

  it('ô cuối cùng là ngày cuối của daily', () => {
    // Client KHÔNG tự tính "hôm nay" — phần tử cuối của daily chính là hôm nay theo
    // settings.tz của server.
    const columns = buildHeatmap(daily('2026-08-11', 91));
    const cells = columns.flat().filter((c) => c !== null);
    expect(cells[cells.length - 1]?.date).toBe('2026-08-11');
  });
});
