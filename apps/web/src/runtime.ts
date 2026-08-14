import {
  ApiClient, createOperations, setSettingsProvider, setSurfaceCapabilities, setTransport,
  toApiError,
} from '@ielts/core';
import type { ExtensionRequest, Transport } from '@ielts/core';

import { resolveApiBase } from './adapters/api-base';
import { createWebAuthFlow } from './adapters/auth-flow';
import { webCredentials } from './adapters/credentials';
import { sessionLastResult } from './adapters/last-result';
import { loadWebSettings } from './adapters/settings-store';

/**
 * Địa chỉ API. Mặc định RỖNG — mọi đường dẫn là tương đối, đi tới chính origin đang phục vụ
 * trang.
 *
 * Không phải chuyện tiện tay: cùng origin là điều kiện để cookie `SameSite=Lax` được gửi
 * kèm. `resolveApiBase` phát hiện cấu hình trỏ sang origin khác và trả về cảnh báo — in ra
 * lúc khởi động thay vì để người đọc tự đoán vì sao đăng nhập xong vẫn 401.
 */
const apiBase = resolveApiBase(import.meta.env.VITE_API_BASE_URL, window.location.origin);

const client = new ApiClient(async () => apiBase.baseUrl, webCredentials);

const handle = createOperations(client, {
  lastResult: sessionLastResult,
  auth: createWebAuthFlow(client),
  // Không có `onVocabChanged`: web không có badge nào để vẽ.
  // Không có `openPanel`: web không có side panel.
});

/**
 * Transport của web: gọi thẳng `operations` trong CÙNG tiến trình.
 *
 * Không có service worker ở giữa như extension, nhưng hình dạng trả về phải giống hệt —
 * `{ ok, data }` hoặc `{ ok: false, error }` — vì `sendToBackground` và toàn bộ UI dùng
 * chung không được biết mình đang chạy ở đâu.
 *
 * Bắt lỗi ngay tại đây, đúng như listener của service worker đang làm.
 */
export const webTransport: Transport = {
  async send(request: unknown) {
    try {
      return { ok: true, data: await handle(request as ExtensionRequest) };
    } catch (error) {
      return { ok: false, error: toApiError(error) };
    }
  },

  /**
   * Gần như không tới được: `send` ở trên đã nuốt mọi lỗi. Vẫn phải là một giá trị thật vì
   * `sendToBackground` trả thẳng nó ra UI nếu `send` ném — và nó chỉ ném khi có lỗi lập
   * trình trong chính hàm bọc kia.
   */
  disconnectedError: {
    code: 'INTERNAL',
    message: 'Lỗi không xác định trong ứng dụng. Tải lại trang.',
    retryable: true,
  },
};

/** Gọi MỘT lần lúc khởi động, TRƯỚC khi render. */
export function installWebRuntime(): void {
  if (apiBase.canhBao) {
    // `console.error` chứ không `warn`: đây là cấu hình làm app KHÔNG chạy được, không phải
    // một lời khuyên. Nó phải nổi bật giữa đống log của trình duyệt.
    console.error(`[IELTS Translator] Cấu hình sai:\n${apiBase.canhBao}`);
  }
  setTransport(webTransport);
  setSettingsProvider(async () => loadWebSettings());
  // Web không cắm được vào trang của người khác. Chỉ dẫn "bôi đen text trên trang" ở
  // đây là bảo người dùng làm một việc bất khả thi rồi để họ tự nghi ngờ mình.
  setSurfaceCapabilities({ selectionCapture: false });
}
