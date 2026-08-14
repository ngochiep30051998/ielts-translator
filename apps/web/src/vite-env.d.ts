/// <reference types="vite/client" />

/**
 * Khai kiểu cho biến môi trường của bundle web.
 *
 * `vite/client` cho `import.meta.env` một index signature trả `any`, nên gõ sai tên biến sẽ
 * lặng lẽ ra `undefined` thay vì đỏ lúc build. Khai tường minh ở đây là cách duy nhất để
 * `tsc --noEmit` bắt được lỗi chính tả.
 *
 * Chỉ những biến mà MÃ NGUỒN đọc mới nằm ở đây. `VITE_DEV_PORT` và `VITE_DEV_BACKEND` chỉ
 * `vite.config.ts` dùng (qua `loadEnv`, đường Node), không đi vào bundle.
 */
interface ImportMetaEnv {
  /**
   * Địa chỉ gốc của API. Rỗng (mặc định) = cùng origin, đường dẫn tương đối.
   *
   * Đặt sang origin khác sẽ làm cookie phiên không được gửi — xem `adapters/api-base.ts`.
   */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
