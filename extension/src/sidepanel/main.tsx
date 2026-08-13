import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { bootTheme } from '../shared/theme-boot';
import './styles.css';

// Áp giao diện TRƯỚC khi render: cài đặt nằm trong chrome.storage (bất đồng bộ), nên render
// trước rồi mới đổi màu sẽ loé một nhịp sáng trước khi chuyển tối.
void bootTheme().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode><App /></StrictMode>,
  );
});
