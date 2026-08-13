import { describe, it, expect, vi, afterEach } from 'vitest';
import { applyTheme, resolveTheme, watchSystemTheme } from './theme';

type Listener = (event: { matches: boolean }) => void;

/** Giả lập chế độ màu của hệ điều hành. Trả về tập listener để test tự bắn sự kiện đổi. */
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

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.style.removeProperty('color-scheme');
});

describe('resolveTheme', () => {
  it('trả thẳng lựa chọn khi người dùng đã ép sáng hoặc tối', () => {
    stubSystem(true);
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('theo hệ điều hành khi để chế độ tự động', () => {
    stubSystem(true);
    expect(resolveTheme('system')).toBe('dark');
    stubSystem(false);
    expect(resolveTheme('system')).toBe('light');
  });

  it('coi như sáng khi trình duyệt không có matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined);
    expect(resolveTheme('system')).toBe('light');
  });
});

describe('applyTheme', () => {
  it('gắn data-theme đã phân giải sẵn lên thẻ gốc', () => {
    stubSystem(true);
    applyTheme('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('ghi đè được lựa chọn của hệ điều hành', () => {
    stubSystem(true);
    applyTheme('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('đặt color-scheme để control gốc của trình duyệt đi theo', () => {
    stubSystem(false);
    applyTheme('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('trả về chế độ đã phân giải để nơi gọi khỏi tính lại', () => {
    stubSystem(true);
    expect(applyTheme('system')).toBe('dark');
  });
});

describe('watchSystemTheme', () => {
  it('báo lại khi hệ điều hành đổi chế độ màu', () => {
    const listeners = stubSystem(false);
    const seen: string[] = [];
    watchSystemTheme((resolved) => seen.push(resolved));

    listeners.forEach((cb) => cb({ matches: true }));

    expect(seen).toEqual(['dark']);
  });

  it('gỡ listener khi huỷ đăng ký', () => {
    const listeners = stubSystem(false);
    const stop = watchSystemTheme(() => {});
    expect(listeners.size).toBe(1);

    stop();

    expect(listeners.size).toBe(0);
  });

  it('không nổ khi trình duyệt không có matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined);
    expect(() => watchSystemTheme(() => {})()).not.toThrow();
  });
});
