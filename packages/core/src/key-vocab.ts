import type { TranslateResult } from './types';

/**
 * Một từ đáng học đã được làm sạch, sẵn sàng dựng thành mục sổ từ.
 *
 * Đây KHÔNG phải bản gương của backend — nó là dạng đã chuẩn hoá của phần tử `key_vocab`
 * trong `EnViSentencePayload`: đã trim, đã bỏ rác, và `band_level` rỗng đã thành `null`.
 */
export interface KeyVocabItem {
  term: string;
  meaningVi: string;
  /** `null` = Gemini không chấm band cho từ này, KHÔNG phải "band bằng rỗng". */
  bandLevel: string | null;
}

/** Chuỗi đã trim, hoặc rỗng nếu giá trị không phải chuỗi. Payload từ Gemini không đảm bảo gì. */
function trimmed(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * Các từ đáng học rút từ một kết quả dịch. Rỗng nếu kết quả không phải EN→VI chế độ CÂU.
 *
 * Đúng MỘT tổ hợp direction × mode có `key_vocab`. Ba tổ hợp còn lại trả rỗng, và đó là
 * cách nút "Lưu N từ đáng học" tự biết lúc nào không nên có mặt:
 *
 * - `EN_VI` + `WORD` — nút "Lưu từ" sẵn có đã lưu đúng từ đó rồi.
 * - `VI_EN` + `SENTENCE` — có `key_phrases`, nhưng đó là mảng chuỗi TRẦN, không mang nghĩa
 *   tiếng Việt. Backend bắt buộc `meaning_vi`, nên dựng mục sổ từ từ chúng là bịa nghĩa.
 * - `VI_EN` + `WORD` — không có khái niệm này.
 *
 * Đọc `payload` phòng thủ y như `buildVocabPayload`: nó là JSON do Gemini sinh, `key_vocab`
 * có thể vắng mặt, có thể không phải mảng, và có thể lẫn phần tử rác.
 */
export function keyVocabOf(result: TranslateResult): KeyVocabItem[] {
  if (result.direction !== 'EN_VI' || result.mode !== 'SENTENCE') return [];

  // Phòng thủ cả chính `payload`, không chỉ `key_vocab` bên trong nó. Kiểu khai là non-null
  // nhưng giá trị thật đến từ bộ nhớ ngoài tiến trình (sessionStorage bên web, bộ nhớ service
  // worker bên extension) và có thể méo. Hàm này chạy ở THÌ RENDER của tab Dịch, nên ném ở
  // đây làm trắng cả tab — khác hẳn `buildVocabPayload` vốn chỉ chạy khi bấm nút.
  const payload = result.payload as unknown as Record<string, unknown> | null | undefined;
  const raw = payload?.key_vocab;
  if (!Array.isArray(raw)) return [];

  const items: KeyVocabItem[] = [];
  /** Term đã lấy, dạng thường hoá — chỉ để bỏ trùng, không dùng để hiển thị. */
  const seen = new Set<string>();

  for (const entry of raw) {
    if (typeof entry !== 'object' || entry === null) continue;
    const row = entry as Record<string, unknown>;

    const term = trimmed(row.term);
    const meaningVi = trimmed(row.meaning_vi);
    // Backend trả 400 cho term/nghĩa rỗng. Lọc ở đây thay vì đẻ ra một lỗi cho người dùng đọc.
    if (!term || !meaningVi) continue;

    // Gemini có lặp từ trong một câu; hai lượt POST cùng một term chỉ tổ làm số đếm khó hiểu.
    const key = term.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    const bandLevel = trimmed(row.band_level);
    items.push({ term, meaningVi, bandLevel: bandLevel || null });
  }

  // KHÔNG sắp lại: thứ tự backend trả về là thứ tự các từ xuất hiện trong câu.
  return items;
}
