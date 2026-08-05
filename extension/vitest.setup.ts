import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// chrome.storage.local giả lập bằng Map, đủ cho mọi test Phase 1
const store = new Map<string, unknown>();

vi.stubGlobal('chrome', {
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
      clear: async () => store.clear(),
    },
  },
  runtime: { sendMessage: vi.fn(), lastError: undefined },
  sidePanel: { open: vi.fn(), setPanelBehavior: vi.fn() },
});
