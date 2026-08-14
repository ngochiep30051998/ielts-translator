import type { ApiClient, AuthFlowPort, AuthUser } from '@ielts/core';

import { sessionLastResult } from './last-result';
import { xoaCacheApi } from '../register-sw';

/** Đường dẫn mở luồng đăng nhập. Backend sinh state, set cookie, rồi redirect sang Google. */
export const SIGN_IN_PATH = '/api/auth/google/start';

export function createWebAuthFlow(client: ApiClient): AuthFlowPort {
  return {
    /**
     * KHÔNG BAO GIỜ resolve.
     *
     * Đây không phải thiếu sót mà là hình dạng thật của luồng: gán `location.href` là bỏ cả
     * trang hiện tại đi. Không dòng nào sau đó chạy nữa, và promise này chết cùng document.
     *
     * `LoginScreen` đang ở trạng thái "Đang mở Google…" lúc đó, và đó đúng là thứ nên hiện
     * trong lúc trình duyệt điều hướng. Resolve giả một giá trị sẽ làm màn hình nháy sang
     * trạng thái đã-đăng-nhập ngay trước khi trang biến mất.
     */
    signIn(): Promise<AuthUser> {
      window.location.href = SIGN_IN_PATH;
      return new Promise<AuthUser>(() => {});
    },

    /**
     * Cookie phiên là httpOnly nên chỉ server xoá được — `operations` đã gọi
     * `client.logout()` trước khi tới đây, và response của nó mang `Set-Cookie` xoá.
     *
     * Việc còn lại là dọn thứ web tự giữ. Bỏ bước này là trên máy dùng chung, người sau mở
     * tab cũ vẫn thấy đoạn dịch của người trước.
     */
    async signOut() {
      await sessionLastResult.set(null);
      // Cache của `/api/*` nằm ở service worker và dùng chung theo ORIGIN, không theo người
      // dùng. Không xoá thì trên máy dùng chung, người đăng nhập sau thấy sổ từ của người
      // trước hiện ra từ cache trước khi request thật kịp trả về.
      xoaCacheApi();
    },

    /**
     * Hỏi server, vì web KHÔNG đọc được cookie httpOnly.
     *
     * Khác hẳn extension — bên đó đọc user từ `chrome.storage` và cố ý không gọi mạng mỗi
     * lần mở panel. Ở đây không có lựa chọn nào khác, nhưng đổi lại được một thứ: chính lượt
     * gọi này làm mới hạn cookie phía server (xem `router.me`).
     *
     * **Không ném.** Chưa đăng nhập, phiên hết hạn và backend chết đều ra `null` — `App`
     * hiển thị màn đăng nhập, là thứ duy nhất người dùng làm được gì đó ở cả ba ca.
     */
    async currentUser(): Promise<AuthUser | null> {
      try {
        return await client.authMe();
      } catch {
        return null;
      }
    },
  };
}
