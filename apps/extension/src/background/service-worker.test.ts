import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ExtensionRequest, TranslatePayload, TranslateResult } from '@ielts/core';

/**
 * Test phần "glue" của service worker: định tuyến message xuống ApiClient, các điểm
 * refresh badge, và việc đăng ký alarm.
 *
 * ApiClient và badge bị mock hoàn toàn — ở đây chỉ quan tâm service worker gọi ĐÚNG
 * method với ĐÚNG tham số, còn hành vi của chúng đã có test riêng.
 */
const api = {
  translate: vi.fn(),
  saveVocab: vi.fn(),
  searchVocab: vi.fn(),
  deleteVocab: vi.fn(),
  vocabTags: vi.fn(),
  updateVocab: vi.fn(),
  getDueCards: vi.fn(),
  submitReview: vi.fn(),
  getPracticeCards: vi.fn(),
  submitPractice: vi.fn(),
  srsStats: vi.fn(),
  learningStats: vi.fn(),
  generateQuiz: vi.fn(),
  answerQuiz: vi.fn(),
  explainQuiz: vi.fn(),
  googleLogin: vi.fn(),
  logout: vi.fn(),
  health: vi.fn(),
};

// `importOriginal` chứ không thay cả module: service worker còn cần `createOperations`
// và `toApiError` thật từ core — mock trắng cả `@ielts/core` là mock luôn thứ đang test.
vi.mock('@ielts/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@ielts/core')>()),
  ApiClient: vi.fn(() => api),
}));
vi.mock('./badge', () => ({ refreshBadge: vi.fn() }));

const { refreshBadge } = await import('./badge');

const BADGE_ALARM = 'srs-badge';

const RESULT: TranslateResult = {
  direction: 'EN_VI',
  mode: 'WORD',
  cached: false,
  payload: { term: 'mitigate', meaning_vi: 'giảm nhẹ', pos: 'verb' } as unknown as TranslatePayload,
  sourceText: 'mitigate',
};

/** Import lại service worker để top-level code (đăng ký listener, alarm) chạy lại từ đầu. */
async function loadServiceWorker(): Promise<void> {
  vi.resetModules();
  await import('./service-worker');
}

function lastListener<T>(addListener: unknown): T {
  const calls = (addListener as { mock: { calls: unknown[][] } }).mock.calls;
  return calls[calls.length - 1][0] as T;
}

/** Gửi một message qua đúng listener service worker đã đăng ký, chờ sendResponse. */
async function send(request: ExtensionRequest): Promise<{ ok: boolean; data?: unknown }> {
  const handler = lastListener<
    (req: ExtensionRequest, sender: unknown, sendResponse: (r: unknown) => void) => boolean
  >(chrome.runtime.onMessage.addListener);

  return new Promise((resolve) => {
    handler(request, {}, resolve as (r: unknown) => void);
  });
}

function fireAlarm(name: string): void {
  lastListener<(alarm: { name: string }) => void>(chrome.alarms.onAlarm.addListener)({ name });
}

describe('service worker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // clearAllMocks giữ nguyên implementation, nên phải đặt lại mặc định "chưa có alarm".
    vi.mocked(chrome.alarms.get).mockResolvedValue(undefined as unknown as chrome.alarms.Alarm);
    api.saveVocab.mockResolvedValue({ id: 1, alreadyExists: false });
    api.deleteVocab.mockResolvedValue(null);
    api.vocabTags.mockResolvedValue({ total: 0, untagged: 0, tags: [] });
    api.updateVocab.mockResolvedValue({ id: 7, term: 'mitigate', meaningVi: 'giảm nhẹ' });
    api.getDueCards.mockResolvedValue([]);
    api.submitReview.mockResolvedValue({ nextDueDate: '2026-08-07', intervalDays: 1, easeFactor: 2.5 });
    api.srsStats.mockResolvedValue({ dueCount: 3, newCount: 1, learnedCount: 9 });
    api.generateQuiz.mockResolvedValue([]);
    api.answerQuiz.mockResolvedValue({
      correct: true, score: 100, feedback: 'Chính xác.', improvedVersion: null,
    });
    api.logout.mockResolvedValue(null);
    void chrome.storage.local.clear();
  });

  describe('đăng ký alarm cập nhật badge', () => {
    it('chưa có alarm thì tạo mới, chu kỳ 30 phút', async () => {
      await loadServiceWorker();

      await vi.waitFor(() => expect(chrome.alarms.create).toHaveBeenCalledWith(
        BADGE_ALARM, { periodInMinutes: 30 },
      ));
    });

    it('alarm đã tồn tại thì KHÔNG tạo lại — tạo lại là đặt đồng hồ về 0 mỗi lần worker thức dậy', async () => {
      vi.mocked(chrome.alarms.get).mockResolvedValue(
        { name: BADGE_ALARM, scheduledTime: Date.now(), periodInMinutes: 30 },
      );

      await loadServiceWorker();

      await vi.waitFor(() => expect(chrome.alarms.get).toHaveBeenCalledWith(BADGE_ALARM));
      expect(chrome.alarms.create).not.toHaveBeenCalled();
    });

    it('alarm đúng tên thì cập nhật badge', async () => {
      await loadServiceWorker();

      fireAlarm(BADGE_ALARM);

      expect(refreshBadge).toHaveBeenCalledTimes(1);
    });

    it('alarm tên khác thì bỏ qua', async () => {
      await loadServiceWorker();

      fireAlarm('alarm-của-tính-năng-khác');

      expect(refreshBadge).not.toHaveBeenCalled();
    });
  });

  describe('định tuyến message SRS', () => {
    it('GET_DUE_CARDS xuống getDueCards kèm limit và newLimit', async () => {
      await loadServiceWorker();

      const response = await send({ type: 'GET_DUE_CARDS', limit: 50, newLimit: 30 });

      expect(api.getDueCards).toHaveBeenCalledWith({ limit: 50, newLimit: 30 });
      expect(response.ok).toBe(true);
    });

    it('SUBMIT_REVIEW xuống submitReview kèm cardId và rating', async () => {
      await loadServiceWorker();

      const response = await send({ type: 'SUBMIT_REVIEW', cardId: 7, rating: 'GOOD' });

      expect(api.submitReview).toHaveBeenCalledWith({ cardId: 7, rating: 'GOOD' });
      expect(response).toMatchObject({ ok: true, data: { intervalDays: 1 } });
    });

    it('SUBMIT_PRACTICE gọi submitPractice và KHÔNG đụng badge', async () => {
      await loadServiceWorker();
      api.submitPractice.mockResolvedValue(null);

      const response = await send({ type: 'SUBMIT_PRACTICE', cardId: 7, rating: 'GOOD' });

      expect(api.submitPractice).toHaveBeenCalledWith({ cardId: 7, rating: 'GOOD' });
      expect(response).toEqual({ ok: true, data: null });
      // Luyện thêm KHÔNG đổi lịch, nên số thẻ đến hạn không thể đổi.
      expect(refreshBadge).not.toHaveBeenCalled();
    });

    it('GET_SRS_STATS xuống srsStats kèm newLimit', async () => {
      await loadServiceWorker();

      await send({ type: 'GET_SRS_STATS', newLimit: 30 });

      expect(api.srsStats).toHaveBeenCalledWith(30);
    });

    it('GET_STATS gọi learningStats và KHÔNG đụng badge', async () => {
      const STATS = {
        streak: { current: 1, longest: 1, lastActiveDate: '2026-08-11' },
        totals: { reviews: 1, learnedWords: 1, activeDays: 1 },
        daily: [],
        recall: { again: 0, hard: 0, good: 1, easy: 0 },
        quiz: [],
      };
      api.learningStats.mockResolvedValue(STATS);
      await loadServiceWorker();

      const response = await send({ type: 'GET_STATS' });

      expect(api.learningStats).toHaveBeenCalled();
      expect(response).toEqual({ ok: true, data: STATS });
      // Thống kê là màn CHỈ ĐỌC: số thẻ đến hạn không thể đổi vì một lượt xem biểu đồ.
      expect(refreshBadge).not.toHaveBeenCalled();
    });

    it('lỗi từ ApiClient trả về dạng { ok: false, error }', async () => {
      api.getDueCards.mockRejectedValue(
        { code: 'BACKEND_DOWN', message: 'Không kết nối được backend.', retryable: true });
      await loadServiceWorker();

      const response = await send({ type: 'GET_DUE_CARDS', limit: 50, newLimit: 30 });

      expect(response).toMatchObject({
        ok: false, error: { code: 'BACKEND_DOWN', retryable: true },
      });
    });
  });

  describe('định tuyến message sổ từ', () => {
    it('GET_VOCAB_TAGS xuống vocabTags, không tham số', async () => {
      // Trả về nguyên khối `{ total, untagged, tags }` — tổng KHÔNG lọc đi cùng danh sách
      // chủ đề trong đúng một lượt gọi, để hai nửa của hàng chip không lệch nhau.
      const info = { total: 128, untagged: 41, tags: [{ tag: 'Môi trường', count: 24 }] };
      api.vocabTags.mockResolvedValue(info);
      await loadServiceWorker();

      const response = await send({ type: 'GET_VOCAB_TAGS' });

      expect(api.vocabTags).toHaveBeenCalledWith();
      expect(response).toEqual({ ok: true, data: info });
    });

    it('UPDATE_VOCAB xuống updateVocab giữ nguyên null của field không đổi', async () => {
      // `null` phải đi tới tận ApiClient để nó bỏ field ra khỏi body. Đổi thành `[]` hay
      // chuỗi rỗng ở đây là im lặng gỡ sạch thẻ của người dùng.
      await loadServiceWorker();

      const response = await send({
        type: 'UPDATE_VOCAB', id: 7, meaningVi: 'giảm nhẹ', tags: null,
      });

      expect(api.updateVocab).toHaveBeenCalledWith({
        id: 7, meaningVi: 'giảm nhẹ', tags: null,
      });
      expect(response).toMatchObject({ ok: true, data: { id: 7 } });
    });

    it('UPDATE_VOCAB KHÔNG đụng badge — sửa nghĩa không thêm bớt thẻ ôn nào', async () => {
      await loadServiceWorker();

      await send({ type: 'UPDATE_VOCAB', id: 7, meaningVi: null, tags: ['Môi trường'] });

      expect(refreshBadge).not.toHaveBeenCalled();
    });
  });

  describe('định tuyến message dịch', () => {
    it('TRANSLATE_TEXT gọi translate không kèm ngữ cảnh và không kèm trang nguồn', async () => {
      api.translate.mockResolvedValue(RESULT);
      await loadServiceWorker();

      const response = await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });

      // sourceUrl/pageTitle rỗng chứ không phải null: api-client đổi chuỗi rỗng thành
      // undefined, và bản ghi vào sổ từ nhận sourceUrl null. Text gõ tay không có trang nguồn.
      expect(api.translate).toHaveBeenCalledWith({
        text: 'mitigate', contextSentence: null, sourceUrl: '', pageTitle: '',
      });
      expect(response).toMatchObject({ ok: true, data: { sourceText: 'mitigate' } });
    });

    it('TRANSLATE_TEXT cập nhật kết quả gần nhất mà GET_LAST_RESULT đọc', async () => {
      api.translate.mockResolvedValue(RESULT);
      await loadServiceWorker();

      await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });
      const response = await send({ type: 'GET_LAST_RESULT' });

      // Cùng một ô nhớ với đường bôi đen: side panel chỉ có MỘT vùng kết quả.
      expect(response).toMatchObject({ ok: true, data: { sourceText: 'mitigate' } });
    });

    it('lỗi khi dịch trả về dạng { ok: false, error }', async () => {
      api.translate.mockRejectedValue(
        { code: 'GEMINI_QUOTA', message: 'Hết quota Gemini hôm nay.', retryable: false });
      await loadServiceWorker();

      const response = await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });

      expect(response).toMatchObject({
        ok: false, error: { code: 'GEMINI_QUOTA', retryable: false },
      });
    });
  });

  describe('định tuyến message Quiz', () => {
    it('GENERATE_QUIZ đổi tên quizType của message thành type của HTTP body', async () => {
      await loadServiceWorker();

      const response = await send({
        type: 'GENERATE_QUIZ', vocabIds: null, count: 4, quizType: 'FILL_BLANK',
      });

      // `type` trong message là trường phân biệt của union, không phải loại quiz —
      // đây là chỗ ánh xạ duy nhất giữa hai tên.
      expect(api.generateQuiz).toHaveBeenCalledWith({
        vocabIds: null, count: 4, type: 'FILL_BLANK',
      });
      expect(response.ok).toBe(true);
    });

    it('GENERATE_QUIZ theo vocabIds giữ nguyên count null', async () => {
      await loadServiceWorker();

      await send({
        type: 'GENERATE_QUIZ', vocabIds: [3, 9], count: null, quizType: 'FREE_WRITE',
      });

      expect(api.generateQuiz).toHaveBeenCalledWith({
        vocabIds: [3, 9], count: null, type: 'FREE_WRITE',
      });
    });

    it('ANSWER_QUIZ xuống answerQuiz kèm quizItemId và answer', async () => {
      await loadServiceWorker();

      const response = await send({ type: 'ANSWER_QUIZ', quizItemId: 12, answer: '2' });

      expect(api.answerQuiz).toHaveBeenCalledWith({ quizItemId: 12, answer: '2' });
      expect(response).toMatchObject({ ok: true, data: { correct: true, score: 100 } });
    });

    it('EXPLAIN_QUIZ xuống explainQuiz kèm ĐÚNG quizItemId và không gì khác', async () => {
      api.explainQuiz.mockResolvedValue({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      });
      await loadServiceWorker();

      const response = await send({ type: 'EXPLAIN_QUIZ', quizItemId: 12 });

      expect(api.explainQuiz).toHaveBeenCalledWith({ quizItemId: 12 });
      expect(response).toMatchObject({ ok: true, data: { explanation: 'x' } });
    });
  });

  describe('các điểm làm badge đổi số', () => {
    it('lưu từ mới thì cập nhật badge — từ mới là thêm một thẻ vào hàng đợi', async () => {
      await loadServiceWorker();

      await send({ type: 'SAVE_WORD', result: RESULT, tags: [] });

      expect(refreshBadge).toHaveBeenCalledTimes(1);
    });

    it('chấm xong một thẻ thì cập nhật badge', async () => {
      await loadServiceWorker();

      await send({ type: 'SUBMIT_REVIEW', cardId: 7, rating: 'GOOD' });

      expect(refreshBadge).toHaveBeenCalledTimes(1);
    });

    it('xoá từ khỏi sổ thì cập nhật badge — thẻ biến mất theo, giữ số cũ là nói dối', async () => {
      await loadServiceWorker();

      await send({ type: 'DELETE_VOCAB', id: 42 });

      expect(api.deleteVocab).toHaveBeenCalledWith(42);
      expect(refreshBadge).toHaveBeenCalledTimes(1);
    });

    it('nộp bài quiz KHÔNG đụng tới badge — quiz không chạm lịch SRS', async () => {
      await loadServiceWorker();

      await send({ type: 'ANSWER_QUIZ', quizItemId: 12, answer: '2' });

      expect(refreshBadge).not.toHaveBeenCalled();
    });

    it('xin giải thích KHÔNG đụng tới badge — quiz không chạm lịch SRS', async () => {
      api.explainQuiz.mockResolvedValue({
        explanation: 'x', answerMeaning: 'y', sentenceEn: null, sentenceVi: null,
      });
      await loadServiceWorker();

      await send({ type: 'EXPLAIN_QUIZ', quizItemId: 12 });

      expect(refreshBadge).not.toHaveBeenCalled();
    });

    it('tra từ thường không đụng tới badge', async () => {
      api.searchVocab.mockResolvedValue({ content: [], totalElements: 0, totalPages: 0, number: 0 });
      await loadServiceWorker();

      await send({ type: 'SEARCH_VOCAB', query: 'renew', tag: null, untagged: false, page: 0 });

      expect(refreshBadge).not.toHaveBeenCalled();
    });
  });

  /* ================= Đăng nhập Google ================= */

  describe('đăng nhập', () => {
    const USER = { email: 'a@b.com', displayName: 'A', pictureUrl: null };
    const REDIRECT = 'https://testextensionid.chromiumapp.org/';

    function redirectWith(params: Record<string, string>): string {
      const url = new URL(REDIRECT);
      for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
      return url.toString();
    }

    /** Lấy `state` mà service worker vừa sinh ra, để dựng redirect hợp lệ. */
    function stateFromLastFlow(): string {
      const call = vi.mocked(chrome.identity.launchWebAuthFlow).mock.calls.at(-1);
      const url = new URL((call![0] as { url: string }).url);
      return url.searchParams.get('state')!;
    }

    it('SIGN_IN mở launchWebAuthFlow rồi đổi code ở BACKEND', async () => {
      vi.mocked(chrome.identity.launchWebAuthFlow).mockImplementation(async () =>
        redirectWith({ code: 'abc', state: pendingState() }));
      api.googleLogin.mockResolvedValue({ token: 't', expiresAt: 'x', user: USER });
      await loadServiceWorker();

      const response = await send({ type: 'SIGN_IN' });

      // code đi qua backend chứ không đổi ở extension: client_secret không bao giờ rời server.
      expect(api.googleLogin).toHaveBeenCalledWith({ code: 'abc', redirectUri: REDIRECT });
      expect(response).toMatchObject({ ok: true, data: { email: 'a@b.com' } });
    });

    /** launchWebAuthFlow được gọi TRƯỚC khi ta đọc state, nên phải lấy nó ngay trong mock. */
    function pendingState(): string {
      return stateFromLastFlow();
    }

    it('state trả về khác state gửi đi → từ chối và KHÔNG đổi code', async () => {
      vi.mocked(chrome.identity.launchWebAuthFlow).mockResolvedValue(
        redirectWith({ code: 'abc', state: 'state-gia' }));
      await loadServiceWorker();

      const response = await send({ type: 'SIGN_IN' });

      // state là thứ duy nhất phân biệt "Google vừa trả lời mình" với một redirect bị nhét
      // vào. Sinh ra mà không đối chiếu thì thà đừng sinh.
      expect(api.googleLogin).not.toHaveBeenCalled();
      expect(response).toMatchObject({ ok: false });
    });

    it('người dùng đóng cửa sổ → lỗi ĐÚNG hình dạng, không ném thô', async () => {
      vi.mocked(chrome.identity.launchWebAuthFlow).mockRejectedValue(
        new Error('The user did not approve access.'));
      await loadServiceWorker();

      const response = await send({ type: 'SIGN_IN' });

      expect(response).toMatchObject({
        ok: false, error: { code: 'UNAUTHORIZED', retryable: false },
      });
    });

    it('redirect mang ?error=access_denied → thông điệp riêng', async () => {
      vi.mocked(chrome.identity.launchWebAuthFlow).mockResolvedValue(
        redirectWith({ error: 'access_denied' }));
      await loadServiceWorker();

      const response = await send({ type: 'SIGN_IN' }) as { error?: { message: string } };

      expect(response.error?.message).toContain('từ chối cấp quyền');
    });

    it('SIGN_OUT xoá token DÙ backend lỗi', async () => {
      api.logout.mockRejectedValue({ code: 'BACKEND_DOWN', message: 'x', retryable: true });
      await chrome.storage.local.set({ authToken: 't', authUser: USER });
      await loadServiceWorker();

      await send({ type: 'SIGN_OUT' });

      // Giữ token khi server không phản hồi sẽ kẹt người dùng ở trạng thái "đã bấm đăng
      // xuất nhưng vẫn đang đăng nhập" — trên máy mượn thì đó đúng là điều họ vừa cố tránh.
      const left = await chrome.storage.local.get(['authToken']);
      expect(left.authToken).toBeUndefined();
    });

    it('GET_AUTH_STATE chưa đăng nhập trả data: null, KHÔNG phải ok: false', async () => {
      await chrome.storage.local.clear();
      await loadServiceWorker();

      const response = await send({ type: 'GET_AUTH_STATE' });

      // Chưa đăng nhập không phải lỗi. Trả ok:false ở đây làm panel hiện "backend chết".
      expect(response).toEqual({ ok: true, data: null });
    });

    it('GET_AUTH_STATE đọc từ storage, KHÔNG gọi backend mỗi lần mở panel', async () => {
      await chrome.storage.local.set({ authToken: 't', authUser: USER });
      await loadServiceWorker();

      const response = await send({ type: 'GET_AUTH_STATE' });

      expect(response).toMatchObject({ ok: true, data: { email: 'a@b.com' } });
      expect(api.health).not.toHaveBeenCalled();
    });
  });
});
