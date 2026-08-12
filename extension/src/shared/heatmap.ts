import type { DailyPoint } from './types';

/** Năm mức đậm nhạt. 0 là ô trống (không ôn ngày đó). */
export type Level = 0 | 1 | 2 | 3 | 4;

export interface Cell {
  date: string;
  reviews: number;
  level: Level;
}

/** Một cột = một tuần, ĐÚNG 7 ô theo thứ tự T2→CN. `null` là ô đệm ngoài khoảng dữ liệu. */
export type Column = (Cell | null)[];

/**
 * Ngưỡng CỐ ĐỊNH, không co theo giá trị lớn nhất của bộ dữ liệu.
 *
 * Thang co theo max làm tuần lười nhất trông y hệt tháng chăm nhất — màu phải mang cùng một
 * nghĩa vào tháng 1 và tháng 6, nếu không biểu đồ chỉ còn là trang trí.
 */
export function levelFor(reviews: number): Level {
  if (reviews <= 0) return 0;
  if (reviews < 5) return 1;
  if (reviews < 15) return 2;
  if (reviews < 30) return 3;
  return 4;
}

/**
 * Parse "YYYY-MM-DD" thành Date GIỜ ĐỊA PHƯƠNG.
 *
 * TUYỆT ĐỐI không dùng `new Date(iso)`: chuỗi chỉ-có-ngày được JS hiểu là nửa đêm UTC, nên ở
 * múi giờ âm `.getDay()` trả về thứ của ngày HÔM TRƯỚC. Cả lưới lệch một ô, không exception,
 * không test nào đỏ trừ test viết riêng cho nó.
 */
export function parseDay(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/** 0 = T2 … 6 = CN. `getDay()` trả 0 cho Chủ nhật nên phải xoay. */
function weekdayIndex(day: Date): number {
  return (day.getDay() + 6) % 7;
}

/**
 * Dựng lưới heatmap từ mảng `daily` của backend.
 *
 * Client KHÔNG tự tính "hôm nay": phần tử cuối của `daily` CHÍNH LÀ hôm nay theo
 * `settings.tz` của server. Gọi `new Date()` ở đây là mở lại đúng cái lỗ múi giờ mà backend
 * vừa bịt bằng `AT TIME ZONE`.
 *
 * 91 ngày cộng ô đệm ra 13 hoặc 14 cột, tuỳ ngày đầu rơi vào thứ mấy.
 */
export function buildHeatmap(daily: DailyPoint[]): Column[] {
  if (daily.length === 0) return [];

  const cells: (Cell | null)[] = Array<Cell | null>(weekdayIndex(parseDay(daily[0].date))).fill(null);
  for (const point of daily) {
    cells.push({ date: point.date, reviews: point.reviews, level: levelFor(point.reviews) });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const columns: Column[] = [];
  for (let i = 0; i < cells.length; i += 7) columns.push(cells.slice(i, i + 7));
  return columns;
}
