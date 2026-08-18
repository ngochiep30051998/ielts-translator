import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '@ielts/core/ui';
import '@ielts/core/styles.css';
import './styles.css';

import { readAuthError } from './auth-error';
import { readSharedText } from './share-target';
import { bootTheme } from './theme-boot';
import { registerServiceWorker } from './register-sw';
import { installWebRuntime } from './runtime';
import { UpdateBanner } from './UpdateBanner';

// Thứ tự có ý nghĩa:
//
// 1. `installWebRuntime` phải chạy TRƯỚC render — UI dùng chung gọi `sendToBackground` và
//    `loadSettings` ngay trong effect đầu tiên, nên đặt muộn là một nhịp chạy bằng mặc định.
// 2. `bootTheme` cũng trước render, để không loé sáng một nhịp rồi mới chuyển tối.
// 3. `readAuthError` xoá tham số khỏi URL, nên phải chạy đúng một lần và trước khi có gì
//    khác kịp đọc `location.search`.
installWebRuntime();
bootTheme();

// Cả hai hàm này ĐỌC RỒI DỌN `location`, nên phải chạy trước mọi thứ khác kịp đọc nó, và
// đúng một lần. `readSharedText` trước vì nó xét `pathname`, còn `readAuthError` xét query —
// một lượt chia sẻ không bao giờ mang `authError`, nên thứ tự không tranh nhau.
const sharedText = readSharedText(window.location, window.history);
const authError = readAuthError(window.location, window.history);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App initialAuthError={authError} initialDraft={sharedText ?? ''} />
    {/* Anh em với `App`, không nằm trong nó: `App` là khung cao đúng 100dvh của UI dùng
        chung, còn banner là một lớp nổi chỉ web mới có. Nhét vào trong là bắt `packages/core`
        biết tới một khái niệm chỉ tồn tại ở một surface. */}
    <UpdateBanner />
  </StrictMode>,
);

// SAU khi render: service worker không cần thiết để vẽ màn hình đầu tiên, và đăng ký nó
// sớm là tranh băng thông với chính những asset đang cần.
registerServiceWorker();
