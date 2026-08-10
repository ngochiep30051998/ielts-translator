/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Client id của OAuth client "Web application". Nhúng lúc build qua .env của Vite.
   * KHÔNG bao giờ đặt client_secret ở đây — mọi thứ trong ImportMetaEnv đều nằm trong
   * bundle mà ai cài extension cũng đọc được.
   */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
