import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { ApiClient } from './api-client';

const BASE_URL = 'http://127.0.0.1:8080';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let client: ApiClient;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    client = new ApiClient(() => Promise.resolve(BASE_URL));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('POST /api/translate và gắn sourceText vào kết quả', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      direction: 'EN_VI', mode: 'WORD', cached: false, payload: { meaning_vi: 'tái tạo' },
    }));

    const result = await client.translate({
      text: 'renewable', contextSentence: 'We need renewable energy.',
      sourceUrl: 'https://example.com', pageTitle: 'Example',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/translate`,
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.sourceText).toBe('renewable');
    expect(result.sourceSentence).toBe('We need renewable energy.');
  });

  it('ném đúng ApiError khi backend trả lỗi có cấu trúc', async () => {
    fetchMock.mockResolvedValue(jsonResponse(
      { code: 'GEMINI_QUOTA', message: 'Đã hết quota Gemini', retryable: false }, 429));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'GEMINI_QUOTA', retryable: false });
  });

  it('ánh xạ lỗi mạng thành BACKEND_DOWN và đánh dấu retryable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'BACKEND_DOWN', retryable: true });
  });

  it('ánh xạ phản hồi không phải JSON thành INTERNAL', async () => {
    fetchMock.mockResolvedValue(new Response('<html>lỗi</html>', { status: 500 }));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'INTERNAL' });
  });

  it('cache kết quả health trong 30 giây', async () => {
    vi.useFakeTimers();
    // mockImplementation chứ không mockResolvedValue: mỗi lần fetch phải trả một
    // Response mới, vì body của Response chỉ đọc được đúng một lần.
    fetchMock.mockImplementation(async () => jsonResponse({
      status: 'UP', dbConnected: true, geminiConfigured: true,
    }));

    await client.health();
    await client.health();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(31_000);
    await client.health();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('không cache health khi lần gọi trước thất bại', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(client.health()).rejects.toMatchObject({ code: 'BACKEND_DOWN' });

    fetchMock.mockResolvedValue(jsonResponse({
      status: 'UP', dbConnected: true, geminiConfigured: true,
    }));
    await client.health();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('searchVocab dựng đúng query string, bỏ tham số rỗng', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      content: [], totalElements: 0, totalPages: 0, number: 0,
    }));

    await client.searchVocab({ query: 'renew', tag: null, page: 2 });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=renew');
    expect(calledUrl).toContain('page=2');
    expect(calledUrl).not.toContain('tag=');
  });

  it('deleteVocab gọi đúng method DELETE', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await client.deleteVocab(42);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/vocab/42`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});
