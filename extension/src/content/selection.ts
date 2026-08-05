export const MAX_SELECTION_LENGTH = 1500;
const MAX_CONTEXT_LENGTH = 400;

export type SelectionCheck =
  | { ok: true; text: string }
  | { ok: false; reason: 'EMPTY' | 'TOO_LONG' };

export function validateSelection(raw: string): SelectionCheck {
  const text = raw.trim();
  if (text.length === 0) return { ok: false, reason: 'EMPTY' };
  if (text.length > MAX_SELECTION_LENGTH) return { ok: false, reason: 'TOO_LONG' };
  return { ok: true, text };
}

/**
 * Tìm câu chứa đoạn được chọn. Mở rộng sang trái tới dấu kết câu gần nhất và
 * sang phải tới dấu kết câu tiếp theo. Trả null nếu không tìm thấy selection.
 */
export function extractContextSentence(
  containerText: string,
  selectedText: string,
): string | null {
  const start = containerText.indexOf(selectedText);
  if (start < 0) return null;
  const end = start + selectedText.length;

  let left = 0;
  for (let i = start - 1; i >= 0; i--) {
    if ('.!?'.includes(containerText[i])) {
      left = i + 1;
      break;
    }
  }

  let right = containerText.length;
  for (let i = end; i < containerText.length; i++) {
    if ('.!?'.includes(containerText[i])) {
      right = i + 1;
      break;
    }
  }

  const sentence = containerText.slice(left, right).trim();
  return sentence.length > MAX_CONTEXT_LENGTH
    ? trimAround(sentence, selectedText)
    : sentence;
}

/** Giữ đoạn được chọn ở giữa khi phải cắt bớt câu quá dài. */
function trimAround(sentence: string, selectedText: string): string {
  const index = sentence.indexOf(selectedText);
  const budget = MAX_CONTEXT_LENGTH - selectedText.length;
  const half = Math.max(0, Math.floor(budget / 2));
  const from = Math.max(0, index - half);
  return sentence.slice(from, from + MAX_CONTEXT_LENGTH);
}
