import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { emitStorageChange } from '../../vitest.setup';
import { bootTheme } from './theme-boot';
import { saveSettings } from './settings';

type Listener = (event: { matches: boolean }) => void;

function stubSystem(dark: boolean): Set<Listener> {
  const listeners = new Set<Listener>();
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: dark,
    media: query,
    addEventListener: (_type: string, cb: Listener) => listeners.add(cb),
    removeEventListener: (_type: string, cb: Listener) => listeners.delete(cb),
  }));
  return listeners;
}

const themeAttr = () => document.documentElement.dataset.theme;

describe('bootTheme', () => {
  beforeEach(async () => {
    await chrome.storage.local.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.removeAttribute('data-theme');
  });

  it('áp chế độ đã lưu ngay khi khởi động', async () => {
    stubSystem(false);
    await saveSettings({ theme: 'dark' });

    await bootTheme();

    expect(themeAttr()).toBe('dark');
  });

  it('chưa từng chọn thì đi theo hệ điều hành', async () => {
    stubSystem(true);

    await bootTheme();

    expect(themeAttr()).toBe('dark');
  });

  it('đổi cài đặt ở trang Options thì surface đang mở đổi theo ngay', async () => {
    stubSystem(false);
    await saveSettings({ theme: 'light' });
    await bootTheme();

    emitStorageChange({ settings: { newValue: { theme: 'dark' } } });

    expect(themeAttr()).toBe('dark');
  });

  it('đang theo hệ điều hành mà hệ điều hành chuyển tối thì đổi theo', async () => {
    const listeners = stubSystem(false);
    await saveSettings({ theme: 'system' });
    await bootTheme();
    expect(themeAttr()).toBe('light');

    listeners.forEach((cb) => cb({ matches: true }));

    expect(themeAttr()).toBe('dark');
  });

  it('đã ép sáng thì hệ điều hành chuyển tối cũng mặc kệ', async () => {
    const listeners = stubSystem(false);
    await saveSettings({ theme: 'light' });
    await bootTheme();

    listeners.forEach((cb) => cb({ matches: true }));

    expect(themeAttr()).toBe('light');
  });

  it('bỏ qua thay đổi storage không dính tới cài đặt', async () => {
    stubSystem(false);
    await saveSettings({ theme: 'dark' });
    await bootTheme();

    emitStorageChange({ auth: { newValue: { token: 'x' } } });

    expect(themeAttr()).toBe('dark');
  });
});
