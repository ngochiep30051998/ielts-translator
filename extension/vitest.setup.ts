import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// chrome.storage.local giả lập bằng Map, đủ cho mọi test Phase 1
const store = new Map<string, unknown>();

/**
 * Gán THẲNG vào globalThis chứ không dùng vi.stubGlobal.
 *
 * `vi.stubGlobal` ghi lại giá trị gốc (undefined) và `vi.unstubAllGlobals()` trong
 * afterEach của một test file sẽ XOÁ luôn `chrome` cho những test sau trong cùng file —
 * lỗi hiện ra là "chrome is not defined" ở một chỗ chẳng liên quan gì.
 */
Object.assign(globalThis, { chrome: {
  storage: {
    local: {
      get: async (keys: string[]) => {
        const result: Record<string, unknown> = {};
        for (const key of keys) {
          if (store.has(key)) result[key] = store.get(key);
        }
        return result;
      },
      set: async (items: Record<string, unknown>) => {
        for (const [key, value] of Object.entries(items)) store.set(key, value);
      },
      remove: async (keys: string[] | string) => {
        for (const key of Array.isArray(keys) ? keys : [keys]) store.delete(key);
      },
      clear: async () => store.clear(),
    },
  },
  runtime: {
    sendMessage: vi.fn(),
    lastError: undefined,
    onMessage: { addListener: vi.fn() },
    onStartup: { addListener: vi.fn() },
    onInstalled: { addListener: vi.fn() },
  },
  // setPanelBehavior phải trả Promise: service worker gọi .catch() ngay lúc import.
  sidePanel: { open: vi.fn(), setPanelBehavior: vi.fn(async () => {}) },
  tabs: { query: vi.fn(async () => []), sendMessage: vi.fn() },
  commands: { onCommand: { addListener: vi.fn() } },
  alarms: {
    create: vi.fn(),
    get: vi.fn(async () => undefined),
    onAlarm: { addListener: vi.fn() },
  },
  action: {
    setBadgeText: vi.fn(),
    setBadgeBackgroundColor: vi.fn(),
  },
  // chrome.identity chỉ tồn tại ở service worker; test luồng đăng nhập cần cả hai hàm này.
  identity: {
    getRedirectURL: vi.fn(() => 'https://testextensionid.chromiumapp.org/'),
    launchWebAuthFlow: vi.fn(),
  },
} });
