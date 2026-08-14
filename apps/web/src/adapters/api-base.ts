/**
 * Địa chỉ gốc để gọi API.
 *
 * Mặc định là **chuỗi rỗng**, tức mọi lời gọi dùng đường dẫn tương đối `/api/...` và đi tới
 * chính origin đang phục vụ trang. Đó không phải mặc định cho tiện — nó là điều kiện để cả
 * cơ chế đăng nhập hoạt động: cookie phiên mang `SameSite=Lax`, và trình duyệt chỉ gửi kèm
 * cookie đó cho request CÙNG origin.
 *
 * Biến `VITE_API_BASE_URL` vẫn có, cho những cách chạy mà tôi chưa lường trước. Nhưng đặt nó
 * sang một origin khác sẽ làm mọi request trả 401 dù đã đăng nhập — nên `resolveApiBase`
 * phát hiện và trả về một cảnh báo để `runtime` in ra console. Im lặng ở đây là đẩy người
 * đọc vào một buổi chiều đi tìm "vì sao đăng nhập xong vẫn 401".
 */

export interface ApiBase {
  /** Truyền thẳng cho `ApiClient`. Rỗng = đường dẫn tương đối. */
  baseUrl: string;
  /** Thông điệp phải in ra console, hoặc `null` khi cấu hình lành. */
  canhBao: string | null;
}

const HUONG_DAN_CROSS_ORIGIN = [
  'Sẽ hỏng ở HAI tầng, và phải sửa cả hai:',
  '',
  '  1. CORS chặn ngay. Mọi request mang header X-IELTS-Web nên trình duyệt gửi preflight',
  '     trước, mà backend chỉ mở CORS cho chrome-extension://<id> (ràng buộc #7). Bạn sẽ',
  '     thấy "blocked by CORS policy" trong console.',
  '     Sửa: app/main.py — thêm origin này kèm allow_credentials=True',
  '',
  '  2. Kể cả khi CORS đã mở, cookie phiên mang SameSite=Lax nên trình duyệt VẪN không gửi',
  '     nó sang origin khác. Lúc đó request đi được nhưng không mang danh tính, và bạn nhận',
  '     401 sạch sẽ — không còn lỗi nào để lần theo nữa. Đây mới là tầng khó chẩn đoán.',
  '     Sửa: app/auth/cookies.py — đổi cookie phiên sang SameSite=None; Secure',
  '',
  'Cả hai thay đổi đó hiện CHƯA có. Cách đúng là để VITE_API_BASE_URL trống.',
].join('\n');

/**
 * @param raw    giá trị thô của `VITE_API_BASE_URL`
 * @param origin origin của trang đang chạy (`window.location.origin`)
 */
export function resolveApiBase(raw: string | undefined, origin: string): ApiBase {
  const baseUrl = (raw ?? '').trim().replace(/\/+$/, '');

  // Rỗng = cùng origin, đường đi đúng. Không có gì để cảnh báo.
  if (!baseUrl) return { baseUrl: '', canhBao: null };

  // Đường dẫn tương đối (`/api-v2` chẳng hạn) vẫn là cùng origin.
  if (baseUrl.startsWith('/')) return { baseUrl, canhBao: null };

  let cauHinh: string;
  try {
    cauHinh = new URL(baseUrl).origin;
  } catch {
    return {
      baseUrl,
      canhBao: `VITE_API_BASE_URL không phải URL hợp lệ: ${baseUrl}`,
    };
  }

  if (cauHinh === origin) return { baseUrl, canhBao: null };

  return {
    baseUrl,
    canhBao:
      `VITE_API_BASE_URL trỏ sang ${cauHinh}, khác origin của trang (${origin}).\n` +
      HUONG_DAN_CROSS_ORIGIN,
  };
}
