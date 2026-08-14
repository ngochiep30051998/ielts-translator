import { applyTheme, resolveTheme, watchSystemTheme } from '@ielts/core';

import { loadWebSettings } from './adapters/settings-store';

/**
 * Áp giao diện và giữ nó khớp với hệ điều hành.
 *
 * Bản web của `theme-boot.ts` bên extension. Khác đúng một chỗ: extension phải nghe
 * `chrome.storage.onChanged` vì side panel và trang Options là hai tài liệu riêng biệt,
 * cùng lúc mở, và không tự biết bên kia vừa đổi gì. Web chỉ có một tài liệu — đổi cài đặt
 * là đổi ngay trong chính trang đó, không có ai để đồng bộ.
 *
 * Gọi TRƯỚC khi render để không loé một nhịp sáng rồi mới chuyển tối.
 */
export function bootTheme(): void {
  const choice = loadWebSettings().theme;
  applyTheme(resolveTheme(choice));

  watchSystemTheme((resolved) => {
    // Chỉ đi theo hệ điều hành khi người dùng để `'system'`. Đã ép Sáng hoặc Tối thì lựa
    // chọn của họ thắng.
    if (loadWebSettings().theme === 'system') applyTheme(resolved);
  });
}
