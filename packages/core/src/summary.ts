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
