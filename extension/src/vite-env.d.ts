/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Client id của OAuth client "Web application". Nhúng lúc build qua .env của Vite.
   * KHÔNG bao giờ đặt client_secret ở đây — mọi thứ trong ImportMetaEnv đều nằm trong
   * bundle mà ai cài extension cũng đọc được.
   */
  readonly VITE_GOOGLE_CLIENT_ID?: string;

  /**
   * Địa chỉ backend, ví dụ `https://ielts-translator.vercel.app`. Chưa đặt thì dùng
   * `http://127.0.0.1:8080`.
   *
   * Cùng biến này dựng ra `host_permissions` trong `manifest.config.ts`, nên đổi một chỗ
   * là đổi cả hai. Công khai được — nó chỉ là địa chỉ, và ai cài extension cũng thấy được
   * qua tab Network.
   */
  readonly VITE_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
