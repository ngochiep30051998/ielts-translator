import { ApiClient } from './api-client';
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
    case 'SAVE_WORD':
      return client.saveVocab(buildVocabPayload(request.result, request.tags));
    case 'SEARCH_VOCAB':
      return client.searchVocab({ query: request.query, tag: request.tag, page: request.page });
    case 'DELETE_VOCAB':
      return client.deleteVocab(request.id);
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
