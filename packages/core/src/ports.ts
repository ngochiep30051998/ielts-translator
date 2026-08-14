/**
 * Mọi thứ `@ielts/core` cần nhưng không tự làm được, khai thành interface.
 *
 * Đây là ranh giới duy nhất giữa core và môi trường. Nếu bạn định thêm `chrome.` hay
 * `localStorage` vào bất kỳ file nào khác trong package này — thứ bạn thật sự cần là một
 * port mới ở đây. `index.test.ts` có một test grep canh đúng chuyện đó.
 */

import type { ApiError, AuthUser, TranslateResult } from './types';

/**
 * Cách gắn danh tính vào một request HTTP. Hai surface làm hai kiểu khác hẳn nhau, và
 * gộp chúng lại là chỗ dễ sai nhất của cả kiến trúc:
 *
 * - **Extension** mang token trong header `Authorization`. Không có token = chưa đăng nhập,
 *   biết được TRƯỚC khi chạm mạng.
 * - **Web** không mang gì cả — cookie httpOnly do trình duyệt tự đính. Phía JavaScript
 *   KHÔNG đọc được nó, nên không có cách nào biết trước là đã đăng nhập hay chưa; chỉ
 *   server trả 401 mới biết.
 */
export interface CredentialsPort {
  /**
   * Header xác thực cho một request cần đăng nhập.
   *
   * `null` nghĩa là **chắc chắn chưa đăng nhập** — `ApiClient` ném `UNAUTHORIZED` tại chỗ,
   * không tốn một vòng mạng. Web KHÔNG BAO GIỜ trả `null`: nó không có cơ sở để khẳng định
   * điều đó, và trả `null` sẽ khoá người dùng đã đăng nhập ra ngoài.
   */
  authHeaders(): Promise<Record<string, string> | null>;

  /**
   * Giá trị `credentials` cho `fetch`.
   *
   * Web dùng `'same-origin'` để cookie được gửi kèm. Extension dùng `'omit'`: nó gọi
   * cross-origin từ `chrome-extension://`, và CORS phía backend cố ý KHÔNG bật
   * `allow_credentials` — gửi kèm cookie ở đó vừa vô nghĩa vừa mở thêm bề mặt.
   */
  readonly credentials: RequestCredentials;

  /** Gọi khi backend trả 401. Xoá phiên phía client nếu surface này có giữ gì. */
  onUnauthorized(): Promise<void>;
}

/** Kết quả dịch gần nhất, để màn hình đọc lại khi vừa mở. */
export interface LastResultStore {
  get(): Promise<TranslateResult | null>;
  set(result: TranslateResult | null): Promise<void>;
}

/** Luồng đăng nhập. Extension mở cửa sổ OAuth; web điều hướng cả trang. */
export interface AuthFlowPort {
  /**
   * Web KHÔNG BAO GIỜ resolve promise này — nó gán `location.href` và trang đi mất.
   * Màn đăng nhập giữ trạng thái "đang mở Google…" cho tới lúc đó, đúng như mong muốn.
   */
  signIn(): Promise<AuthUser>;
  signOut(): Promise<void>;
  /** Người dùng hiện tại, hoặc `null` nếu chưa đăng nhập. Không ném. */
  currentUser(): Promise<AuthUser | null>;
}

/**
 * Mọi thứ `operations` cần ngoài `ApiClient`.
 *
 * `onVocabChanged` và `openPanel` là no-op trên web: web không có badge và không có side
 * panel. Khai `optional` thay vì bắt web viết hàm rỗng.
 */
export interface OperationsPlatform {
  lastResult: LastResultStore;
  auth: AuthFlowPort;
  /**
   * Số thẻ đến hạn đã đổi — extension vẽ lại badge.
   *
   * Trả Promise được: đăng nhập/đăng xuất CHỜ nó xong (trạng thái badge phải đúng ngay khi
   * phiên đổi), còn các thao tác khác thì bắn rồi quên — người dùng không nên phải đợi một
   * con số nhỏ trên icon để thấy từ vừa lưu.
   */
  onVocabChanged?: () => void | Promise<void>;
  /** Mở side panel ở tab đang gửi message. Chỉ extension có. */
  openPanel?: (tabId: number) => Promise<void>;
}

/**
 * Đường đưa một `ExtensionRequest` tới nơi xử lý nó.
 *
 * Nằm ở ĐÚNG CÙNG TẦNG với `chrome.runtime.sendMessage`: `send` trả về object thô
 * `{ ok, data }`, còn việc bọc try/catch và kiểm hình dạng vẫn là của `sendToBackground`.
 * Giữ đúng tầng này là lý do 6 file test của side panel chuyển sang được mà không phải đổi
 * một assertion nào.
 */
export interface Transport {
  send(request: unknown): Promise<unknown>;
  /**
   * Lỗi trả về khi `send` ném.
   *
   * Là dữ liệu chứ không phải chuỗi cứng trong core: extension hỏng vì service worker vừa
   * reload, web hỏng vì lý do hoàn toàn khác — và cách khắc phục in ra cho người dùng cũng
   * khác. Core không có cơ sở để đoán cái nào.
   */
  readonly disconnectedError: ApiError;
}
