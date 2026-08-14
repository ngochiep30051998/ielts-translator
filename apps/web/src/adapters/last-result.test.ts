import { describe, it, expect, beforeEach } from 'vitest';
import type { TranslateResult } from '@ielts/core';

import { sessionLastResult } from './last-result';

const KET_QUA = {
  direction: 'EN_VI',
  mode: 'WORD',
  cached: false,
  sourceText: 'mitigate',
  payload: { term: 'mitigate', meaning_vi: 'giảm nhẹ' },
} as unknown as TranslateResult;

describe('lastResult trên sessionStorage', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('chưa có gì thì trả null', async () => {
    expect(await sessionLastResult.get()).toBeNull();
  });

  it('sống qua một lần tải lại trang', async () => {
    // Đây là toàn bộ lý do dùng storage thay vì biến trong bộ nhớ: extension giữ kết quả
    // trong service worker (tách khỏi panel), web thì F5 là mất sạch — mà F5 là thao tác
    // người ta làm liên tục trên điện thoại.
    await sessionLastResult.set(KET_QUA);

    expect(await sessionLastResult.get()).toMatchObject({ sourceText: 'mitigate' });
  });

  it('đặt null là xoá hẳn', async () => {
    await sessionLastResult.set(KET_QUA);
    await sessionLastResult.set(null);

    expect(await sessionLastResult.get()).toBeNull();
    expect(window.sessionStorage.getItem('lastResult')).toBeNull();
  });

  it('dữ liệu hỏng trong storage trả null chứ không ném', async () => {
    window.sessionStorage.setItem('lastResult', 'không phải json');

    expect(await sessionLastResult.get()).toBeNull();
  });
});
