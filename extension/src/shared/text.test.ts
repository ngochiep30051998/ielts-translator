import { describe, it, expect } from 'vitest';
import { validateSelection, MAX_SELECTION_LENGTH } from './text';

describe('validateSelection', () => {
  it('chấp nhận text bình thường và trim khoảng trắng', () => {
    expect(validateSelection('  renewable  ')).toEqual({ ok: true, text: 'renewable' });
  });

  it('từ chối chuỗi rỗng', () => {
    expect(validateSelection('   ')).toEqual({ ok: false, reason: 'EMPTY' });
  });

  it('chấp nhận đúng ngưỡng tối đa', () => {
    const atLimit = 'a'.repeat(MAX_SELECTION_LENGTH);
    expect(validateSelection(atLimit)).toEqual({ ok: true, text: atLimit });
  });

  it('từ chối khi vượt ngưỡng', () => {
    expect(validateSelection('a'.repeat(MAX_SELECTION_LENGTH + 1)))
      .toEqual({ ok: false, reason: 'TOO_LONG' });
  });
});
