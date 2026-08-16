import { describe, it, expect } from 'vitest';
import { keyVocabOf } from './key-vocab';
import type { TranslatePayload, TranslateResult } from './types';

/** Dựng một kết quả dịch với payload tuỳ ý — payload ở đây cố ý được phép "bẩn". */
function result(
  direction: TranslateResult['direction'],
  mode: TranslateResult['mode'],
  payload: unknown,
): TranslateResult {
  return {
    direction, mode, cached: false, sourceText: 'câu nguồn',
    payload: payload as TranslatePayload,
  };
}

const EN_VI_SENTENCE = {
  translation_vi: 'Chính phủ nên phân bổ nhiều ngân sách hơn.',
  key_vocab: [
    { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
    { term: 'funding', meaning_vi: 'ngân sách', band_level: '6.5' },
  ],
  structure_note: 'Câu dùng mệnh đề quan hệ.',
};

describe('keyVocabOf', () => {
  it('EN→VI chế độ CÂU: trả đúng các từ đáng học', () => {
    expect(keyVocabOf(result('EN_VI', 'SENTENCE', EN_VI_SENTENCE))).toEqual([
      { term: 'allocate', meaningVi: 'phân bổ', bandLevel: '7.0' },
      { term: 'funding', meaningVi: 'ngân sách', bandLevel: '6.5' },
    ]);
  });

  it('EN→VI chế độ TỪ: rỗng — nút "Lưu từ" sẵn có đã làm đúng việc đó', () => {
    expect(keyVocabOf(result('EN_VI', 'WORD', {
      term: 'renewable', meaning_vi: 'tái tạo', band_level: '6.5',
    }))).toEqual([]);
  });

  it('VI→EN chế độ CÂU: rỗng — key_phrases là chuỗi trần, không có nghĩa tiếng Việt', () => {
    // Backend bắt buộc `meaning_vi`, nên dựng mục sổ từ từ `key_phrases` là bịa nghĩa.
    expect(keyVocabOf(result('VI_EN', 'SENTENCE', {
      band65_version: 'The government should allocate more funding.',
      why_notes: [], key_phrases: ['allocate funding'], avoid: [],
    }))).toEqual([]);
  });

  it('VI→EN chế độ TỪ: rỗng', () => {
    expect(keyVocabOf(result('VI_EN', 'WORD', {
      best_en: 'renewable', alternatives: [], collocations: [], examples: [],
    }))).toEqual([]);
  });

  it('CHIỀU sai nhưng payload có key_vocab: vẫn rỗng', () => {
    // Bốn ca "đủ tổ hợp" ở trên xanh một cách RỖNG RUỘT: payload của ba tổ hợp kia vốn
    // không có khoá `key_vocab`, nên chúng trả rỗng kể cả khi guard bị gỡ hẳn. Đây là ca
    // duy nhất phân biệt được — nó chết ngay nếu ai đó bỏ vế `direction` khỏi guard.
    expect(keyVocabOf(result('VI_EN', 'SENTENCE', {
      key_vocab: [{ term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' }],
    }))).toEqual([]);
  });

  it('CHẾ ĐỘ sai nhưng payload có key_vocab: vẫn rỗng', () => {
    // Cặp với ca trên: ca này chết nếu ai đó bỏ vế `mode` khỏi guard.
    expect(keyVocabOf(result('EN_VI', 'WORD', {
      key_vocab: [{ term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' }],
    }))).toEqual([]);
  });

  it('payload méo (null) thì trả rỗng chứ KHÔNG ném', () => {
    // Hàm này chạy ở thì render của tab Dịch. Ném ở đây làm trắng cả tab, chứ không chỉ
    // hỏng một lượt lưu — `lastResult` đến từ bộ nhớ ngoài tiến trình nên có thể méo.
    const meo = { ...result('EN_VI', 'SENTENCE', {}), payload: null } as never;
    expect(() => keyVocabOf(meo)).not.toThrow();
    expect(keyVocabOf(meo)).toEqual([]);
  });

  it('bỏ phần tử có term hoặc nghĩa rỗng/toàn khoảng trắng', () => {
    // Backend trả 400 cho chúng; lọc ở đây thay vì đẻ ra lỗi cho người dùng đọc.
    const items = keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: [
        { term: '   ', meaning_vi: 'phân bổ', band_level: '7.0' },
        { term: 'funding', meaning_vi: '  ', band_level: '6.5' },
        { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
      ],
    }));

    expect(items).toEqual([{ term: 'mitigate', meaningVi: 'giảm nhẹ', bandLevel: '7.5' }]);
  });

  it('bỏ trùng theo term, không phân biệt hoa thường và bỏ qua khoảng trắng thừa', () => {
    // Gemini có lặp từ; hai lượt POST cùng một term chỉ tổ làm số đếm khó hiểu.
    const items = keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: [
        { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
        { term: '  Allocate ', meaning_vi: 'cấp phát', band_level: '7.5' },
        { term: 'funding', meaning_vi: 'ngân sách', band_level: '6.5' },
      ],
    }));

    // Giữ bản ĐẦU TIÊN, bỏ bản sau.
    expect(items).toEqual([
      { term: 'allocate', meaningVi: 'phân bổ', bandLevel: '7.0' },
      { term: 'funding', meaningVi: 'ngân sách', bandLevel: '6.5' },
    ]);
  });

  it('giữ nguyên thứ tự backend trả về — đó là thứ tự xuất hiện trong câu', () => {
    const items = keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: [
        { term: 'zebra', meaning_vi: 'ngựa vằn', band_level: '5.0' },
        { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
        { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
      ],
    }));

    expect(items.map((i) => i.term)).toEqual(['zebra', 'allocate', 'mitigate']);
  });

  it('key_vocab vắng mặt: rỗng, không ném', () => {
    expect(keyVocabOf(result('EN_VI', 'SENTENCE', { translation_vi: 'x' }))).toEqual([]);
  });

  it('key_vocab không phải mảng: rỗng, không ném', () => {
    expect(keyVocabOf(result('EN_VI', 'SENTENCE', { key_vocab: 'allocate' }))).toEqual([]);
    expect(keyVocabOf(result('EN_VI', 'SENTENCE', { key_vocab: null }))).toEqual([]);
  });

  it('phần tử không phải object thì bỏ qua, phần tử tốt vẫn giữ', () => {
    const items = keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: ['allocate', null, 42, { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' }],
    }));

    expect(items).toEqual([{ term: 'mitigate', meaningVi: 'giảm nhẹ', bandLevel: '7.5' }]);
  });

  it('band_level vắng mặt hoặc rỗng thành null, KHÔNG thành chuỗi rỗng', () => {
    // `bandLevel` đi thẳng vào sổ từ. Chuỗi rỗng ở đó hiện thành một pill band trống.
    const items = keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: [
        { term: 'allocate', meaning_vi: 'phân bổ' },
        { term: 'funding', meaning_vi: 'ngân sách', band_level: '  ' },
      ],
    }));

    expect(items).toEqual([
      { term: 'allocate', meaningVi: 'phân bổ', bandLevel: null },
      { term: 'funding', meaningVi: 'ngân sách', bandLevel: null },
    ]);
  });

  it('trim term và nghĩa trước khi trả — chúng đi thẳng vào sổ từ', () => {
    expect(keyVocabOf(result('EN_VI', 'SENTENCE', {
      key_vocab: [{ term: '  allocate ', meaning_vi: ' phân bổ  ', band_level: ' 7.0 ' }],
    }))).toEqual([{ term: 'allocate', meaningVi: 'phân bổ', bandLevel: '7.0' }]);
  });
});
