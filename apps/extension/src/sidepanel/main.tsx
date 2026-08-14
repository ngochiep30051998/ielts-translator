import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '@ielts/core/ui';
import { setSettingsProvider, setSurfaceCapabilities } from '@ielts/core';
import { bootTheme } from '../shared/theme-boot';
import { installChromeTransport } from '../shared/chrome-transport';
import { loadSettings } from '../shared/settings';
import '@ielts/core/styles.css';

// Đấu dây cho `@ielts/core` TRƯỚC khi render: UI dùng chung gọi `sendToBackground` và
// `loadSettings` ngay trong effect đầu tiên, nên đặt muộn là một nhịp chạy bằng mặc định.
installChromeTransport();
setSettingsProvider(loadSettings);
// Extension cắm được content script vào trang của người khác, nên chỉ dẫn "bôi đen
// text trên trang" là đúng ở đây — và chỉ ở đây.
setSurfaceCapabilities({ selectionCapture: true });

// Áp giao diện TRƯỚC khi render: cài đặt nằm trong chrome.storage (bất đồng bộ), nên render
// trước rồi mới đổi màu sẽ loé một nhịp sáng trước khi chuyển tối.
void bootTheme().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode><App /></StrictMode>,
  );
});
