import type { CredentialsPort } from '@ielts/core';

/**
 * Header BẮT BUỘC để backend chấp nhận cookie phiên.
 *
 * Phải khớp từng ký tự với `WEB_CLIENT_HEADER` trong `api-service/app/auth/cookies.py`.
 * Lệch một chữ thì mọi request trả 401 và trông y hệt "phiên hết hạn" — không có lỗi CORS,
 * không có lỗi mạng, chỉ là không ai nhận ra bạn nữa.
 *
 * Vì sao tồn tại: cookie là *ambient credential*, nó tự đi kèm mọi request kể cả request do
 * một trang lạ kích hoạt. `SameSite=Lax` che POST/DELETE nhưng CỐ Ý cho GET điều hướng đi
 * qua, mà `GET /api/srs/due` thì commit DB và xếp tới 10 lượt gọi Gemini. Điều hướng
 * top-level không đặt được header; fetch cross-site mang header lạ thì vấp preflight, mà
 * CORS chỉ mở cho `chrome-extension://`. Nên header này là chốt chặn CSRF thật sự.
 */
export const WEB_CLIENT_HEADER = 'X-IELTS-Web';

export const webCredentials: CredentialsPort = {
  /**
   * KHÔNG BAO GIỜ trả `null`.
   *
   * `null` nghĩa là "chắc chắn chưa đăng nhập", và web không có cơ sở để khẳng định điều
   * đó: cookie phiên là httpOnly nên JavaScript không đọc được. Trả `null` ở đây sẽ khoá
   * một người ĐANG đăng nhập ra ngoài, vì `ApiClient` ném UNAUTHORIZED trước khi kịp gọi
   * mạng. Chỉ server mới biết, và nó nói bằng 401.
   */
  async authHeaders() {
    return { [WEB_CLIENT_HEADER]: '1' };
  },

  /** Cookie chỉ được gửi kèm khi khai `credentials`. Mặc định của `fetch` là 'same-origin'
   *  nhưng khai tường minh để không phụ thuộc mặc định của trình duyệt. */
  credentials: 'same-origin',

  /**
   * Không có gì để xoá phía client: cookie là httpOnly, chỉ server xoá được nó. Phiên chết
   * sẽ tự lộ ra ở request kế tiếp, và `App` đưa người dùng về màn đăng nhập.
   */
  async onUnauthorized() {},
};
