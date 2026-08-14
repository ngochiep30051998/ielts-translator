/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Chỉ có cấu hình test — `@ielts/core` KHÔNG build ra bundle riêng.
 *
 * Nó xuất thẳng mã nguồn TypeScript qua `exports` trong package.json, và mỗi app tự
 * transpile nó trong bundle của mình. Đổi lại là không có bước build trung gian phải nhớ
 * chạy, và `tsc --noEmit` của app typecheck luôn cả core — sai kiểu ở đây thì build app đỏ.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
});
