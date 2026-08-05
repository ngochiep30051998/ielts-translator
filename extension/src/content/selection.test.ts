import { describe, it, expect } from 'vitest';
import { validateSelection, extractContextSentence, MAX_SELECTION_LENGTH } from './selection';

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

describe('extractContextSentence', () => {
  const paragraph =
    'The sun is hot. We need renewable energy now. It is urgent.';

  it('lấy đúng câu chứa từ được chọn', () => {
    expect(extractContextSentence(paragraph, 'renewable'))
      .toBe('We need renewable energy now.');
  });

  it('lấy câu đầu tiên khi từ nằm ở câu đầu', () => {
    expect(extractContextSentence(paragraph, 'sun')).toBe('The sun is hot.');
  });

  it('gộp cả hai câu khi selection trải qua ranh giới câu', () => {
    expect(extractContextSentence(paragraph, 'now. It is'))
      .toBe('We need renewable energy now. It is urgent.');
  });

  it('trả toàn bộ text khi không có dấu kết câu', () => {
    expect(extractContextSentence('renewable energy sources', 'energy'))
      .toBe('renewable energy sources');
  });

  it('xử lý được dấu chấm hỏi và chấm than', () => {
    expect(extractContextSentence('Is it hot? Yes it is!', 'Yes')).toBe('Yes it is!');
  });

  it('xử lý được câu tiếng Việt có dấu', () => {
    const text = 'Trời rất nóng. Chúng ta cần năng lượng tái tạo. Việc này gấp.';
    expect(extractContextSentence(text, 'tái tạo'))
      .toBe('Chúng ta cần năng lượng tái tạo.');
  });

  it('trả null khi không tìm thấy selection trong container', () => {
    expect(extractContextSentence(paragraph, 'không tồn tại')).toBeNull();
  });

  it('cắt bớt khi câu ngữ cảnh quá dài', () => {
    const long = 'x'.repeat(500) + ' target ' + 'y'.repeat(500);
    const context = extractContextSentence(long, 'target');
    expect(context!.length).toBeLessThanOrEqual(400);
    expect(context).toContain('target');
  });
});
