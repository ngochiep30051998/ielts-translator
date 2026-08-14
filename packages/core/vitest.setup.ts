import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

import { setTransport } from './src/transport';
import { resetSettingsProvider } from './src/settings';
import { resetSurfaceCapabilities } from './src/surface';

/**
 * Transport giả cho mọi test của core.
 *
 * Nó nằm ở ĐÚNG CÙNG TẦNG với `chrome.runtime.sendMessage` ngày trước — trả về object thô
 * `{ ok, data }`, còn `sendToBackground` vẫn là chỗ bọc lỗi. Nhờ vậy các test của side
 * panel chuyển sang đây chỉ phải đổi tên thứ mình giả lập, không phải đổi cách giả lập.
 *
 * Xuất ra để test dùng trực tiếp:
 *
 *     transportSend.mockImplementation(async () => ({ ok: true, data: ... }));
 */
export const transportSend = vi.fn();

/**
 * Lỗi khi transport ném. Trong test nó gần như không xảy ra, nhưng phải có giá trị thật —
 * `sendToBackground` trả thẳng object này ra cho UI.
 */
export const DISCONNECTED_ERROR = {
  code: 'BACKEND_DOWN',
  message: 'Transport giả trong test đã ném.',
  retryable: true,
} as const;

setTransport({ send: transportSend, disconnectedError: DISCONNECTED_ERROR });

// Provider cài đặt là trạng thái cấp module. Test nào đặt provider riêng mà không dọn sẽ
// làm test sau của cùng file đọc nhầm giá trị — trả về mặc định trước mỗi test là cách rẻ
// nhất để chuyện đó không thành một giờ đi tìm.
beforeEach(() => {
  resetSettingsProvider();
  resetSurfaceCapabilities();
});
