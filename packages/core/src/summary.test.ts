import { describe, it, expect } from 'vitest';
import { shortMeaning } from './summary';
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
