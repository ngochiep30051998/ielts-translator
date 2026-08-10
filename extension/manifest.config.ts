import { defineManifest } from '@crxjs/vite-plugin';

export default defineManifest({
  manifest_version: 3,
  name: 'IELTS Translator',
  version: '0.1.0',
  description: 'Dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+ và học từ mới',
  key: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAycO1Wb9FLs24mQE8eIJzmEOlldeUHj9Eh5YbZ5Zk/N3D5TJNMvqL6P+gYVmM4jct8YF1NkY5DDrtKRXzp7JRa4Feh2l/7Hyt/RQkMJjvBjk+KpPBl1tfEY+KZ+U6yjApc/fSZLPQ5F/DUtIwO6At/HNmfe8hI6mSC3X+vsIx9ijXpeADBMqLDswDCTrz2CkgYKitMUWRjBbK3Utz1+9fgtDwuV8MNMZlbkqsOP2wIQx5OnWxx7pqn/MK7cUFrAaAnORoqPEuAmXsnHIUkklVxVsod9iaKua1aBn/2HgY+aND+KaVqT3WB/Ednl4KkiO7lUtOvpUzJsg78+/F285pZwIDAQAB',
  // `identity` cho chrome.identity.launchWebAuthFlow — luồng đăng nhập Google.
  permissions: ['storage', 'sidePanel', 'tabs', 'alarms', 'identity'],
  /**
   * Ràng buộc #10 nay có BA chỗ phải khớp nhau, không phải hai:
   *   1. danh sách này
   *   2. `backendUrl` mặc định trong shared/settings.ts và ô nhập ở trang Options
   *   3. domain thật đang chạy trên VPS
   *
   * Options là ô nhập tự do, nhưng Chrome chỉ cho gọi origin đã khai ở đây. Trỏ Options
   * sang một domain chưa khai thì request chết IM LẶNG — không lỗi mạng, không lỗi CORS,
   * chỉ là fetch không bao giờ đi.
   */
  host_permissions: [
    'http://127.0.0.1:8080/*',
    // Đổi thành domain thật trước khi deploy. Để nguyên placeholder là extension chết
    // ngay khi trỏ sang VPS.
    'https://ielts.example.com/*',
  ],
  icons: {
    16: 'icons/16.png',
    32: 'icons/32.png',
    48: 'icons/48.png',
    128: 'icons/128.png',
  },
  action: {
    default_title: 'IELTS Translator',
    default_icon: {
      16: 'icons/16.png',
      32: 'icons/32.png',
      48: 'icons/48.png',
      128: 'icons/128.png',
    },
  },
  background: { service_worker: 'src/background/service-worker.ts', type: 'module' },
  side_panel: { default_path: 'src/sidepanel/index.html' },
  options_page: 'src/options/index.html',
  content_scripts: [
    {
      matches: ['<all_urls>'],
      js: ['src/content/index.ts'],
      run_at: 'document_idle',
    },
  ],
  commands: {
    'translate-selection': {
      suggested_key: { default: 'Alt+T' },
      description: 'Dịch đoạn đang bôi đen',
    },
  },
});
