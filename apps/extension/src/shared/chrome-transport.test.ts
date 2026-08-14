import { describe, it, expect, beforeEach, vi } from 'vitest';
import { sendToBackground } from '@ielts/core';
import { chromeTransport, installChromeTransport } from './chrome-transport';

/**
 * Đường `chrome.runtime` sau khi `sendToBackground` chuyển sang `@ielts/core`.
 *
 * Logic bọc lỗi đã có test riêng ở core với transport giả; ở đây chỉ chứng minh đúng một
 * chuyện — transport của extension thật sự nối vào `chrome.runtime.sendMessage`, và ca
 * "không có bên nhận" ra đúng thông điệp của extension chứ không phải của web.
 */
describe('chromeTransport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installChromeTransport();
  });

  it('gửi request qua chrome.runtime.sendMessage', async () => {
    vi.mocked(chrome.runtime.sendMessage).mockResolvedValue({ ok: true, data: null });

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith({ type: 'GET_LAST_RESULT' });
    expect(response).toEqual({ ok: true, data: null });
  });

  it('không có bên nhận thì trả lỗi retryable của extension, không ném', async () => {
    vi.mocked(chrome.runtime.sendMessage).mockRejectedValue(
      new Error('Could not establish connection. Receiving end does not exist.'),
    );

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toEqual({ ok: false, error: chromeTransport.disconnectedError });
    expect(chromeTransport.disconnectedError.message).toContain('chrome://extensions');
  });
});
