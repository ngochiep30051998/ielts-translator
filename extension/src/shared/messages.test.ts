import { describe, it, expect, beforeEach, vi } from 'vitest';
import { sendToBackground } from './messages';

const sendMessageMock = () => chrome.runtime.sendMessage as unknown as ReturnType<typeof vi.fn>;

describe('sendToBackground', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('chuyển thẳng phản hồi ok của service worker', async () => {
    sendMessageMock().mockResolvedValue({ ok: true, data: { id: 1, alreadyExists: false } });

    const response = await sendToBackground({ type: 'SAVE_WORD', result: {} as never, tags: [] });

    expect(response).toEqual({ ok: true, data: { id: 1, alreadyExists: false } });
  });

  it('chuyển thẳng phản hồi lỗi có cấu trúc của service worker', async () => {
    sendMessageMock().mockResolvedValue({
      ok: false, error: { code: 'GEMINI_QUOTA', message: 'Hết quota', retryable: false },
    });

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toEqual({
      ok: false, error: { code: 'GEMINI_QUOTA', message: 'Hết quota', retryable: false },
    });
  });

  it('không ném khi không có bên nhận, trả lỗi retryable thay vì reject', async () => {
    sendMessageMock().mockRejectedValue(
      new Error('Could not establish connection. Receiving end does not exist.'),
    );

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toMatchObject({ ok: false, error: { code: 'BACKEND_DOWN', retryable: true } });
  });

  it('coi phản hồi undefined (listener không gọi sendResponse) là lỗi INTERNAL', async () => {
    sendMessageMock().mockResolvedValue(undefined);

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toMatchObject({ ok: false, error: { code: 'INTERNAL', retryable: false } });
  });

  it('coi phản hồi sai hình dạng là lỗi INTERNAL', async () => {
    sendMessageMock().mockResolvedValue({ something: 'else' });

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toMatchObject({ ok: false, error: { code: 'INTERNAL' } });
  });

  it('giữ nguyên phản hồi ok kèm data null', async () => {
    sendMessageMock().mockResolvedValue({ ok: true, data: null });

    const response = await sendToBackground({ type: 'GET_LAST_RESULT' });

    expect(response).toEqual({ ok: true, data: null });
  });
});
