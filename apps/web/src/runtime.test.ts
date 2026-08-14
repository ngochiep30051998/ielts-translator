import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { sendToBackground } from '@ielts/core';

import { WEB_CLIENT_HEADER } from './adapters/credentials';
import { installWebRuntime } from './runtime';

/**
 * Đấu dây của web, kiểm từ đầu này sang đầu kia: `sendToBackground` → `operations` →
 * `ApiClient` → `fetch`.
 *
 * Chỉ giả lập `fetch`, tức là toàn bộ đường thật ở giữa vẫn chạy — dựng URL, gắn header,
 * map lỗi. Giả lập ở tầng cao hơn là bỏ qua đúng phần dễ đấu sai nhất.
 */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('runtime của web', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    installWebRuntime();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('gọi đường dẫn TƯƠNG ĐỐI — web cùng origin với backend', async () => {
    // Có tiền tố origin nghĩa là request thành cross-site, và cookie SameSite=Lax sẽ không
    // bao giờ được gửi. Triệu chứng khi đó chỉ là 401 sạch sẽ, không lỗi CORS nào để lần.
    fetchMock.mockResolvedValue(jsonResponse({ dueCount: 3, newCount: 1, learnedCount: 9 }));

    await sendToBackground({ type: 'GET_SRS_STATS', newLimit: 30 });

    expect(fetchMock.mock.calls[0][0]).toBe('/api/srs/stats?newLimit=30');
  });

  it('mọi request mang header X-IELTS-Web — thiếu nó backend coi như chưa đăng nhập', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await sendToBackground({ type: 'GET_DUE_CARDS', limit: 50, newLimit: 30 });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)[WEB_CLIENT_HEADER]).toBe('1');
  });

  it('gửi kèm cookie same-origin', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await sendToBackground({ type: 'GET_DUE_CARDS', limit: 50, newLimit: 30 });

    expect((fetchMock.mock.calls[0][1] as RequestInit).credentials).toBe('same-origin');
  });

  it('KHÔNG gắn Authorization — web không có token nào để gắn', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await sendToBackground({ type: 'GET_DUE_CARDS', limit: 50, newLimit: 30 });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('trả { ok: true, data } khi thành công', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ dueCount: 3, newCount: 1, learnedCount: 9 }));

    const response = await sendToBackground({ type: 'GET_SRS_STATS', newLimit: 30 });

    expect(response).toMatchObject({ ok: true, data: { dueCount: 3 } });
  });

  it('lỗi có cấu trúc của backend đi thẳng ra UI, không bị nuốt', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: 'GEMINI_QUOTA', message: 'Hết quota', retryable: false }, 429),
    );

    const response = await sendToBackground({ type: 'GET_SRS_STATS', newLimit: 30 });

    expect(response).toMatchObject({
      ok: false,
      error: { code: 'GEMINI_QUOTA', retryable: false },
    });
  });

  it('mất mạng thành BACKEND_DOWN retryable, KHÔNG ném', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const response = await sendToBackground({ type: 'GET_SRS_STATS', newLimit: 30 });

    expect(response).toMatchObject({ ok: false, error: { code: 'BACKEND_DOWN', retryable: true } });
  });

  it('401 trả UNAUTHORIZED để App đưa về màn đăng nhập', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: 'UNAUTHORIZED', message: 'Cần đăng nhập', retryable: false }, 401),
    );

    const response = await sendToBackground({ type: 'GET_SRS_STATS', newLimit: 30 });

    expect(response).toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED' } });
  });

  it('GET_AUTH_STATE hỏi /api/auth/me và trả null khi chưa đăng nhập', async () => {
    // Khác hẳn extension — bên đó đọc user từ chrome.storage. Web không đọc được cookie
    // httpOnly nên bắt buộc phải hỏi server, và chính lượt gọi đó làm mới hạn cookie.
    fetchMock.mockResolvedValue(
      jsonResponse({ code: 'UNAUTHORIZED', message: 'Cần đăng nhập', retryable: false }, 401),
    );

    const response = await sendToBackground({ type: 'GET_AUTH_STATE' });

    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/me');
    expect(response).toEqual({ ok: true, data: null });
  });

  it('GET_AUTH_STATE trả user khi đã đăng nhập', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ email: 'a@b.com', displayName: 'A', pictureUrl: null }),
    );

    const response = await sendToBackground({ type: 'GET_AUTH_STATE' });

    expect(response).toMatchObject({ ok: true, data: { email: 'a@b.com' } });
  });

  it('TRANSLATE_TEXT lưu kết quả cho GET_LAST_RESULT đọc lại', async () => {
    window.sessionStorage.clear();
    fetchMock.mockResolvedValue(
      jsonResponse({ direction: 'EN_VI', mode: 'WORD', cached: false, payload: { term: 'x' } }),
    );

    await sendToBackground({ type: 'TRANSLATE_TEXT', text: 'mitigate' });
    const lai = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(lai).toMatchObject({ ok: true, data: { sourceText: 'mitigate' } });
  });
});
