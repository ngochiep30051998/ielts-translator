import { validateSelection, extractContextSentence } from './selection';
import {
  showLoadingBubble, showResultBubble, showNoticeBubble, showErrorBubble, hideBubble, BUBBLE_HOST_ID,
} from './bubble';
import { sendToBackground } from '../shared/messages';
import { shortMeaning } from '../shared/summary';
import { loadSettings } from '../shared/settings';
import type { TranslateResult } from '../shared/types';

const DEBOUNCE_MS = 250;

let debounceTimer: number | undefined;
let currentResult: TranslateResult | null = null;

function selectionRect(): DOMRect | null {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  return selection.getRangeAt(0).getBoundingClientRect();
}

function containerTextOf(selection: Selection): string {
  const node = selection.anchorNode;
  const element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element | null);
  return element?.textContent ?? '';
}

function noopHandlers() {
  return { onSpeak: () => {}, onSave: () => {}, onExpand: () => {}, onRetry: () => {} };
}

function speak(text: string, voiceName: string | null): void {
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = speechSynthesis.getVoices()
    .find((v) => (voiceName ? v.name === voiceName : v.lang.startsWith('en')));
  if (voice) utterance.voice = voice;
  speechSynthesis.speak(utterance);
}

/** Đọc phần tiếng Anh: text gốc nếu EN→VI, bản dịch nếu VI→EN. */
function spokenTextOf(result: TranslateResult): string {
  return result.direction === 'EN_VI' ? result.sourceText : shortMeaning(result);
}

async function saveCurrent(rect: DOMRect): Promise<void> {
  if (!currentResult) return;
  const response = await sendToBackground({ type: 'SAVE_WORD', result: currentResult, tags: [] });
  if (!response.ok) {
    showErrorBubble(rect, response.error.message, response.error.retryable, noopHandlers());
    return;
  }
  showNoticeBubble(rect, response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ');
}

async function translateCurrentSelection(): Promise<void> {
  const selection = window.getSelection();
  const rect = selectionRect();
  if (!selection || !rect) return;

  const check = validateSelection(selection.toString());
  if (!check.ok) {
    if (check.reason === 'TOO_LONG') {
      showErrorBubble(rect, 'Đoạn bôi đen quá dài, hãy chọn ít chữ hơn.', false, noopHandlers());
    }
    return;
  }

  const settings = await loadSettings();
  showLoadingBubble(rect);

  const response = await sendToBackground({
    type: 'TRANSLATE_SELECTION',
    text: check.text,
    contextSentence: extractContextSentence(containerTextOf(selection), check.text),
    sourceUrl: location.href,
    pageTitle: document.title,
  });

  if (!response.ok) {
    showErrorBubble(rect, response.error.message, response.error.retryable, {
      ...noopHandlers(),
      onRetry: () => void translateCurrentSelection(),
    });
    return;
  }

  currentResult = response.data;
  showResultBubble(rect, shortMeaning(response.data), {
    onSpeak: () => speak(spokenTextOf(response.data), settings.voiceName),
    onSave: () => void saveCurrent(rect),
    onExpand: () => void sendToBackground({ type: 'OPEN_PANEL_WITH_RESULT', result: response.data }),
    onRetry: () => void translateCurrentSelection(),
  });
}

document.addEventListener('mouseup', () => {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(async () => {
    const settings = await loadSettings();
    if (settings.triggerMode !== 'auto') return;
    if ((window.getSelection()?.toString() ?? '').trim().length === 0) {
      hideBubble();
      return;
    }
    void translateCurrentSelection();
  }, DEBOUNCE_MS);
});

document.addEventListener('mousedown', (event) => {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (host && !event.composedPath().includes(host)) hideBubble();
});

chrome.runtime.onMessage.addListener((message: { type?: string }) => {
  if (message?.type === 'HOTKEY_TRANSLATE') void translateCurrentSelection();
});
