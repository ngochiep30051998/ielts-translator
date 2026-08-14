import { defineManifest } from '@crxjs/vite-plugin';
import { loadEnv } from 'vite';

import { hostPermissionsFor, normaliseBackendUrl } from './src/shared/backend-url';

/**
 * Manifest là HÀM chứ không phải object vì `host_permissions` phải đọc được `.env`.
 *
 * File này chạy ở Node lúc Vite nạp cấu hình, nơi KHÔNG có `import.meta.env` — biến đó chỉ
 * tồn tại sau khi Vite biến đổi mã nguồn cho trình duyệt. Dùng nó ở đây sẽ ra `undefined`
 * và manifest lặng lẽ chỉ khai mỗi localhost, còn bundle thì trỏ đúng domain production:
 * extension cài được, nhìn bình thường, và mọi request chết im lặng.
 */
export default defineManifest(({ mode }) => {
  // `'.'` chứ không `process.cwd()`: tránh phải kéo thêm `@types/node` vào chỉ vì một lời
  // gọi (ràng buộc #12). `loadEnv` tự `path.resolve` nên hai cách cho ra cùng thư mục.
  const env = loadEnv(mode, '.', 'VITE_');
  const backendUrl = normaliseBackendUrl(env.VITE_BACKEND_URL);

  return {
    manifest_version: 3,
    name: 'IELTS Translator',
    version: '0.1.0',
    description: 'Dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+ và học từ mới',
    key: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAycO1Wb9FLs24mQE8eIJzmEOlldeUHj9Eh5YbZ5Zk/N3D5TJNMvqL6P+gYVmM4jct8YF1NkY5DDrtKRXzp7JRa4Feh2l/7Hyt/RQkMJjvBjk+KpPBl1tfEY+KZ+U6yjApc/fSZLPQ5F/DUtIwO6At/HNmfe8hI6mSC3X+vsIx9ijXpeADBMqLDswDCTrz2CkgYKitMUWRjBbK3Utz1+9fgtDwuV8MNMZlbkqsOP2wIQx5OnWxx7pqn/MK7cUFrAaAnORoqPEuAmXsnHIUkklVxVsod9iaKua1aBn/2HgY+aND+KaVqT3WB/Ednl4KkiO7lUtOvpUzJsg78+/F285pZwIDAQAB',
    // `identity` cho chrome.identity.launchWebAuthFlow — luồng đăng nhập Google.
    permissions: ['storage', 'sidePanel', 'tabs', 'alarms', 'identity'],
    /**
     * Sinh từ `VITE_BACKEND_URL`, CÙNG biến mà `shared/settings.ts` dùng cho `backendUrl`
     * mặc định. Ràng buộc #10 vì thế rút từ ba chỗ phải khớp tay xuống một biến, và chỗ còn
     * lại — domain thật đang chạy — là thứ duy nhất bạn phải tự đảm bảo.
     *
     * Options vẫn là ô nhập tự do, nhưng Chrome chỉ cho gọi origin đã khai ở đây. Trỏ Options
     * sang một domain chưa khai thì request chết IM LẶNG — không lỗi mạng, không lỗi CORS,
     * chỉ là fetch không bao giờ đi. Danh sách luôn giữ cả localhost để đổi qua lại giữa hai
     * backend mà không phải build lại.
     */
    host_permissions: hostPermissionsFor(backendUrl),
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
  };
});
