import { FALLBACK_SETTINGS, normaliseSettings } from '@ielts/core';
import type { Settings } from '@ielts/core';

const STORAGE_KEY = 'settings';

/**
 * Mặc định của web.
 *
 * `backendUrl` rỗng là ĐÚNG chứ không phải thiếu sót: web chạy cùng origin với backend nên
 * mọi lời gọi dùng đường dẫn tương đối. Đây cũng là lý do web không có trang Options như
 * extension — không có địa chỉ backend nào để nhập.
 */
export const WEB_DEFAULT_SETTINGS: Settings = { ...FALLBACK_SETTINGS, backendUrl: '' };

/** **Không bao giờ ném.** localStorage tắt (chế độ ẩn danh của vài trình duyệt, hoặc người
 *  dùng chặn) thì app vẫn phải chạy được bằng mặc định. */
export function loadWebSettings(): Settings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Partial<Settings>) : {};
    return normaliseSettings(parsed, WEB_DEFAULT_SETTINGS);
  } catch {
    return { ...WEB_DEFAULT_SETTINGS };
  }
}

export function saveWebSettings(patch: Partial<Settings>): Settings {
  const next = normaliseSettings({ ...loadWebSettings(), ...patch }, WEB_DEFAULT_SETTINGS);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Bỏ lặng một lượt lưu là tệ, nhưng ném ở đây thì cả app chết vì một tuỳ chọn giao
    // diện. Giá trị vẫn đúng trong phiên hiện tại, chỉ không sống qua lần mở sau.
  }
  return next;
}
