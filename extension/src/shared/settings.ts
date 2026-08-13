import { normaliseBackendUrl } from './backend-url';
import type { Theme } from './theme';

export type TriggerMode = 'auto' | 'hotkey';

export interface Settings {
  backendUrl: string;
  triggerMode: TriggerMode;
  voiceName: string | null;
  /** Số thẻ MỚI tối đa được đưa vào hàng đợi ôn mỗi ngày. */
  newWordsPerDay: number;
  /** Chế độ màu. `'system'` để giao diện đi theo hệ điều hành. */
  theme: Theme;
}

export const DEFAULT_SETTINGS: Settings = {
  // Nhúng lúc build từ `VITE_BACKEND_URL`. Cùng biến đó dựng ra `host_permissions` trong
  // manifest, nên hai thứ không thể lệch nhau — xem `shared/backend-url.ts`.
  backendUrl: normaliseBackendUrl(import.meta.env.VITE_BACKEND_URL),
  triggerMode: 'auto',
  voiceName: null,
  newWordsPerDay: 30,
  theme: 'system',
};

const STORAGE_KEY = 'settings';
const THEMES: readonly Theme[] = ['system', 'light', 'dark'];
const MAX_NEW_WORDS_PER_DAY = 200;

/** Giá trị lạ (NaN, chuỗi, undefined) quay về mặc định thay vì lọt xuống backend. */
function normaliseNewWordsPerDay(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return DEFAULT_SETTINGS.newWordsPerDay;
  }
  return Math.min(MAX_NEW_WORDS_PER_DAY, Math.max(0, Math.round(value)));
}

function normalise(raw: Partial<Settings>): Settings {
  const merged = { ...DEFAULT_SETTINGS, ...raw };
  return {
    backendUrl: merged.backendUrl.replace(/\/+$/, ''),
    triggerMode: merged.triggerMode === 'hotkey' ? 'hotkey' : 'auto',
    voiceName: merged.voiceName ?? null,
    newWordsPerDay: normaliseNewWordsPerDay(merged.newWordsPerDay),
    // Cài đặt lưu từ bản chưa có tính năng này không mang field `theme`, nên phải chịu
    // được giá trị thiếu lẫn giá trị lạ — cả hai đều lui về `'system'`.
    theme: THEMES.includes(merged.theme) ? merged.theme : 'system',
  };
}

/**
 * Đọc cấu hình. **Không bao giờ ném** — hỏng thì trả mặc định.
 *
 * Reload extension biến mọi content script trên các tab đang mở thành mồ côi, và
 * `chrome.storage.local` của chúng ném "Extension context invalidated". Content script
 * gọi hàm này ở MỖI lần `mouseup`, trong một callback async không ai bắt, nên ném ở đây
 * đổ unhandled rejection ra console của mọi trang người dùng đang mở.
 *
 * Nuốt được vì có đường lui đúng nghĩa: chạy tiếp bằng mặc định. Bản thân thao tác dịch
 * vẫn sẽ báo lỗi tử tế qua `sendToBackground`, vốn đã nuốt đúng ca mồ côi này cho
 * `chrome.runtime.sendMessage`. `saveSettings` thì KHÔNG nuốt — bỏ lặng một lượt lưu tệ
 * hơn hẳn là báo lỗi.
 */
export async function loadSettings(): Promise<Settings> {
  try {
    const stored = await chrome.storage.local.get([STORAGE_KEY]);
    return normalise((stored[STORAGE_KEY] ?? {}) as Partial<Settings>);
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = normalise({ ...(await loadSettings()), ...patch });
  await chrome.storage.local.set({ [STORAGE_KEY]: next });
  return next;
}
