import type { DailyPoint, RecallBreakdown, VocabTag } from './types';

/**
 * Số liệu của màn Hôm nay — hàm thuần, không chạm mạng và không chạm React.
 *
 * Tách ra khỏi `HomeTab` vì mọi ca lắt léo của màn đó đều là số học: sổ từ rỗng, chưa ôn
 * lượt nào, chủ đề chưa có từ nào thuộc. Ba ca đó đều dẫn tới một phép chia cho 0, và một
 * `NaN` lọt vào `conic-gradient` hay `width` chỉ làm hình biến mất — không lỗi, không dấu
 * vết. Ở đây chúng test được thẳng.
 */

/**
 * Giây ước lượng cho mỗi thẻ ôn.
 *
 * ƯỚC LƯỢNG THÔ, cố ý không đo thật: câu "Khoảng N phút nữa" là để người học biết mình sắp
 * xong hay còn lâu, không phải một cam kết. Đo thời gian thật cho từng người rồi trung bình
 * là một cột dữ liệu mới ở backend cho một dòng chữ động viên — không đáng.
 */
export const SECONDS_PER_CARD = 12;

/** Số ô trong dải streak — đúng một tuần. */
export const STREAK_DAYS = 7;

/** Tối đa bao nhiêu chủ đề yếu được liệt kê ở màn Hôm nay. */
const WEAK_TOPIC_LIMIT = 3;

/** `getDay()` trả 0 cho Chủ nhật, nên mảng này bắt đầu từ Chủ nhật. */
const WEEKDAYS = ['Chủ nhật', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'];

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/**
 * "Thứ 5, 14/08" — dòng ngày ở đầu màn Hôm nay.
 *
 * Đọc ngày của MÁY người dùng chứ không của server. Chấp nhận được: đây là dòng chào, không
 * phải mốc tính lịch ôn (mốc đó do backend gửi sẵn trong `daily`).
 */
export function formatVietnameseDate(date: Date): string {
  return `${WEEKDAYS[date.getDay()]}, ${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}`;
}

export interface DailyGoal {
  /** Số lượt ôn theo lịch đã làm hôm nay. */
  done: number;
  /** Số thẻ còn đến hạn. */
  remaining: number;
  /** `done + remaining` — mẫu số của vòng tròn tiến độ. */
  total: number;
  /** 0..1, dùng thẳng cho `conic-gradient`. */
  ratio: number;
}

/**
 * Mục tiêu hôm nay.
 *
 * Backend KHÔNG có khái niệm "mục tiêu": nó chỉ biết còn bao nhiêu thẻ đến hạn
 * (`GET_SRS_STATS`) và hôm nay đã ôn bao nhiêu lượt (phần tử cuối của `StatsDto.daily`).
 * Mẫu số 29 trong thiết kế chính là tổng hai con số đó.
 */
export function dailyGoal(reviewsToday: number, dueCount: number): DailyGoal {
  const total = reviewsToday + dueCount;
  return {
    done: reviewsToday,
    remaining: dueCount,
    total,
    // Sổ chưa có thẻ nào tới hạn thì 0/0 = NaN, và NaN trong `conic-gradient` làm vòng tròn
    // biến mất hoàn toàn mà không có lỗi nào nổ ra.
    ratio: total === 0 ? 0 : reviewsToday / total,
  };
}

/** Ước lượng thô số phút còn lại. 0 nghĩa là không còn gì để ôn. */
export function estimateMinutes(dueCount: number): number {
  if (dueCount <= 0) return 0;
  // Làm tròn LÊN tối thiểu 1: "Khoảng 0 phút nữa" đọc như đã xong trong khi vẫn còn thẻ.
  return Math.max(1, Math.round((dueCount * SECONDS_PER_CARD) / 60));
}

/**
 * Tỉ lệ nhớ 0..100.
 *
 * `null` = chưa có lượt tự chấm nào. Khác hẳn 0: 0% đọc là "quên sạch", còn sự thật là
 * "chưa ôn lần nào".
 */
export function recallPercent(recall: RecallBreakdown): number | null {
  const total = recall.again + recall.hard + recall.good + recall.easy;
  if (total === 0) return null;
  return Math.round(((total - recall.again) / total) * 100);
}

export interface TopicMastery {
  tag: string;
  count: number;
  mastered: number;
  /** 0..100, đã làm tròn. */
  percent: number;
}

export function topicMastery(tag: VocabTag): TopicMastery {
  // `?? 0` chứ không đọc thẳng: backend CHƯA deploy field `mastered` trả JSON thiếu hẳn nó,
  // và `undefined / count` là NaN — thanh thành thạo biến mất mà không có gì đỏ.
  const mastered = tag.mastered ?? 0;
  return {
    tag: tag.tag,
    count: tag.count,
    mastered,
    percent: tag.count === 0 ? 0 : Math.round((mastered / tag.count) * 100),
  };
}

/**
 * Các chủ đề thành thạo thấp nhất, tối đa 3.
 *
 * Bằng % thì chủ đề NHIỀU TỪ hơn đứng trước — nó là chỗ còn nhiều việc phải làm hơn.
 */
export function weakestTopics(tags: VocabTag[], limit = WEAK_TOPIC_LIMIT): TopicMastery[] {
  return tags
    .map(topicMastery)
    .sort((a, b) => a.percent - b.percent || b.count - a.count)
    .slice(0, limit);
}

export interface SparkBar {
  date: string;
  /** Tổng lượt học trong ngày: ôn theo lịch + luyện thêm. */
  total: number;
  /** 0..100, so với ngày cao nhất của tuần. */
  height: number;
  /** Ngày đạt đỉnh tuần — tô đậm hơn các cột còn lại. */
  peak: boolean;
}

/**
 * Bảy cột của sparkline "tỉ lệ nhớ".
 *
 * `slice(-STREAK_DAYS)` chứ không `slice(0, 7)`: `daily` dài 91 phần tử và LUÔN kết thúc ở
 * hôm nay, nên lấy đầu mảng là vẽ tuần của ba tháng trước — không có gì đỏ cả.
 */
export function sparkline(daily: DailyPoint[]): SparkBar[] {
  const week = daily.slice(-STREAK_DAYS);
  const totals = week.map((point) => point.reviews + point.practice);
  const max = Math.max(...totals, 0);
  return week.map((point, i) => ({
    date: point.date,
    total: totals[i],
    // Cả tuần nghỉ thì max = 0 — chia cho nó ra NaN và cả dải cột biến mất.
    height: max === 0 ? 0 : Math.round((totals[i] / max) * 100),
    peak: max > 0 && totals[i] === max,
  }));
}

/**
 * Ba mức của một ô trong dải streak.
 *
 * `half` tồn tại vì `reviews` và `practice` là hai field RIÊNG ở backend: streak chỉ đếm
 * lượt ôn theo lịch. Một ngày chỉ luyện thêm KHÔNG nối chuỗi, nhưng cũng không phải ngày bỏ
 * trống — tô nó y hệt ngày không học là xoá công của người dùng, tô y hệt ngày có ôn là nói
 * dối về chuỗi.
 */
export function streakLevel(point: DailyPoint): 'on' | 'half' | 'off' {
  if (point.reviews > 0) return 'on';
  if (point.practice > 0) return 'half';
  return 'off';
}
