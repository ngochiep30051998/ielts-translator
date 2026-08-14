import type { CardDto, Rating } from './types';

export type QuizDirection = 'EN_VI' | 'VI_EN';

export interface Question {
  direction: QuizDirection;
  card: CardDto;
  /** Đã trộn sẵn. Độ dài 2 tới 4 tuỳ số mồi nhử gom được. */
  options: string[];
  correctIndex: number;
}

const MAX_DISTRACTORS = 3;
const MIN_OPTIONS = 2;

const EASY_UNDER_MS = 5_000;
const GOOD_UNDER_MS = 15_000;
/** Trên mốc này coi như người dùng rời máy, bỏ tín hiệu thời gian đi. */
const AWAY_OVER_MS = 60_000;

/**
 * Suy ra mức SM-2 từ kết quả và thời gian trả lời.
 *
 * Dùng đủ bốn mức là có chủ ý: nếu chỉ có GOOD/AGAIN thì ΔEF chỉ có thể là 0 hoặc
 * −0.32, mọi thẻ sẽ tụt dần về sàn 1.3 và khoảng cách ôn teo lại vĩnh viễn.
 */
export function ratingFor(correct: boolean, elapsedMs: number): Rating {
  if (!correct) return 'AGAIN';
  if (elapsedMs < EASY_UNDER_MS) return 'EASY';
  if (elapsedMs < GOOD_UNDER_MS) return 'GOOD';
  if (elapsedMs > AWAY_OVER_MS) return 'GOOD';
  return 'HARD';
}

/**
 * Dựng một câu trắc nghiệm cho thẻ. Trả null khi không gom nổi tối thiểu 2 lựa chọn —
 * gọi bên ngoài phải bỏ qua thẻ đó chứ không được coi là đã ôn.
 *
 * @param pool hàng đợi đang nạp trong panel, dùng để bù mồi nhử khi thẻ chưa có bộ riêng
 * @param random tiêm vào để test tất định
 */
export function buildQuestion(
  card: CardDto,
  pool: CardDto[],
  random: () => number,
): Question | null {
  const direction: QuizDirection = random() < 0.5 ? 'EN_VI' : 'VI_EN';
  const correct = direction === 'EN_VI' ? card.meaningVi : card.term;

  const own = direction === 'EN_VI' ? card.viDistractors : card.enDistractors;
  const fallback = pool
    .filter((other) => other.id !== card.id)
    .map((other) => (direction === 'EN_VI' ? other.meaningVi : other.term));

  const distractors = pickDistinct([...own, ...fallback], correct, MAX_DISTRACTORS);
  if (distractors.length + 1 < MIN_OPTIONS) {
    return null;
  }

  const options = shuffle([correct, ...distractors], random);
  return { direction, card, options, correctIndex: options.indexOf(correct) };
}

/** Lấy tối đa `max` phần tử khác rỗng, khác nhau, và khác đáp án đúng. */
function pickDistinct(candidates: string[], correct: string, max: number): string[] {
  const seen = new Set<string>([key(correct)]);
  const picked: string[] = [];
  for (const candidate of candidates) {
    if (picked.length >= max) break;
    if (!candidate || !candidate.trim()) continue;
    const k = key(candidate);
    if (seen.has(k)) continue;
    seen.add(k);
    picked.push(candidate);
  }
  return picked;
}

function key(value: string): string {
  return value.trim().toLowerCase();
}

/** Fisher-Yates với nguồn ngẫu nhiên tiêm từ ngoài. */
function shuffle(items: string[], random: () => number): string[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
