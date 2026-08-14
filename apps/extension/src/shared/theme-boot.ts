/** Nối cài đặt giao diện với thẻ `<html>` cho một surface (side panel hoặc Options).
 *
 * Tách khỏi `theme.ts` vì `settings.ts` đã import `theme.ts` để lấy kiểu `Theme` — gộp
 * vào đó là tạo vòng phụ thuộc. Ở đây là tầng trên: biết cả hai và ghép chúng lại.
 */

import { loadSettings } from './settings';
import { applyTheme, resolveTheme, watchSystemTheme, type ResolvedTheme, type Theme } from '@ielts/core';

const SETTINGS_KEY = 'settings';

/**
 * Theo dõi lựa chọn giao diện và báo chế độ đã phân giải mỗi khi nó đổi — kể cả lần đầu.
 *
 * Tách khỏi `bootTheme` vì bubble dịch KHÔNG dùng được cách áp mặc định: nó sống trong
 * Shadow DOM trên trang của người khác, và gắn `data-theme` lên `<html>` ở đó là sửa DOM
 * của trang lạ. Bubble nhận chế độ qua callback rồi tự đặt lên host của chính nó.
 */
export async function watchThemeChoice(
  onResolved: (resolved: ResolvedTheme) => void,
): Promise<void> {
  let choice: Theme = (await loadSettings()).theme;
  onResolved(resolveTheme(choice));

  // Dùng thẳng giá trị sự kiện mang tới, không hỏi lại `matchMedia`: sự kiện đã nói rõ
  // chế độ mới là gì, và hỏi lại là mở khe cho hai nguồn lệch nhau.
  watchSystemTheme((resolved) => {
    if (choice === 'system') onResolved(resolved);
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== 'local' || !changes[SETTINGS_KEY]) return;
    const next = (changes[SETTINGS_KEY].newValue as { theme?: Theme } | undefined)?.theme;
    if (!next || next === choice) return;
    choice = next;
    onResolved(resolveTheme(choice));
  });
}

/**
 * Đọc cài đặt, áp ngay, rồi giữ cho giao diện khớp với hai nguồn có thể đổi giữa chừng:
 *
 * 1. **Người dùng đổi lựa chọn ở trang Options** — side panel có thể đang mở cùng lúc, và
 *    mỗi surface là một tài liệu riêng nên không tự biết. `chrome.storage.onChanged` là
 *    đường duy nhất nối chúng.
 * 2. **Hệ điều hành tự chuyển tối/sáng** — chỉ tính khi người dùng để `'system'`; đã ép
 *    Sáng hoặc Tối thì lựa chọn của họ thắng.
 *
 * Gọi TRƯỚC khi render để không nháy sáng một nhịp rồi mới đổi sang tối.
 */
export function bootTheme(): Promise<void> {
  return watchThemeChoice((resolved) => applyTheme(resolved));
}
