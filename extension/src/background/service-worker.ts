import { ApiClient } from './api-client';
import { refreshBadge } from './badge';
import { loadSettings } from '../shared/settings';
import type { ExtensionRequest, ExtensionResponse } from '../shared/messages';
import type { ApiError, TranslateResult } from '../shared/types';

const client = new ApiClient(async () => (await loadSettings()).backendUrl);

/** Kết quả dịch gần nhất, để side panel đọc lại khi vừa mở. */
let lastResult: TranslateResult | null = null;

function toApiError(error: unknown): ApiError {
  if (error && typeof error === 'object' && 'code' in error) {
    return error as ApiError;
  }
  return { code: 'INTERNAL', message: 'Lỗi không xác định trong extension', retryable: false };
}

/** Chuyển kết quả dịch thành body cho POST /api/vocab. */
function buildVocabPayload(result: TranslateResult, tags: string[]) {
  const payload = result.payload as unknown as Record<string, unknown>;
  const isEnVi = result.direction === 'EN_VI';
  const isWord = result.mode === 'WORD';

  const term = isEnVi
    ? (payload.term as string) ?? result.sourceText
    : (payload.best_en as string) ?? (payload.band65_version as string) ?? '';
  const meaningVi = isEnVi
    ? (payload.meaning_vi as string) ?? (payload.translation_vi as string) ?? ''
    : result.sourceText;

  return {
    term,
    lemma: (payload.lemma as string) ?? term,
    lang: 'en',
    pos: isWord ? ((payload.pos as string) ?? '') : 'phrase',
    ipa: (payload.ipa as string) ?? null,
    meaningVi,
    definitionEn: (payload.definition_en as string) ?? null,
    cefr: (payload.cefr as string) ?? null,
    bandLevel: (payload.band_level as string) ?? null,
    tags,
    sourceUrl: result.sourceUrl ?? null,
    sourceSentence: result.sourceSentence ?? null,
    collocations: payload.collocations ?? [],
    examples: payload.examples ?? [],
  };
}

async function handle(request: ExtensionRequest, senderTabId?: number): Promise<unknown> {
  switch (request.type) {
    case 'TRANSLATE_SELECTION': {
      const result = await client.translate({
        text: request.text,
        contextSentence: request.contextSentence,
        sourceUrl: request.sourceUrl,
        pageTitle: request.pageTitle,
      });
      lastResult = result;
      return result;
    }
    case 'OPEN_PANEL_WITH_RESULT': {
      lastResult = request.result;
      if (senderTabId !== undefined) {
        await chrome.sidePanel.open({ tabId: senderTabId });
      }
      return null;
    }
    case 'GET_LAST_RESULT':
      return lastResult;
    case 'SAVE_WORD': {
      // Từ mới vào sổ = thêm một thẻ vào hàng đợi ôn, nên badge phải đổi ngay.
      const result = await client.saveVocab(buildVocabPayload(request.result, request.tags));
      void refreshBadge(client);
      return result;
    }
    case 'SEARCH_VOCAB':
      return client.searchVocab({ query: request.query, tag: request.tag, page: request.page });
    case 'DELETE_VOCAB': {
      // Xoá từ là xoá luôn thẻ của nó (ON DELETE CASCADE) — badge phải bỏ số cũ đi.
      const result = await client.deleteVocab(request.id);
      void refreshBadge(client);
      return result;
    }
    case 'GET_DUE_CARDS':
      return client.getDueCards({ limit: request.limit, newLimit: request.newLimit });
    case 'SUBMIT_REVIEW': {
      const result = await client.submitReview({ cardId: request.cardId, rating: request.rating });
      void refreshBadge(client);
      return result;
    }
    case 'GET_SRS_STATS':
      return client.srsStats(request.newLimit);
    case 'GENERATE_QUIZ':
      return client.generateQuiz({
        vocabIds: request.vocabIds,
        count: request.count,
        type: request.quizType,   // quizType (message) -> type (HTTP body)
      });
    case 'ANSWER_QUIZ':
      // KHÔNG gọi refreshBadge ở đây: quiz không chạm lịch SRS, nên số thẻ đến hạn
      // không thể đổi vì một lượt nộp bài.
      return client.answerQuiz({ quizItemId: request.quizItemId, answer: request.answer });
    case 'CHECK_HEALTH':
      return client.health();
  }
}

chrome.runtime.onMessage.addListener((request: ExtensionRequest, sender, sendResponse) => {
  handle(request, sender.tab?.id)
    .then((data) => sendResponse({ ok: true, data } satisfies ExtensionResponse<unknown>))
    .catch((error) => sendResponse({ ok: false, error: toApiError(error) } satisfies ExtensionResponse<never>));
  return true;   // giữ kênh mở cho phản hồi bất đồng bộ
});

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
  /* Chrome cũ không hỗ trợ — bỏ qua, người dùng vẫn mở panel từ bubble được */
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== 'translate-selection') return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id !== undefined) {
    chrome.tabs.sendMessage(tab.id, { type: 'HOTKEY_TRANSLATE' });
  }
});

/* ---------- Badge số thẻ đến hạn ---------- */

const BADGE_ALARM = 'srs-badge';
const BADGE_REFRESH_MINUTES = 30;

// Alarm chứ không phải setInterval: service worker MV3 bị ngủ bất cứ lúc nào,
// timer trong bộ nhớ chết theo còn alarm thì đánh thức worker dậy.
//
// Phải hỏi `get` trước khi `create`: file này chạy lại MỖI lần worker thức dậy, mà
// `create` trùng tên sẽ xoá alarm cũ và đếm lại từ đầu 30 phút. Người dùng tra từ
// đều đặn hơn 30 phút một lần thì alarm bị reset liên tục và không bao giờ nổ.
void chrome.alarms.get(BADGE_ALARM).then((existing) => {
  if (!existing) {
    chrome.alarms.create(BADGE_ALARM, { periodInMinutes: BADGE_REFRESH_MINUTES });
  }
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === BADGE_ALARM) void refreshBadge(client);
});

chrome.runtime.onStartup.addListener(() => void refreshBadge(client));
chrome.runtime.onInstalled.addListener(() => void refreshBadge(client));
