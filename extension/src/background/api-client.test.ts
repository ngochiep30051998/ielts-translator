import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { ApiClient } from './api-client';
import { loadAuth, saveAuth } from '../shared/auth-storage';

const USER = { email: 'a@b.com', displayName: 'A', pictureUrl: null };

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

  beforeEach(async () => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    client = new ApiClient(() => Promise.resolve(BASE_URL));
    // Mặc định đã đăng nhập: mọi endpoint nghiệp vụ nay đòi token, nên không có nó thì
    // request() ném trước khi chạm fetch và test cũ đo nhầm thứ khác.
    await chrome.storage.local.clear();
    await saveAuth('test-token', USER);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    // Gỡ spy đặt trên AbortSignal.timeout ở nhóm test timeout; để rò rỉ thì mọi
    // test sau vẫn đếm chung một mock và số lần gọi thành vô nghĩa.
    vi.restoreAllMocks();
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

  it('getDueCards gọi đúng đường dẫn kèm limit và newLimit', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await client.getDueCards({ limit: 50, newLimit: 30 });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/due?limit=50&newLimit=30`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('submitReview POST đúng body', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ nextDueDate: '2026-08-07', intervalDays: 1, easeFactor: 2.5 }),
    );

    const result = await client.submitReview({ cardId: 7, rating: 'GOOD' });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/review`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ cardId: 7, rating: 'GOOD' }),
      }),
    );
    expect(result.intervalDays).toBe(1);
  });

  it('getPracticeCards gọi GET /api/srs/practice với limit', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await client.getPracticeCards(30);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/practice?limit=30`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('submitPractice gọi POST /api/srs/practice', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await client.submitPractice({ cardId: 7, rating: 'GOOD' });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/practice`,
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('srsStats gọi đúng đường dẫn kèm newLimit', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ dueCount: 3, newCount: 1, learnedCount: 9 }));

    const stats = await client.srsStats(30);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/srs/stats?newLimit=30`,
      expect.objectContaining({ method: 'GET' }),
    );
    expect(stats.dueCount).toBe(3);
  });

  it('learningStats gọi GET /api/stats', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      streak: { current: 0, longest: 0, lastActiveDate: null },
      totals: { reviews: 0, learnedWords: 0, activeDays: 0 },
      daily: [],
      recall: { again: 0, hard: 0, good: 0, easy: 0 },
      quiz: [],
    }));

    await client.learningStats();

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/stats`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('review thẻ không tồn tại ném NOT_FOUND, không retry được', async () => {
    fetchMock.mockResolvedValue(jsonResponse(
      { code: 'NOT_FOUND', message: 'Không tìm thấy thẻ 999', retryable: false }, 404));

    await expect(client.submitReview({ cardId: 999, rating: 'GOOD' }))
      .rejects.toMatchObject({ code: 'NOT_FOUND', retryable: false });
  });

  /* ---------- Đăng nhập và token ---------- */

  describe('auth', () => {
    it('mọi request nghiệp vụ mang Authorization: Bearer', async () => {
      fetchMock.mockResolvedValue(jsonResponse([]));

      await client.getDueCards({ limit: 1, newLimit: 1 });

      const init = fetchMock.mock.calls[0][1] as RequestInit;
      expect((init.headers as Record<string, string>).Authorization).toBe('Bearer test-token');
    });

    it('chưa đăng nhập thì KHÔNG gọi fetch, ném UNAUTHORIZED tại chỗ', async () => {
      // Gọi rồi nhận 401 cũng ra kết quả đó, nhưng tốn một vòng mạng và một dòng log rác
      // mỗi lần alarm badge chạy lúc chưa đăng nhập.
      await chrome.storage.local.clear();

      await expect(client.srsStats(30)).rejects.toMatchObject({ code: 'UNAUTHORIZED' });
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('/api/auth/google KHÔNG gắn Authorization — lúc đó chưa có token nào', async () => {
      await chrome.storage.local.clear();
      fetchMock.mockResolvedValue(jsonResponse({
        token: 't', expiresAt: '2026-10-09T00:00:00Z', user: USER,
      }));

      await client.googleLogin({ code: 'c', redirectUri: 'https://x.chromiumapp.org/' });

      const init = fetchMock.mock.calls[0][1] as RequestInit;
      expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
    });

    it('/api/health KHÔNG cần token — thứ dùng để chẩn đoán khi auth hỏng', async () => {
      await chrome.storage.local.clear();
      fetchMock.mockResolvedValue(jsonResponse({
        status: 'UP', dbConnected: true, geminiConfigured: true,
      }));

      await expect(client.health()).resolves.toMatchObject({ status: 'UP' });
    });

    it('nhận 401 thì XOÁ token — request sau không lặp lại vòng đó', async () => {
      fetchMock.mockResolvedValue(jsonResponse(
        { code: 'UNAUTHORIZED', message: 'Cần đăng nhập', retryable: false }, 401));

      await expect(client.srsStats(30)).rejects.toMatchObject({ code: 'UNAUTHORIZED' });

      expect(await loadAuth()).toBeNull();
    });

    it('lỗi 404 KHÔNG xoá token — chỉ 401 mới là phiên chết', async () => {
      fetchMock.mockResolvedValue(jsonResponse(
        { code: 'NOT_FOUND', message: 'x', retryable: false }, 404));

      await expect(client.submitReview({ cardId: 1, rating: 'GOOD' })).rejects.toBeTruthy();

      // Đá người dùng ra màn đăng nhập vì một id sai là mất hết nháp đang gõ dở.
      expect(await loadAuth()).not.toBeNull();
    });

    it('logout gọi POST /api/auth/logout kèm token', async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

      await client.logout();

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE_URL}/api/auth/logout`,
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  /* ---------- Timeout: lưới chặn cuối, phải LỚN HƠN xấu nhất của backend ---------- */

  describe('timeout', () => {
    /**
     * Cọc canh môi trường, KHÔNG phải test hành vi của ApiClient.
     *
     * Mọi request đều đi qua AbortSignal.timeout(). Nếu môi trường test thiếu API đó
     * (đổi jsdom, đổi `environment` trong vite.config, chạy dưới runner khác) thì
     * TOÀN BỘ test đụng tới request() đỏ cùng lúc và không cái nào nói ra nguyên nhân.
     * Test này đỏ một mình và gọi thẳng tên thủ phạm.
     */
    it('môi trường test có AbortSignal.timeout', () => {
      expect(typeof AbortSignal.timeout).toBe('function');
    });

    /**
     * Đọc thẳng con số đã truyền vào AbortSignal.timeout. Không có cách nào đọc
     * ngược thời hạn ra từ một AbortSignal đã dựng, mà khẳng định "có truyền gì đó"
     * thì không bắt được ca đặt nhầm 20s — chính là rủi ro R5 của hợp đồng.
     */
    function spyTimeout() {
      return vi.spyOn(AbortSignal, 'timeout');
    }

    it('mọi request thường bọc timeout mặc định 40 giây', async () => {
      const timeout = spyTimeout();
      fetchMock.mockResolvedValue(jsonResponse({ dueCount: 0, newCount: 0, learnedCount: 0 }));

      await client.srsStats(30);

      expect(timeout).toHaveBeenCalledWith(40_000);
    });

    it('generateQuiz nới lên 70 giây — sinh cả lô đề lâu hơn dịch một từ', async () => {
      const timeout = spyTimeout();
      fetchMock.mockResolvedValue(jsonResponse([]));

      await client.generateQuiz({ vocabIds: null, count: 4, type: 'FILL_BLANK' });

      expect(timeout).toHaveBeenCalledWith(70_000);
    });

    it('answerQuiz nới lên 50 giây — chấm FREE_WRITE tốn một lượt gọi Gemini', async () => {
      const timeout = spyTimeout();
      fetchMock.mockResolvedValue(jsonResponse({
        correct: true, score: 100, feedback: 'Chính xác.', improvedVersion: null,
      }));

      await client.answerQuiz({ quizItemId: 7, answer: '2' });

      expect(timeout).toHaveBeenCalledWith(50_000);
    });

    it('explainQuiz dùng mức chờ 50 giây như chấm bài — cũng một lượt gọi Gemini', async () => {
      const timeout = spyTimeout();
      fetchMock.mockResolvedValue(jsonResponse({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      }));

      await client.explainQuiz({ quizItemId: 7 });

      expect(timeout).toHaveBeenCalledWith(50_000);
    });

    it('mọi request mang theo một AbortSignal', async () => {
      fetchMock.mockResolvedValue(jsonResponse([]));

      await client.getDueCards({ limit: 50, newLimit: 30 });

      const init = fetchMock.mock.calls[0][1] as RequestInit;
      expect(init.signal).toBeInstanceOf(AbortSignal);
    });

    it('quá hạn chờ trả BACKEND_DOWN kèm thông điệp phân biệt với mất kết nối', async () => {
      // vi.useFakeTimers() KHÔNG điều khiển được AbortSignal.timeout (nó không chạy
      // trên setTimeout của JS) — test bằng fake timer sẽ treo. Giả lập thẳng lỗi mà
      // fetch ném ra khi signal quá hạn.
      fetchMock.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'));

      await expect(client.generateQuiz({ vocabIds: null, count: 4, type: 'FILL_BLANK' }))
        .rejects.toMatchObject({
          code: 'BACKEND_DOWN',
          retryable: true,
          message: expect.stringContaining('quá hạn'),
        });
    });

    it('mất kết nối và quá hạn chờ là hai thông điệp khác nhau', async () => {
      fetchMock.mockRejectedValueOnce(new DOMException('signal timed out', 'TimeoutError'));
      const timedOut = await client.getDueCards({ limit: 1, newLimit: 1 }).catch((e) => e);

      fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
      const offline = await client.getDueCards({ limit: 1, newLimit: 1 }).catch((e) => e);

      expect(timedOut.message).not.toBe(offline.message);
      expect(offline.message).toContain('Không kết nối được');
    });
  });

  /* ---------- Quiz ---------- */

  describe('quiz', () => {
    it('generateQuiz POST /api/quiz/generate với field type trên đường HTTP', async () => {
      fetchMock.mockResolvedValue(jsonResponse([]));

      await client.generateQuiz({ vocabIds: null, count: 4, type: 'COLLOCATION_CHOICE' });

      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe(`${BASE_URL}/api/quiz/generate`);
      expect(init.method).toBe('POST');
      // Message dùng tên `quizType`, HTTP dùng `type`. Đây là chỗ ánh xạ duy nhất.
      expect(JSON.parse(init.body as string)).toEqual({
        vocabIds: null, count: 4, type: 'COLLOCATION_CHOICE',
      });
    });

    it('không có ứng viên thì trả mảng rỗng chứ không phải lỗi', async () => {
      fetchMock.mockResolvedValue(jsonResponse([]));

      await expect(client.generateQuiz({ vocabIds: null, count: 10, type: 'FREE_WRITE' }))
        .resolves.toEqual([]);
    });

    it('answerQuiz POST /api/quiz/answer đúng body', async () => {
      fetchMock.mockResolvedValue(jsonResponse({
        correct: false, score: 0, feedback: 'Chưa đúng. Đáp án: mitigate', improvedVersion: null,
      }));

      const result = await client.answerQuiz({ quizItemId: 7, answer: 'mitigated' });

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE_URL}/api/quiz/answer`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ quizItemId: 7, answer: 'mitigated' }),
        }),
      );
      expect(result.feedback).toContain('mitigate');
      expect(result.improvedVersion).toBeNull();
    });

    it('explainQuiz POST /api/quiz/explain và KHÔNG gửi kèm câu trả lời', async () => {
      fetchMock.mockResolvedValue(jsonResponse({
        explanation: '"mitigate" đi với "impact".',
        answerMeaning: 'mitigate = giảm nhẹ',
        sentenceEn: 'Governments must mitigate the impact.',
        sentenceVi: 'Chính phủ phải giảm nhẹ tác động.',
      }));

      const result = await client.explainQuiz({ quizItemId: 7 });

      // Body đúng bằng { quizItemId }: thêm câu trả lời vào đây là mở đường vòng đọc đáp án.
      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE_URL}/api/quiz/explain`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ quizItemId: 7 }),
        }),
      );
      expect(result.sentenceVi).toBe('Chính phủ phải giảm nhẹ tác động.');
    });

    it('bài viết quá dài ném TEXT_TOO_LONG, không retry được', async () => {
      fetchMock.mockResolvedValue(jsonResponse(
        { code: 'TEXT_TOO_LONG', message: 'Bài viết quá dài (tối đa 1000 ký tự)', retryable: false },
        400));

      await expect(client.answerQuiz({ quizItemId: 7, answer: 'x'.repeat(1001) }))
        .rejects.toMatchObject({ code: 'TEXT_TOO_LONG', retryable: false });
    });
  });
});
