import { startUpdateChecks, updateSignal } from './sw-update';

/** Đường dẫn service worker. `public/sw.js` được Vite chép nguyên xi ra gốc `dist/`. */
const SW_PATH = '/sw.js';

/**
 * Đăng ký service worker.
 *
 * **Chỉ ở bản build production.** Ở dev, SW sẽ cache asset của Vite rồi đánh nhau với HMR:
 * sửa code mà màn hình không đổi, và cách chữa duy nhất là tự đi xoá cache trong DevTools.
 * Đó là loại rắc rối tốn hàng giờ mà chẳng đổi lấy được gì trong lúc phát triển.
 *
 * Không có SW thì app vẫn chạy đủ chức năng — chỉ mất phần offline và mất mục "cài vào màn
 * hình chính" trên vài trình duyệt. Nên mọi lỗi ở đây đều nuốt.
 */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) return;
  if (!('serviceWorker' in navigator)) return;

  // Đợi `load`: đăng ký SW tranh băng thông với chính những asset đang cần để vẽ màn hình
  // đầu tiên.
  window.addEventListener('load', () => {
    void navigator.serviceWorker
      .register(SW_PATH)
      .then((reg) => {
        // Web app cài vào màn hình chính gần như không bao giờ được đóng, nên nếu không
        // theo dõi ở đây thì người dùng chạy bundle của lần mở đầu tiên cho tới hết đời máy.
        updateSignal.watch(reg, navigator.serviceWorker);
        startUpdateChecks(reg);
      })
      .catch(() => {
        /* Không có offline thì thôi, app vẫn chạy. */
      });
  });
}

/**
 * Bảo service worker xoá cache của `/api/*`.
 *
 * Gọi khi ĐĂNG XUẤT, và đây không phải dọn dẹp cho gọn: cache dùng chung theo ORIGIN chứ
 * không theo người dùng. Bỏ bước này thì trên máy dùng chung, người đăng nhập sau sẽ thấy
 * sổ từ của người trước hiện ra từ cache trước khi request thật kịp trả về.
 */
export function xoaCacheApi(): void {
  navigator.serviceWorker?.controller?.postMessage({ type: 'XOA_CACHE_API' });
}
