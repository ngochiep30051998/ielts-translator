import { ApiClient, createOperations, toApiError } from '@ielts/core';
import type {
  AuthFlowPort, CredentialsPort, ExtensionRequest, ExtensionResponse, LastResultStore,
  TranslateResult,
} from '@ielts/core';
import { refreshBadge } from './badge';
import { loadSettings } from '../shared/settings';
import { bumpDailySaves } from '../shared/daily-saves';
import { clearAuth, loadAuth, loadToken, saveAuth } from '../shared/auth-storage';

/**
 * Client id của OAuth client kiểu "Web application". CÔNG KHAI được — nó nằm trong URL mà
 * người dùng nhìn thấy. `client_secret` thì TUYỆT ĐỐI không: nó chỉ sống ở backend.
 */
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';

/**
 * Extension mang danh tính bằng header `Authorization`, KHÔNG bằng cookie.
 *
 * `credentials: 'omit'` là cố ý: nó gọi backend cross-origin từ `chrome-extension://`, và
 * CORS phía backend không bật `allow_credentials`. Đính cookie ở đây vừa không có tác dụng
 * vừa mở thêm một bề mặt phải nghĩ tới.
 */
const credentials: CredentialsPort = {
  async authHeaders() {
    const token = await loadToken();
    return token ? { Authorization: `Bearer ${token}` } : null;
  },
  credentials: 'omit',
  onUnauthorized: clearAuth,
};

const client = new ApiClient(async () => (await loadSettings()).backendUrl, credentials);

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
  return session.user;
}

const auth: AuthFlowPort = {
  signIn,
  signOut: clearAuth,
  /**
   * Đọc từ storage chứ không gọi /auth/me mỗi lần mở panel: panel mở rất thường xuyên, và
   * token chết sẽ tự lộ ra ở request nghiệp vụ đầu tiên qua 401.
   */
  async currentUser() {
    return (await loadAuth())?.user ?? null;
  },
};

/** Kết quả dịch gần nhất, để side panel đọc lại khi vừa mở. */
let lastResult: TranslateResult | null = null;

/**
 * Giữ trong bộ nhớ tiến trình, y như trước khi tách package.
 *
 * Web thì lưu vào `sessionStorage` vì F5 sẽ mất — extension không có vấn đề đó: side panel
 * và service worker là hai tài liệu khác nhau, panel đóng mở không giết worker.
 */
const lastResultStore: LastResultStore = {
  async get() {
    return lastResult;
  },
  async set(result) {
    lastResult = result;
  },
};

const handle = createOperations(client, {
  lastResult: lastResultStore,
  auth,
  onVocabChanged: () => refreshBadge(client),
  openPanel: (tabId) => chrome.sidePanel.open({ tabId }),
});

/**
 * Đếm số từ mới lưu trong ngày cho chip "+N từ hôm nay" trên bubble.
 *
 * Đặt ở service worker chứ không ở content script vì đây là chỗ DUY NHẤT mọi lượt lưu đi
 * qua — lưu từ bubble và lưu từ side panel phải cùng được đếm, nếu không chip nói một con
 * số nhỏ hơn sự thật.
 *
 * `alreadyExists` KHÔNG đếm: từ đó đã ở trong sổ từ trước rồi, người dùng không học thêm
 * được từ nào mới trong hôm nay.
 */
async function noteVocabSaved(request: ExtensionRequest, data: unknown): Promise<void> {
  if (request.type === 'SAVE_WORD') {
    const saved = data as { alreadyExists?: boolean } | null;
    if (saved?.alreadyExists) return;
    await bumpDailySaves();
    return;
  }

  // Một mẻ "Lưu N từ đáng học" thêm NHIỀU từ trong một message. Cộng theo `saved` — con số
  // đã trừ sẵn những từ `alreadyExists` và những từ lưu hỏng, nên nó đúng bằng số từ mới
  // thật sự vào sổ. Quên nhánh này thì chip đứng yên sau khi vừa lưu cả nắm từ.
  if (request.type === 'SAVE_KEY_VOCAB') {
    const batch = data as { saved?: number } | null;
    await bumpDailySaves(new Date(), batch?.saved ?? 0);
  }
}

chrome.runtime.onMessage.addListener((request: ExtensionRequest, sender, sendResponse) => {
  handle(request, sender.tab?.id)
    .then(async (data) => {
      // Đếm TRƯỚC khi trả lời: content script đọc lại con số ngay sau khi nhận phản hồi,
      // nên đếm sau là nó đọc phải giá trị cũ đúng một nhịp.
      await noteVocabSaved(request, data);
      sendResponse({ ok: true, data } satisfies ExtensionResponse<unknown>);
    })
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
