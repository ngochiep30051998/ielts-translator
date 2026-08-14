import type { Theme } from './theme';

export type TriggerMode = 'auto' | 'hotkey';

export interface Settings {
  /**
   * Chỉ có ý nghĩa với extension — nó gọi backend cross-origin nên phải biết địa chỉ.
   * Web chạy cùng origin với backend nên dùng đường dẫn tương đối và để trống field này.
   */
  backendUrl: string;
  triggerMode: TriggerMode;
  voiceName: string | null;
  /** Số thẻ MỚI tối đa được đưa vào hàng đợi ôn mỗi ngày. */
  newWordsPerDay: number;
  /** Chế độ màu. `'system'` để giao diện đi theo hệ điều hành. */
  theme: Theme;
}

/**
 * Giá trị dùng khi surface chưa kịp đăng ký provider — hoặc không có nơi lưu nào cả.
 *
 * KHÔNG đọc `import.meta.env` ở đây: `VITE_BACKEND_URL` là khái niệm riêng của bundle
 * extension, và core thì không được biết mình đang nằm trong bundle nào.
 */
export const FALLBACK_SETTINGS: Settings = {
  backendUrl: '',
  triggerMode: 'auto',
  voiceName: null,
  newWordsPerDay: 30,
  theme: 'system',
};

const THEMES: readonly Theme[] = ['system', 'light', 'dark'];
const MAX_NEW_WORDS_PER_DAY = 200;

/** Giá trị lạ (NaN, chuỗi, undefined) quay về mặc định thay vì lọt xuống backend. */
function normaliseNewWordsPerDay(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(MAX_NEW_WORDS_PER_DAY, Math.max(0, Math.round(value)));
}

/**
 * Làm sạch cài đặt đọc từ nơi lưu bất kỳ.
 *
 * Ở core chứ không ở từng app vì cả hai đọc từ hai nơi khác nhau nhưng phải chấp nhận đúng
 * cùng một tập giá trị — hai bản `normalise` song song sẽ lệch dần mà không có gì đỏ, và
 * lệch ở đây nghĩa là hai thiết bị của cùng một người học theo hai hạn mức khác nhau.
 *
 * `defaults` là tham số vì `backendUrl` mặc định khác nhau thật: extension nhúng
 * `VITE_BACKEND_URL` lúc build, web thì chạy cùng origin nên để rỗng.
 */
export function normaliseSettings(
  raw: Partial<Settings>,
  defaults: Settings = FALLBACK_SETTINGS,
): Settings {
  const merged = { ...defaults, ...raw };
  return {
    backendUrl: (merged.backendUrl ?? '').replace(/\/+$/, ''),
    triggerMode: merged.triggerMode === 'hotkey' ? 'hotkey' : 'auto',
    voiceName: merged.voiceName ?? null,
    newWordsPerDay: normaliseNewWordsPerDay(merged.newWordsPerDay, defaults.newWordsPerDay),
    // Cài đặt lưu từ bản chưa có tính năng này không mang field `theme`, nên phải chịu
    // được giá trị thiếu lẫn giá trị lạ — cả hai đều lui về `'system'`.
    theme: THEMES.includes(merged.theme) ? merged.theme : 'system',
  };
}

let provider: () => Promise<Settings> = async () => ({ ...FALLBACK_SETTINGS });

/**
 * Đăng ký nơi đọc cài đặt. Extension trỏ vào `chrome.storage.local`, web vào
 * `localStorage`.
 */
export function setSettingsProvider(next: () => Promise<Settings>): void {
  provider = next;
}

/** Chỉ dùng trong test: trả provider về mặc định để test này không rò sang test kia. */
export function resetSettingsProvider(): void {
  provider = async () => ({ ...FALLBACK_SETTINGS });
}

/** **Không bao giờ ném** — provider hỏng thì lui về mặc định. */
export async function loadSettings(): Promise<Settings> {
  try {
    return await provider();
  } catch {
    return { ...FALLBACK_SETTINGS };
  }
}
