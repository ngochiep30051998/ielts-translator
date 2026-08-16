import { describe, it, expect } from 'vitest';
import { bubbleSummary, shortMeaning } from './summary';
import type { TranslateResult } from './types';

const base = { cached: false, sourceText: 'x' };

describe('shortMeaning', () => {
  it('lấy meaning_vi cho EN→VI tra từ', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD',
      payload: { meaning_vi: 'tái tạo' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('tái tạo');
  });

  it('lấy translation_vi cho EN→VI tra câu', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'SENTENCE',
      payload: { translation_vi: 'Chính phủ nên đầu tư nhiều hơn.' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('Chính phủ nên đầu tư nhiều hơn.');
  });

  it('lấy best_en cho VI→EN tra từ', () => {
    const result = {
      ...base, direction: 'VI_EN', mode: 'WORD',
      payload: { best_en: 'renewable' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('renewable');
  });

  it('lấy band65_version cho VI→EN tra câu', () => {
    const result = {
      ...base, direction: 'VI_EN', mode: 'SENTENCE',
      payload: { band65_version: 'The government should invest more.' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('The government should invest more.');
  });

  it('trả chuỗi rỗng khi payload thiếu trường mong đợi', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD', payload: {},
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('');
  });
});

describe('bubbleSummary', () => {
  it('EN→VI tra từ: từ tiếng Anh, band, nghĩa tiếng Việt', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD', sourceText: 'deteriorated',
      payload: { term: 'deteriorate', band_level: '7.0', meaning_vi: 'xấu đi, suy giảm' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result)).toEqual({
      term: 'deteriorate', band: '7.0', meaning: 'xấu đi, suy giảm', meaningLang: 'vi',
    });
  });

  it('EN→VI tra từ thiếu term thì lùi về đoạn người dùng bôi đen', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD', sourceText: 'deteriorated',
      payload: { meaning_vi: 'xấu đi' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result).term).toBe('deteriorated');
  });

  it('VI→EN tra từ: từ tiếng Anh là ĐÁP ÁN, dòng nghĩa là đoạn tiếng Việt đã bôi đen', () => {
    // Đảo ngược so với chiều kia, và đó là điểm chính: dòng serif LUÔN là tiếng Việt.
    const result = {
      ...base, direction: 'VI_EN', mode: 'WORD', sourceText: 'suy giảm',
      payload: { best_en: 'deteriorate' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result)).toEqual({
      term: 'deteriorate', band: '', meaning: 'suy giảm', meaningLang: 'vi',
    });
  });

  it('tra câu thì KHÔNG có dòng từ — chỉ một dòng nội dung', () => {
    // Nhét cả câu vào chỗ dành cho một từ sẽ phá vỡ bố cục bubble ngay ở ca thường gặp
    // nhất của chế độ dịch câu.
    const result = {
      ...base, direction: 'EN_VI', mode: 'SENTENCE',
      payload: { translation_vi: 'Chính phủ nên đầu tư nhiều hơn.' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result)).toEqual({
      term: '', band: '', meaning: 'Chính phủ nên đầu tư nhiều hơn.', meaningLang: 'vi',
    });
  });

  it('VI→EN tra CÂU: dòng nghĩa là TIẾNG ANH, nên meaningLang phải là "en"', () => {
    // Ca này từng dùng chung nhánh SENTENCE với EN→VI và nhận class serif (Lora) — mặt chữ
    // dành riêng cho tiếng Việt. `band65_version` là một câu tiếng Anh, đặt vào đó là sai
    // mặt chữ. Không sửa bằng cách trả `sourceText`: người dùng sẽ nhận lại chính đoạn họ
    // vừa bôi đen, tức bubble mất hết công dụng ở ca đó.
    const result = {
      ...base, direction: 'VI_EN', mode: 'SENTENCE',
      sourceText: 'Chính phủ nên đầu tư nhiều hơn.',
      payload: { band65_version: 'The government should invest more.' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result)).toEqual({
      term: '', band: '',
      meaning: 'The government should invest more.',
      meaningLang: 'en',
    });
  });

  it('payload thiếu band thì band rỗng, không phải "undefined"', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD', sourceText: 'x',
      payload: { term: 'mitigate', meaning_vi: 'giảm nhẹ' },
    } as unknown as TranslateResult;

    expect(bubbleSummary(result).band).toBe('');
  });
});
