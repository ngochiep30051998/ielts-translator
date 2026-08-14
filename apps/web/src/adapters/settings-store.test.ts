import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

import { WEB_DEFAULT_SETTINGS, loadWebSettings, saveWebSettings } from './settings-store';

describe('settings trên localStorage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('chưa lưu gì thì trả mặc định của web', () => {
    expect(loadWebSettings()).toEqual(WEB_DEFAULT_SETTINGS);
  });

  it('backendUrl mặc định RỖNG — web gọi đường dẫn tương đối', () => {
    // Không phải thiếu sót: web cùng origin với backend. Điền một địa chỉ vào đây là biến
    // mọi request thành cross-site và cookie SameSite=Lax sẽ không bao giờ được gửi.
    expect(WEB_DEFAULT_SETTINGS.backendUrl).toBe('');
  });

  it('lưu rồi đọc lại đúng giá trị', () => {
    saveWebSettings({ newWordsPerDay: 15, theme: 'dark' });

    expect(loadWebSettings()).toMatchObject({ newWordsPerDay: 15, theme: 'dark' });
  });

  it('áp cùng luật làm sạch với extension: âm về 0, quá lớn cắt ở 200', () => {
    expect(saveWebSettings({ newWordsPerDay: -5 }).newWordsPerDay).toBe(0);
    expect(saveWebSettings({ newWordsPerDay: 9999 }).newWordsPerDay).toBe(200);
  });

  it('theme lạ lui về system', () => {
    expect(saveWebSettings({ theme: 'neon' as never }).theme).toBe('system');
  });

  it('JSON hỏng trong storage KHÔNG làm app chết', () => {
    window.localStorage.setItem('settings', '{ đây không phải json');

    expect(loadWebSettings()).toEqual(WEB_DEFAULT_SETTINGS);
  });

  it('localStorage bị chặn thì vẫn chạy bằng mặc định', () => {
    // Có thật ở chế độ ẩn danh của vài trình duyệt và khi người dùng chặn lưu trữ.
    // Spy thẳng lên chính object, không lên `Storage.prototype`: dưới test, localStorage
    // có thể là shim của `vitest.setup.ts` chứ không phải instance của `Storage`.
    vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });

    expect(loadWebSettings()).toEqual(WEB_DEFAULT_SETTINGS);
  });

  it('lưu thất bại thì không ném — mất tiện lợi, không mất chức năng', () => {
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => saveWebSettings({ theme: 'dark' })).not.toThrow();
    expect(saveWebSettings({ theme: 'dark' }).theme).toBe('dark');
  });
});
