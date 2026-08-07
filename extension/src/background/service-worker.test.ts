import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ExtensionRequest } from '../shared/messages';
import type { TranslatePayload, TranslateResult } from '../shared/types';

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
  getDueCards: vi.fn(),
  submitReview: vi.fn(),
  srsStats: vi.fn(),
  generateQuiz: vi.fn(),
  answerQuiz: vi.fn(),
  health: vi.fn(),
};

vi.mock('./api-client', () => ({ ApiClient: vi.fn(() => api) }));
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
    api.getDueCards.mockResolvedValue([]);
    api.submitReview.mockResolvedValue({ nextDueDate: '2026-08-07', intervalDays: 1, easeFactor: 2.5 });
    api.srsStats.mockResolvedValue({ dueCount: 3, newCount: 1, learnedCount: 9 });
    api.generateQuiz.mockResolvedValue([]);
    api.answerQuiz.mockResolvedValue({
      correct: true, score: 100, feedback: 'Chính xác.', improvedVersion: null,
    });
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

    it('GET_SRS_STATS xuống srsStats kèm newLimit', async () => {
      await loadServiceWorker();

      await send({ type: 'GET_SRS_STATS', newLimit: 30 });

      expect(api.srsStats).toHaveBeenCalledWith(30);
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

    it('tra từ thường không đụng tới badge', async () => {
      api.searchVocab.mockResolvedValue({ content: [], totalElements: 0, totalPages: 0, number: 0 });
      await loadServiceWorker();

      await send({ type: 'SEARCH_VOCAB', query: 'renew', tag: null, page: 0 });

      expect(refreshBadge).not.toHaveBeenCalled();
    });
  });
});
