/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Web app chạy CÙNG ORIGIN với backend, nên bundle không có khái niệm "địa chỉ backend":
 * mọi lời gọi dùng đường dẫn tương đối `/api/...`. Đó là lý do ở đây không có
 * `VITE_BACKEND_URL` như bên extension.
 *
 * Lúc `npm run dev` thì Vite phục vụ ở cổng khác backend, nên `/api` được proxy sang
 * uvicorn — chính nhờ vậy cookie phiên vẫn là cookie same-origin và luồng đăng nhập chạy
 * đúng như production. Trỏ thẳng bundle sang `http://127.0.0.1:8080` sẽ biến nó thành
 * cross-site và cookie `SameSite=Lax` sẽ không bao giờ được gửi.
 */
/** Không phải 5173 (mặc định của Vite) để không tranh cổng với project Vite khác đang mở. */
const CONG_MAC_DINH = 5174;
const BACKEND_MAC_DINH = 'http://127.0.0.1:8080';

export default defineConfig(({ mode }) => {
  // `loadEnv` chạy ở Node lúc nạp cấu hình, nơi KHÔNG có `import.meta.env` — cùng lý do đã
  // ghi trong `manifest.config.ts` của extension. Hai biến dưới đây chỉ phục vụ dev server,
  // chúng KHÔNG đi vào bundle.
  const env = loadEnv(mode, '.', 'VITE_');

  // `Number('')` ra 0 và `Number('abc')` ra NaN — cả hai đều falsy, nên `||` bắt trọn cả ba
  // ca hỏng (thiếu biến, để trống, gõ sai) về đúng một mặc định.
  const port = Number(env.VITE_DEV_PORT) || CONG_MAC_DINH;
  const backend = env.VITE_DEV_BACKEND?.trim() || BACKEND_MAC_DINH;

  return {
    plugins: [react()],
    server: {
      port,
      // Báo lỗi thay vì lặng lẽ nhảy sang cổng khác: người dùng đã khai một cổng cụ thể thì
      // chạy ở cổng khác là làm hỏng redirect URI đã đăng ký với Google.
      strictPort: true,
      proxy: {
        '/api': {
          target: backend,
          changeOrigin: false,
        },
      },
    },
    build: {
      // Tên có hash cho asset (cache vĩnh viễn được), trừ service worker và manifest —
      // hai thứ đó phải giữ đường dẫn cố định, xử lý riêng ở task PWA.
      outDir: 'dist',
      emptyOutDir: true,
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./vitest.setup.ts'],
      /**
       * Ghim biến môi trường cho test, KHÔNG để `.env` của máy dev lọt vào.
       *
       * Vitest chạy qua Vite nên nó cũng nạp `apps/web/.env`. Một người đặt
       * `VITE_API_BASE_URL` trong đó sẽ làm `runtime.test.ts` đỏ trên máy họ mà xanh trên
       * CI — loại lỗi tốn nhiều thời gian nhất để tin.
       *
       * Rỗng = đúng cấu hình mà sản phẩm chạy (cùng origin). Nhánh khác-origin có test
       * riêng ở `adapters/api-base.test.ts`, nơi giá trị được truyền thẳng vào hàm thay vì
       * đi qua môi trường.
       */
      env: {
        VITE_API_BASE_URL: '',
      },
    },
  };
});
