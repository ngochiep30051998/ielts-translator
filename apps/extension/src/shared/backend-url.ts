/**
 * Địa chỉ backend — nguồn sự thật DUY NHẤT cho cả bundle lẫn manifest.
 *
 * Ràng buộc #10 nói ba chỗ phải khớp: `host_permissions` trong manifest, `backendUrl` mặc
 * định, và domain thật đang chạy. Hai chỗ đầu là code, và giữ chúng khớp bằng tay là kiểu
 * việc người ta làm sai đúng vào lúc đang vội deploy. Module này gộp chúng về một biến môi
 * trường: `manifest.config.ts` đọc qua `loadEnv` lúc build, phần chạy trong trình duyệt đọc
 * qua `import.meta.env`.
 *
 * Vì sao đáng làm: trỏ Options sang một origin chưa khai trong `host_permissions` thì
 * request chết IM LẶNG — không lỗi mạng, không lỗi CORS, `fetch` đơn giản là không bao giờ
 * đi. Không có gì trong hệ thống nói cho bạn biết.
 *
 * File này KHÔNG được import gì từ `chrome.*` hay Node: nó chạy ở cả hai môi trường.
 */

/** Backend chạy local. Cũng là giá trị dùng khi `VITE_BACKEND_URL` chưa đặt. */
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8080';

/**
 * Bỏ dấu `/` thừa ở cuối. Chuỗi rỗng hoặc chỉ khoảng trắng coi như chưa đặt.
 *
 * Chuỗi rỗng phải rơi về mặc định chứ không được lọt qua: một `.env` có dòng
 * `VITE_BACKEND_URL=` (khai mà quên điền) sẽ dựng ra `fetch('/api/health')` — trỏ vào
 * chính trang web người dùng đang mở, và lỗi trả về sẽ nói về trang đó chứ không nói gì
 * về cấu hình sai.
 */
export function normaliseBackendUrl(raw: string | undefined): string {
  const trimmed = (raw ?? '').trim();
  if (trimmed === '') {
    return DEFAULT_BACKEND_URL;
  }
  return trimmed.replace(/\/+$/, '');
}

/**
 * Đổi một địa chỉ backend thành mẫu khớp cho `host_permissions`.
 *
 * Lấy `origin` chứ không nối chuỗi thô: Chrome chỉ nhận mẫu ở mức origin, nên một URL lỡ
 * mang theo đường dẫn (`https://x.vercel.app/api`) mà đưa thẳng vào manifest sẽ làm Chrome
 * từ chối NGUYÊN CẢ manifest — extension không tải được, và thông báo lỗi của Chrome không
 * chỉ ra dòng nào sai.
 */
export function toHostPermission(backendUrl: string): string {
  return `${new URL(backendUrl).origin}/*`;
}

/**
 * Danh sách `host_permissions` đầy đủ: luôn có backend local, cộng backend đã cấu hình.
 *
 * Giữ local kể cả khi đã trỏ sang production là cố ý — nó cho phép đổi Options về
 * `127.0.0.1` để đối chiếu hai backend mà không phải build lại extension.
 */
export function hostPermissionsFor(backendUrl: string): string[] {
  const local = toHostPermission(DEFAULT_BACKEND_URL);
  const configured = toHostPermission(backendUrl);
  return configured === local ? [local] : [local, configured];
}
