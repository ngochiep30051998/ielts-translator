import { ApiClient } from './api-client';
import { refreshBadge } from './badge';
import { loadSettings } from '../shared/settings';
import { clearAuth, loadAuth, saveAuth } from '../shared/auth-storage';
import type { ExtensionRequest, ExtensionResponse } from '../shared/messages';
import type { ApiError, TranslateResult } from '../shared/types';

const client = new ApiClient(async () => (await loadSettings()).backendUrl);

/**
 * Client id của OAuth client kiểu "Web application". CÔNG KHAI được — nó nằm trong URL mà
 * người dùng nhìn thấy. `client_secret` thì TUYỆT ĐỐI không: nó chỉ sống ở backend.
 */
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';

/**
 * Mở luồng OAuth và đổi code lấy phiên.
 *
 * `chrome.identity` chỉ dùng được ở service worker, nên toàn bộ luồng nằm ở đây và panel
 * chỉ gửi message SIGN_IN.
 */
async function signIn() {
  const redirectUri = chrome.identity.getRedirectURL();
  const state = crypto.randomUUID();

  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', 'openid email profile');
  url.searchParams.set('redirect_uri', redirectUri);
  url.searchParams.set('state', state);
  url.searchParams.set('nonce', crypto.randomUUID());
  // Thiếu select_account thì Chrome im lặng dùng lại tài khoản Google lần trước — người có
  // hai tài khoản không đổi được mà cũng không hiểu vì sao.
  url.searchParams.set('prompt', 'select_account');

  let redirect: string | undefined;
  try {
    redirect = await chrome.identity.launchWebAuthFlow({ url: url.toString(), interactive: true });
  } catch {
    // Người dùng đóng cửa sổ là ca thường gặp nhất, không phải sự cố.
    throw { code: 'UNAUTHORIZED', message: 'Đã huỷ đăng nhập.', retryable: false };
  }
  if (!redirect) {
    throw { code: 'UNAUTHORIZED', message: 'Đã huỷ đăng nhập.', retryable: false };
  }

  const params = new URL(redirect).searchParams;
  if (params.get('error')) {
    throw {
      code: 'UNAUTHORIZED',
      message: params.get('error') === 'access_denied'
        ? 'Bạn đã từ chối cấp quyền cho extension.'
        : `Google từ chối đăng nhập (${params.get('error')}).`,
      retryable: false,
    };
  }
  // state là thứ DUY NHẤT phân biệt "Google vừa trả lời mình" với một redirect bị nhét vào.
  // Sinh ra mà không đối chiếu thì thà đừng sinh.
  if (params.get('state') !== state) {
    throw { code: 'UNAUTHORIZED', message: 'Phản hồi đăng nhập không khớp.', retryable: false };
  }
  const code = params.get('code');
  if (!code) {
    throw { code: 'UNAUTHORIZED', message: 'Google không trả mã đăng nhập.', retryable: false };
  }

  const session = await client.googleLogin({ code, redirectUri });
  await saveAuth(session.token, session.user);
  await refreshBadge(client);
  return session.user;
}

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
    case 'TRANSLATE_TEXT': {
      // Chuỗi rỗng chứ không phải null cho sourceUrl/pageTitle: api-client đã có sẵn
      // `args.sourceUrl || undefined`, nên rỗng tự biến thành "không có nguồn".
      const result = await client.translate({
        text: request.text,
        contextSentence: null,
        sourceUrl: '',
        pageTitle: '',
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
    case 'GET_STATS':
      // KHÔNG gọi refreshBadge: đây là màn chỉ đọc, số thẻ đến hạn không thể đổi vì
      // một lượt xem biểu đồ.
      return client.learningStats();
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
    case 'EXPLAIN_QUIZ':
      // Cũng như ANSWER_QUIZ: không refreshBadge. Quiz không chạm lịch SRS nên số thẻ đến
      // hạn không thể đổi vì một lượt xin giải thích.
      return client.explainQuiz({ quizItemId: request.quizItemId });
    case 'SIGN_IN':
      return signIn();
    case 'SIGN_OUT':
      // Xoá token phía client DÙ backend lỗi. Giữ lại vì server không phản hồi sẽ kẹt người
      // dùng ở trạng thái "đã bấm đăng xuất nhưng vẫn đang đăng nhập" — và trên máy mượn
      // thì đó đúng là điều họ vừa cố tránh.
      try {
        await client.logout();
      } finally {
        await clearAuth();
        await refreshBadge(client);
      }
      return null;
    case 'GET_AUTH_STATE': {
      // Đọc từ storage chứ không gọi /auth/me mỗi lần mở panel: panel mở rất thường xuyên,
      // và token chết sẽ tự lộ ra ở request nghiệp vụ đầu tiên qua 401.
      const stored = await loadAuth();
      return stored?.user ?? null;
    }
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
