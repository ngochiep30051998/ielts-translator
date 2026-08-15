import { parseDay } from './heatmap';
import type { VocabEntryDto } from './types';

/**
 * Số lần ôn đúng liên tiếp coi như "đã thuộc" — cũng chính là số vạch của thanh thành thạo
 * trong thiết kế. Hai con số đó phải bằng nhau: thanh đầy mà chữ vẫn nói "ôn sau 6 ngày"
 * là hai kênh thông tin nói ngược nhau trên cùng một dòng.
 */
export const MASTERED_REPETITIONS = 5;

/** Số vạch được tô, từ 0 tới `MASTERED_REPETITIONS`. */
export type MasteryLevel = 0 | 1 | 2 | 3 | 4 | 5;

export interface VocabProgress {
  level: MasteryLevel;
  /** Chữ trạng thái đứng cạnh thanh: "ôn sau 6 ngày" / "đã thuộc" / "hay quên". */
  label: string;
  /**
   * Thẻ đang ở vòng học lại. Thanh phải đổi sang màu cảnh báo chứ không chỉ ngắn đi:
   * SM-2 đặt `repetitions` về 0 khi quên, nên nhìn số vạch thì thẻ hay quên giống hệt
   * thẻ mới tinh.
   */
  lapsed: boolean;
}

/** Số ngày từ `today` tới `iso`, làm tròn theo NGÀY chứ không theo giờ. */
function daysUntil(iso: string, today: Date): number {
  const due = parseDay(iso);
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due.getTime() - from.getTime()) / 86_400_000);
}

function clamp(value: number, min: number, max: number): MasteryLevel {
  return Math.min(max, Math.max(min, value)) as MasteryLevel;
}

/**
 * Suy ra thanh thành thạo + chữ trạng thái của một dòng sổ từ.
 *
 * `today` tiêm từ ngoài để test tất định. Mặc định là ngày của MÁY người dùng, không phải
 * của server — chấp nhận được vì kết quả chỉ là một câu "ôn sau N ngày", lệch nhiều nhất
 * một ngày ở hai đầu múi giờ. (Khác hẳn heatmap: ở đó server gửi sẵn mốc "hôm nay" nên
 * client tự tính là sai thật.)
 */
export function vocabProgress(
  entry: Pick<VocabEntryDto, 'srsState' | 'srsDueDate' | 'srsRepetitions'>,
  today: Date = new Date(),
): VocabProgress {
  // `?? null` chứ không so thẳng với `null`: backend CŨ (chưa deploy bản có ba field này)
  // trả về JSON thiếu hẳn chúng, tức `undefined`. Coi đó là "chưa có thẻ" thì sổ từ vẫn
  // vẽ ra được; so thẳng `=== null` sẽ rơi xuống nhánh dưới và nổ ở `srsDueDate.split`,
  // tức cả tab trắng màn hình chỉ vì backend chậm một nhịp deploy.
  const state = entry.srsState ?? null;
  const dueDate = entry.srsDueDate ?? null;

  // Cả ba cùng null = chưa có thẻ ôn. Đây là trạng thái RIÊNG, không phải "0 lần ôn".
  if (state === null) {
    return { level: 0, label: 'chưa vào lịch ôn', lapsed: false };
  }

  const repetitions = entry.srsRepetitions ?? 0;

  if (state === 'RELEARNING') {
    return { level: clamp(repetitions, 1, MASTERED_REPETITIONS), label: 'hay quên', lapsed: true };
  }

  const level = clamp(repetitions, 0, MASTERED_REPETITIONS);

  if (repetitions >= MASTERED_REPETITIONS) {
    return { level, label: 'đã thuộc', lapsed: false };
  }

  // Có thẻ mà không có ngày hẹn là dữ liệu vỡ, không phải một trạng thái người dùng hiểu
  // được — nói "chưa vào lịch ôn" còn thật hơn là bịa ra một con số ngày.
  if (dueDate === null) {
    return { level, label: 'chưa vào lịch ôn', lapsed: false };
  }

  const days = daysUntil(dueDate, today);
  // Quá hạn cũng chỉ nói "đến hạn": số ngày âm không phải thông tin người học cần, và
  // "ôn sau -3 ngày" thì vô nghĩa.
  return { level, label: days <= 0 ? 'đến hạn' : `ôn sau ${days} ngày`, lapsed: false };
}
