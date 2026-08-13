import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Options } from './Options';
import { bootTheme } from '../shared/theme-boot';
import '../sidepanel/styles.css';

// `finally` chứ không `then`: cài đặt hỏng thì vẫn phải mở được trang Options — đó chính
// là nơi người dùng vào để sửa.
void bootTheme().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode><Options /></StrictMode>,
  );
});
