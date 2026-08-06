import { describe, it, expect, beforeEach } from 'vitest';
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from './settings';

describe('settings', () => {
  beforeEach(async () => {
    await chrome.storage.local.clear();
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
});
