import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ApiClient } from './api-client';
import { buildKeyVocabPayload, createOperations } from './operations';
import type { OperationsPlatform } from './ports';
import type { SaveKeyVocabResult } from './messages';
import type { TranslatePayload, TranslateResult } from './types';

/**
 * Kết quả dịch EN→VI chế độ CÂU với `n` từ đáng học.
 *
 * `sourceSentence` để trống mặc định: đó là ca người dùng gõ tay vào ô Dịch, và cũng là ca
 * dễ sai nhất khi dựng payload.
 */
function sentenceResult(
  terms: { term: string; meaning_vi: string; band_level?: string }[],
  extra: Partial<TranslateResult> = {},
): TranslateResult {
  return {
    direction: 'EN_VI',
    mode: 'SENTENCE',
    cached: false,
    sourceText: 'The government should allocate more funding.',
    payload: {
      translation_vi: 'Chính phủ nên phân bổ nhiều ngân sách hơn.',
      key_vocab: terms,
      structure_note: '',
    } as unknown as TranslatePayload,
    ...extra,
  };
}

const TWO_TERMS = [
  { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
  { term: 'funding', meaning_vi: 'ngân sách', band_level: '6.5' },
];

function makeOperations() {
  const saveVocab = vi.fn().mockResolvedValue({ id: 1, alreadyExists: false });
  const onVocabChanged = vi.fn();
  const platform: OperationsPlatform = {
    lastResult: { get: vi.fn().mockResolvedValue(null), set: vi.fn() },
    auth: { signIn: vi.fn(), signOut: vi.fn(), currentUser: vi.fn() },
    onVocabChanged,
  };
  const handle = createOperations({ saveVocab } as unknown as ApiClient, platform);
  return { handle, saveVocab, onVocabChanged };
}

/** Gửi SAVE_KEY_VOCAB và ép kiểu kết quả — `handle` khai trả `unknown` cho mọi loại request. */
async function saveKeyVocab(
  handle: ReturnType<typeof createOperations>,
  result: TranslateResult,
  tags: string[] = [],
): Promise<SaveKeyVocabResult> {
  return await handle({ type: 'SAVE_KEY_VOCAB', result, tags }) as SaveKeyVocabResult;
}

describe('SAVE_KEY_VOCAB', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lưu từng từ đáng học một, đếm số từ mới', async () => {
    const { handle, saveVocab, onVocabChanged } = makeOperations();

    const outcome = await saveKeyVocab(handle, sentenceResult(TWO_TERMS));

    expect(saveVocab).toHaveBeenCalledTimes(2);
    expect(outcome).toEqual({ saved: 2, existed: 0, failures: [] });
    expect(onVocabChanged).toHaveBeenCalledTimes(1);
  });

  it('đếm riêng những từ backend báo đã có sẵn', async () => {
    const { handle, saveVocab } = makeOperations();
    saveVocab
      .mockResolvedValueOnce({ id: 1, alreadyExists: false })
      .mockResolvedValueOnce({ id: 2, alreadyExists: true });

    const outcome = await saveKeyVocab(handle, sentenceResult(TWO_TERMS));

    expect(outcome).toEqual({ saved: 1, existed: 1, failures: [] });
  });

  it('một từ hỏng KHÔNG chặn những từ sau — lưu được 2 trong 3 vẫn hơn bỏ cả 3', async () => {
    const { handle, saveVocab } = makeOperations();
    saveVocab
      .mockResolvedValueOnce({ id: 1, alreadyExists: false })
      .mockRejectedValueOnce({ code: 'INTERNAL', message: 'Lưu hỏng', retryable: false })
      .mockResolvedValueOnce({ id: 3, alreadyExists: false });

    const outcome = await saveKeyVocab(handle, sentenceResult([
      ...TWO_TERMS, { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
    ]));

    expect(saveVocab).toHaveBeenCalledTimes(3);
    expect(outcome.saved).toBe(2);
    expect(outcome.failures).toEqual([
      { term: 'funding', error: { code: 'INTERNAL', message: 'Lưu hỏng', retryable: false } },
    ]);
  });

  it('lỗi ném ra không đúng hình dạng vẫn thành ApiError chuẩn, không rò nội dung gốc', async () => {
    const { handle, saveVocab } = makeOperations();
    saveVocab.mockRejectedValue(new Error('bể tanh bành'));

    const outcome = await saveKeyVocab(handle, sentenceResult([TWO_TERMS[0]]));

    expect(outcome.failures[0].error).toEqual({
      code: 'INTERNAL', message: 'Lỗi không xác định', retryable: false,
    });
  });

  it('gọi TUẦN TỰ, không chồng lấn — hai POST song song cho hai từ giống nhau là cuộc đua thừa', async () => {
    const { handle, saveVocab } = makeOperations();
    let dangChay = 0;
    let toiDa = 0;
    saveVocab.mockImplementation(async () => {
      dangChay += 1;
      toiDa = Math.max(toiDa, dangChay);
      await new Promise((resolve) => setTimeout(resolve, 0));
      dangChay -= 1;
      return { id: 1, alreadyExists: false };
    });

    await saveKeyVocab(handle, sentenceResult([
      ...TWO_TERMS, { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
    ]));

    expect(toiDa).toBe(1);
  });

  it('báo badge ĐÚNG MỘT LẦN cho cả mẻ, không phải mỗi từ một lần', async () => {
    const { handle, onVocabChanged } = makeOperations();

    await saveKeyVocab(handle, sentenceResult([
      ...TWO_TERMS, { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
    ]));

    expect(onVocabChanged).toHaveBeenCalledTimes(1);
  });

  it('KHÔNG báo badge khi không thêm được từ nào mới', async () => {
    // Badge đếm thẻ đến hạn. Mẻ toàn từ đã có sẵn không thêm thẻ nào, nên số không đổi.
    const { handle, saveVocab, onVocabChanged } = makeOperations();
    saveVocab.mockResolvedValue({ id: 1, alreadyExists: true });

    const outcome = await saveKeyVocab(handle, sentenceResult(TWO_TERMS));

    expect(outcome).toEqual({ saved: 0, existed: 2, failures: [] });
    expect(onVocabChanged).not.toHaveBeenCalled();
  });

  it('không có từ đáng học nào: KHÔNG gọi HTTP lần nào', async () => {
    const { handle, saveVocab, onVocabChanged } = makeOperations();

    const outcome = await saveKeyVocab(handle, {
      direction: 'VI_EN', mode: 'SENTENCE', cached: false, sourceText: 'câu tiếng Việt',
      payload: {
        band65_version: 'x', why_notes: [], key_phrases: ['allocate funding'], avoid: [],
      } as unknown as TranslatePayload,
    });

    expect(saveVocab).not.toHaveBeenCalled();
    expect(onVocabChanged).not.toHaveBeenCalled();
    expect(outcome).toEqual({ saved: 0, existed: 0, failures: [] });
  });

  it('gửi lên payload đã dựng từ chính từ đó, kèm tag người dùng chọn', async () => {
    const { handle, saveVocab } = makeOperations();

    await saveKeyVocab(handle, sentenceResult([TWO_TERMS[0]]), ['Môi trường']);

    expect(saveVocab).toHaveBeenCalledWith(expect.objectContaining({
      term: 'allocate', meaningVi: 'phân bổ', bandLevel: '7.0', tags: ['Môi trường'],
    }));
  });

  it('bỏ trùng trước khi gửi: term lặp chỉ tốn đúng một lượt POST', async () => {
    const { handle, saveVocab } = makeOperations();

    const outcome = await saveKeyVocab(handle, sentenceResult([
      { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
      { term: 'Allocate', meaning_vi: 'cấp phát', band_level: '7.5' },
    ]));

    expect(saveVocab).toHaveBeenCalledTimes(1);
    expect(outcome.saved).toBe(1);
  });
});

describe('buildKeyVocabPayload', () => {
  const ITEM = { term: 'allocate', meaningVi: 'phân bổ', bandLevel: '7.0' };

  it('dùng chính từ đó làm lemma và để trống pos — key_vocab không mang hai thứ này', () => {
    const payload = buildKeyVocabPayload(sentenceResult(TWO_TERMS), ITEM, []);

    expect(payload).toMatchObject({
      term: 'allocate',
      lemma: 'allocate',
      lang: 'en',
      // Chuỗi rỗng chứ không phải 'phrase': đây là TỪ. `pos` còn là một nửa khoá chống
      // trùng `(term, pos)` phía backend, nên bịa ra một giá trị là tạo bản sao.
      pos: '',
      meaningVi: 'phân bổ',
      bandLevel: '7.0',
    });
  });

  it('để null những thứ key_vocab không có, KHÔNG bịa', () => {
    const payload = buildKeyVocabPayload(sentenceResult(TWO_TERMS), ITEM, []);

    expect(payload).toMatchObject({
      ipa: null, definitionEn: null, cefr: null, collocations: [], examples: [],
    });
  });

  it('lấy CÂU ĐANG DỊCH làm ngữ cảnh khi không có câu nguồn từ trang web', () => {
    // `sourceSentence` null khi người dùng gõ tay vào ô Dịch — lúc đó `sourceText` chính là
    // câu đó, và với một từ đáng học thì câu đó LÀ ngữ cảnh của nó.
    const payload = buildKeyVocabPayload(sentenceResult(TWO_TERMS), ITEM, []);

    expect(payload.sourceSentence).toBe('The government should allocate more funding.');
    expect(payload.sourceUrl).toBeNull();
  });

  it('ưu tiên câu ngữ cảnh trên trang khi có', () => {
    const result = sentenceResult(TWO_TERMS, {
      sourceSentence: 'Governments allocate funding every year.',
      sourceUrl: 'https://example.com/a',
    });

    const payload = buildKeyVocabPayload(result, ITEM, []);

    expect(payload.sourceSentence).toBe('Governments allocate funding every year.');
    expect(payload.sourceUrl).toBe('https://example.com/a');
  });

  it('giữ nguyên bandLevel null của từ Gemini không chấm band', () => {
    const payload = buildKeyVocabPayload(
      sentenceResult(TWO_TERMS), { ...ITEM, bandLevel: null }, [],
    );

    expect(payload.bandLevel).toBeNull();
  });
});
