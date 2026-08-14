/**
 * Giới hạn cứng phía client, khớp với `TranslationService.MAX_TEXT_LENGTH` ở backend.
 * Đổi số ở đây phải đổi đồng bộ bên backend.
 *
 * Chặn ở client không thay thế chặn ở backend — nó chỉ để khỏi đốt một vòng mạng
 * cho thứ backend chắc chắn từ chối.
 */
export const MAX_SELECTION_LENGTH = 1500;

export type SelectionCheck =
  | { ok: true; text: string }
  | { ok: false; reason: 'EMPTY' | 'TOO_LONG' };

export function validateSelection(raw: string): SelectionCheck {
  const text = raw.trim();
  if (text.length === 0) return { ok: false, reason: 'EMPTY' };
  if (text.length > MAX_SELECTION_LENGTH) return { ok: false, reason: 'TOO_LONG' };
  return { ok: true, text };
}
