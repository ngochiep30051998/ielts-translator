import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from './settings';

describe('settings', () => {
  beforeEach(async () => {
    await chrome.storage.local.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('context extension chết thì trả mặc định, không ném', async () => {
    // Reload extension làm mọi content script trên các tab đang mở thành mồ côi:
    // chrome.storage.local ném "Extension context invalidated". Content script gọi
    // loadSettings() ở MỖI lần mouseup, và callback đó là async không ai bắt — nên
    // ném ở đây thành unhandled rejection đổ ra console của mọi trang người dùng mở.
    // shared/messages.ts đã nuốt đúng ca này cho sendMessage; đây là chỗ còn sót.
    vi.spyOn(chrome.storage.local, 'get').mockRejectedValue(
      new Error('Extension context invalidated.'),
    );

    await expect(loadSettings()).resolves.toEqual(DEFAULT_SETTINGS);
  });

  it('saveSettings KHÔNG nuốt lỗi — nuốt một lượt lưu hỏng tệ hơn là báo lỗi', async () => {
    vi.spyOn(chrome.storage.local, 'set').mockRejectedValue(
      new Error('Extension context invalidated.'),
    );

    await expect(saveSettings({ triggerMode: 'hotkey' })).rejects.toThrow();
  });

  it('trả về mặc định khi chưa lưu gì', async () => {
    expect(await loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it('lưu rồi đọc lại đúng giá trị', async () => {
    await saveSettings({ triggerMode: 'hotkey' });

    expect((await loadSettings()).triggerMode).toBe('hotkey');
  });

  it('gộp giá trị đã lưu lên trên mặc định, không mất field khác', async () => {
    await saveSettings({ backendUrl: 'http://localhost:9999' });

    const settings = await loadSettings();
    expect(settings.backendUrl).toBe('http://localhost:9999');
    expect(settings.triggerMode).toBe(DEFAULT_SETTINGS.triggerMode);
  });

  it('bỏ qua field lạ còn sót trong storage', async () => {
    await chrome.storage.local.set({ settings: { backendUrl: 'http://x', obsoleteField: 1 } });

    expect(await loadSettings()).not.toHaveProperty('obsoleteField');
  });

  it('cắt dấu / thừa ở cuối backendUrl', async () => {
    await saveSettings({ backendUrl: 'http://127.0.0.1:8080/' });

    expect((await loadSettings()).backendUrl).toBe('http://127.0.0.1:8080');
  });

  it('newWordsPerDay mặc định là 30', async () => {
    const settings = await loadSettings();
    expect(settings.newWordsPerDay).toBe(30);
  });

  it('newWordsPerDay âm bị kéo về 0, quá lớn bị cắt ở 200', async () => {
    expect((await saveSettings({ newWordsPerDay: -5 })).newWordsPerDay).toBe(0);
    expect((await saveSettings({ newWordsPerDay: 9999 })).newWordsPerDay).toBe(200);
  });

  it('newWordsPerDay không phải số thì quay về mặc định', async () => {
    const settings = await saveSettings({ newWordsPerDay: Number.NaN });
    expect(settings.newWordsPerDay).toBe(30);
  });

  it('mặc định để giao diện đi theo hệ điều hành', () => {
    expect(DEFAULT_SETTINGS.theme).toBe('system');
  });

  it('lưu được cả ba lựa chọn giao diện', async () => {
    expect((await saveSettings({ theme: 'dark' })).theme).toBe('dark');
    expect((await saveSettings({ theme: 'light' })).theme).toBe('light');
    expect((await saveSettings({ theme: 'system' })).theme).toBe('system');
  });

  it('giá trị giao diện lạ quay về theo hệ điều hành', async () => {
    // Cài đặt cũ lưu trước khi có tính năng này, hoặc storage bị sửa tay.
    const settings = await saveSettings({ theme: 'xanh lá' as never });
    expect(settings.theme).toBe('system');
  });
});
