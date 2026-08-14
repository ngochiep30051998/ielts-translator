import { setTransport } from '@ielts/core';
import type { Transport } from '@ielts/core';

/**
 * Nối `sendToBackground` của `@ielts/core` vào `chrome.runtime`.
 *
 * Ràng buộc #1 vẫn nguyên vẹn: side panel, Options và content script KHÔNG tự gọi HTTP —
 * chúng gửi message, và service worker là chỗ duy nhất chạm mạng. File này chỉ nói cho core
 * biết "gửi đi đâu", không tự xử lý gì.
 */
export const chromeTransport: Transport = {
  send: (request) => chrome.runtime.sendMessage(request),
  /**
   * `chrome.runtime.sendMessage` REJECT khi không có bên nhận. Xảy ra thật khi service
   * worker vừa reload/crash, hoặc content script bị mồ côi sau khi reload extension —
   * và cách khắc phục là thứ chỉ đúng cho extension, nên nó nằm ở đây chứ không ở core.
   */
  disconnectedError: {
    code: 'BACKEND_DOWN',
    message:
      'Không liên lạc được với extension. Tải lại trang, hoặc bật lại extension trong chrome://extensions.',
    retryable: true,
  },
};

/** Gọi MỘT lần lúc khởi động mỗi surface, TRƯỚC khi render. */
export function installChromeTransport(): void {
  setTransport(chromeTransport);
}
