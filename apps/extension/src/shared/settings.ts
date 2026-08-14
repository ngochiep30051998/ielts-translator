import { normaliseBackendUrl } from './backend-url';
import { normaliseSettings } from '@ielts/core';
import type { Settings, TriggerMode } from '@ielts/core';

/**
 * `Settings` và `TriggerMode` định nghĩa ở `@ielts/core` — UI dùng chung đọc chúng, nên hai
 * bên phải là CÙNG MỘT kiểu. Định nghĩa lại ở đây sẽ tạo hai hình dạng trông giống hệt nhau
 * mà TypeScript vẫn coi là tương thích, rồi lệch dần mà không có gì đỏ.
 *
 * Xuất lại để mọi chỗ trong extension vẫn `import { Settings } from '../shared/settings'`
 * như trước.
 */
export type { Settings, TriggerMode };

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

/**
 * Luật làm sạch nằm ở `@ielts/core` — web đọc cài đặt từ `localStorage` nhưng phải chấp
 * nhận đúng cùng một tập giá trị. Hai bản `normalise` song song sẽ lệch dần mà không có gì
 * đỏ, và lệch ở đây nghĩa là hai thiết bị của cùng một người học theo hai hạn mức khác nhau.
 */
function normalise(raw: Partial<Settings>): Settings {
  return normaliseSettings(raw, DEFAULT_SETTINGS);
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
