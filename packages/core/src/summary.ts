import type { TranslateResult } from './types';

/** Rút một dòng ngắn để hiện trong bubble, bất kể payload thuộc hình dạng nào. */
export function shortMeaning(result: TranslateResult): string {
  const payload = result.payload as unknown as Record<string, unknown>;
  const key =
    result.direction === 'EN_VI'
      ? result.mode === 'WORD'
        ? 'meaning_vi'
        : 'translation_vi'
      : result.mode === 'WORD'
        ? 'best_en'
        : 'band65_version';

  const value = payload[key];
  return typeof value === 'string' ? value : '';
}

/** Các mảnh chữ của bubble kết quả theo thiết kế 1a. */
export interface BubbleSummary {
  /** Từ tiếng Anh, in đậm ở dòng đầu. RỖNG khi kết quả là một câu — xem ghi chú dưới. */
  term: string;
  /** Band ước lượng. Rỗng khi payload không có (mọi chiều VI→EN, và mọi kết quả câu). */
  band: string;
  /** Dòng nội dung, nằm dưới dòng từ. Ngôn ngữ của nó ở `meaningLang`. */
  meaning: string;
  /**
   * Ngôn ngữ của `meaning`. Bubble chỉ áp serif (Lora) khi là 'vi' — thiết kế 1a dành mặt
   * chữ serif cho tiếng Việt, đặt tiếng Anh vào đó là sai mặt chữ.
   */
  meaningLang: 'vi' | 'en';
}

function text(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === 'string' ? value : '';
}

/**
 * Rút các mảnh chữ cho bubble kết quả.
 *
 * Hai bất biến của bố cục 1a mà hàm này giữ:
 *
 * 1. Dòng đầu LUÔN là tiếng Anh; dòng nội dung thì KHÔNG luôn — nên nó khai ngôn ngữ của
 *    mình ra ở `meaningLang` thay vì để bubble đoán. Ba trong bốn tổ hợp là tiếng Việt,
 *    riêng VI→EN chế độ CÂU trả `band65_version`, một câu tiếng Anh. Không "sửa" ca đó bằng
 *    cách trả `result.sourceText`: người dùng sẽ nhận lại chính đoạn họ vừa bôi đen, tức
 *    bubble mất hết công dụng.
 * 2. Chế độ dịch CÂU không có "từ": nhét cả câu vào ô đó phá vỡ bố cục ngay ở ca thường
 *    gặp nhất. `term` rỗng là tín hiệu để bubble bỏ hẳn dòng đầu đi.
 */
export function bubbleSummary(result: TranslateResult): BubbleSummary {
  const payload = result.payload as unknown as Record<string, unknown>;

  if (result.mode === 'SENTENCE') {
    return {
      term: '', band: '', meaning: shortMeaning(result),
      meaningLang: result.direction === 'VI_EN' ? 'en' : 'vi',
    };
  }

  if (result.direction === 'VI_EN') {
    // Đảo nguồn so với chiều kia: đáp án tiếng Anh ở payload, còn tiếng Việt chính là đoạn
    // người dùng vừa bôi đen.
    return {
      term: text(payload, 'best_en'), band: '',
      meaning: result.sourceText, meaningLang: 'vi',
    };
  }

  return {
    term: text(payload, 'term') || result.sourceText,
    band: text(payload, 'band_level'),
    meaning: text(payload, 'meaning_vi'),
    meaningLang: 'vi',
  };
}
