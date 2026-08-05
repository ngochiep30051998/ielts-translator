import type { ApiError, PageResponse, SaveVocabResponse, TranslateResult, VocabEntryDto } from './types';

export interface TranslateSelectionRequest {
  type: 'TRANSLATE_SELECTION';
  text: string;
  contextSentence: string | null;
  sourceUrl: string;
  pageTitle: string;
}

export interface OpenPanelRequest {
  type: 'OPEN_PANEL_WITH_RESULT';
  result: TranslateResult;
}

export interface SaveWordRequest {
  type: 'SAVE_WORD';
  result: TranslateResult;
  tags: string[];
}

export interface SearchVocabRequest {
  type: 'SEARCH_VOCAB';
  query: string | null;
  tag: string | null;
  page: number;
}

export interface DeleteVocabRequest {
  type: 'DELETE_VOCAB';
  id: number;
}

export interface GetLastResultRequest {
  type: 'GET_LAST_RESULT';
}

export interface HealthRequest {
  type: 'CHECK_HEALTH';
}

export type ExtensionRequest =
  | TranslateSelectionRequest
  | OpenPanelRequest
  | SaveWordRequest
  | SearchVocabRequest
  | DeleteVocabRequest
  | GetLastResultRequest
  | HealthRequest;

export type ExtensionResponse<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export interface ResponseMap {
  TRANSLATE_SELECTION: TranslateResult;
  OPEN_PANEL_WITH_RESULT: null;
  SAVE_WORD: SaveVocabResponse;
  SEARCH_VOCAB: PageResponse<VocabEntryDto>;
  DELETE_VOCAB: null;
  GET_LAST_RESULT: TranslateResult | null;
  CHECK_HEALTH: { status: string; dbConnected: boolean; geminiConfigured: boolean };
}

function localError(code: string, message: string, retryable: boolean): { ok: false; error: ApiError } {
  return { ok: false, error: { code, message, retryable } };
}

/**
 * Gửi message tới service worker và nhận về kết quả đã phân biệt ok/lỗi.
 *
 * `chrome.runtime.sendMessage` REJECT khi không có bên nhận — xảy ra thật khi
 * service worker vừa reload/crash, hoặc content script bị mồ côi sau khi reload
 * extension. Nuốt lỗi đó ở đây để mọi caller chỉ phải xử lý một hình dạng kết
 * quả, thay vì mỗi chỗ tự bọc try/catch (và quên).
 */
export async function sendToBackground<R extends ExtensionRequest>(
  request: R,
): Promise<ExtensionResponse<ResponseMap[R['type']]>> {
  let response: unknown;
  try {
    response = await chrome.runtime.sendMessage(request);
  } catch {
    return localError(
      'BACKEND_DOWN',
      'Không liên lạc được với extension. Tải lại trang, hoặc bật lại extension trong chrome://extensions.',
      true,
    );
  }

  if (typeof response !== 'object' || response === null || !('ok' in response)) {
    return localError('INTERNAL', 'Service worker không phản hồi đúng định dạng.', false);
  }
  return response as ExtensionResponse<ResponseMap[R['type']]>;
}
