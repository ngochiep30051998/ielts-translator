import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import { setTransport } from '@ielts/core';
import { chromeTransport } from './src/shared/chrome-transport';

// chrome.storage.local giả lập bằng Map, đủ cho mọi test Phase 1
const store = new Map<string, unknown>();

type StorageListener = (
  changes: Record<string, { newValue?: unknown; oldValue?: unknown }>,
  areaName: string,
) => void;

/** Listener của `chrome.storage.onChanged`. Test bắn sự kiện qua `emitStorageChange`. */
const storageListeners = new Set<StorageListener>();

/** Giả lập một lượt storage đổi — dùng để test đồng bộ cài đặt giữa các surface. */
export function emitStorageChange(
  changes: Record<string, { newValue?: unknown; oldValue?: unknown }>,
  areaName = 'local',
): void {
  storageListeners.forEach((cb) => cb(changes, areaName));
}

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
    // Đồng bộ theme giữa Options và side panel đang mở đi qua sự kiện này. Test tự bắn
    // bằng cách gọi các listener đã đăng ký.
    onChanged: {
      addListener: (cb: StorageListener) => storageListeners.add(cb),
      removeListener: (cb: StorageListener) => storageListeners.delete(cb),
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

/**
 * Nối `sendToBackground` của core vào `chrome.runtime` cho MỌI test của extension.
 *
 * Sản phẩm thật cài transport ở entry point từng surface (`main.tsx`, `content/index.ts`),
 * nhưng test render component thẳng nên không đi qua đó. Không có dòng này thì mọi test UI
 * nhận "Transport chưa được cài đặt" thay vì gọi tới mock `chrome.runtime.sendMessage` ở
 * trên — và lỗi hiện ra ở chỗ chẳng liên quan gì tới thứ đang test.
 */
setTransport(chromeTransport);
