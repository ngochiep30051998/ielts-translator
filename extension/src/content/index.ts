import { extractContextSentence } from './selection';
import { validateSelection } from '../shared/text';
import {
  showLoadingBubble, showResultBubble, showNoticeBubble, showErrorBubble, showIconBubble,
  hideBubble, BUBBLE_HOST_ID,
} from './bubble';
import { sendToBackground } from '../shared/messages';
import { shortMeaning } from '../shared/summary';
import { loadSettings } from '../shared/settings';
import { speak } from '../shared/speech';
import type { TranslateResult } from '../shared/types';

const DEBOUNCE_MS = 250;

/**
 * Đoạn cần dịch, chụp lại NGAY lúc selection còn sống.
 *
 * Vì sao không đọc `window.getSelection()` lúc bấm nút: trình duyệt collapse selection
 * khi `mousedown` lên một nút, nên tới lượt `click` thì nó đã rỗng. Chụp trước là cách
 * duy nhất để icon (và nút Thử lại) luôn dịch đúng đoạn người dùng đã chọn.
 */
interface SelectionSnapshot {
  text: string;
  contextSentence: string | null;
  rect: DOMRect;
}

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

/**
 * Chụp selection hiện tại nếu nó hợp lệ. Trả `null` khi không có gì để dịch.
 *
 * Validate ở đây chứ không đợi tới lúc bấm: hiện icon rồi mới báo "đoạn quá dài" là bắt
 * người dùng bấm một lần vô ích.
 */
function captureSelection(): SelectionSnapshot | null {
  const selection = window.getSelection();
  const rect = selectionRect();
  if (!selection || !rect) return null;

  const check = validateSelection(selection.toString());
  if (!check.ok) {
    if (check.reason === 'TOO_LONG') {
      showErrorBubble(rect, 'Đoạn bôi đen quá dài, hãy chọn ít chữ hơn.', false, noopHandlers());
    }
    return null;
  }

  return {
    text: check.text,
    contextSentence: extractContextSentence(containerTextOf(selection), check.text),
    rect,
  };
}

async function translateSnapshot(shot: SelectionSnapshot): Promise<void> {
  const settings = await loadSettings();
  showLoadingBubble(shot.rect);

  const response = await sendToBackground({
    type: 'TRANSLATE_SELECTION',
    text: shot.text,
    contextSentence: shot.contextSentence,
    sourceUrl: location.href,
    pageTitle: document.title,
  });

  if (!response.ok) {
    showErrorBubble(shot.rect, response.error.message, response.error.retryable, {
      ...noopHandlers(),
      // Dùng lại ảnh chụp: đọc lại selection ở đây thì sau khi người dùng bấm đi chỗ
      // khác, "Thử lại" sẽ im lặng không làm gì.
      onRetry: () => void translateSnapshot(shot),
    });
    return;
  }

  currentResult = response.data;
  showResultBubble(shot.rect, shortMeaning(response.data), {
    onSpeak: () => speak(spokenTextOf(response.data), settings.voiceName),
    onSave: () => void saveCurrent(shot.rect),
    onExpand: () => void sendToBackground({ type: 'OPEN_PANEL_WITH_RESULT', result: response.data }),
    onRetry: () => void translateSnapshot(shot),
  });
}

/** Đường của phím tắt: bấm Alt+T đã là ý định rõ ràng nên dịch thẳng, không qua icon. */
async function translateCurrentSelection(): Promise<void> {
  const shot = captureSelection();
  if (!shot) return;
  await translateSnapshot(shot);
}

document.addEventListener('mouseup', (event) => {
  // Thao tác BÊN TRONG bubble không phải là một lượt chọn chữ mới.
  //
  // Không có nhánh này thì cú bấm icon tự bắn `mouseup` lên document, khởi động lại
  // debounce, và 250ms sau vẽ đè icon lên chính kết quả vừa dịch xong. Lỗi chỉ lộ ở
  // đường cache (trả về trước 250ms); đường Gemini che mất vì kết quả về sau mốc đó
  // nên nó đè ngược lại icon. Cũng chính nhánh này chặn việc bấm "Lưu vào sổ" kích
  // hoạt một lượt dịch lại đè lên thông báo vừa lưu.
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (host && event.composedPath().includes(host)) return;

  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(async () => {
    const settings = await loadSettings();
    if (settings.triggerMode !== 'auto') return;
    if ((window.getSelection()?.toString() ?? '').trim().length === 0) {
      hideBubble();
      return;
    }

    const shot = captureSelection();
    if (!shot) return;          // quá dài: captureSelection đã hiện bubble lỗi
    showIconBubble(shot.rect, () => void translateSnapshot(shot));
  }, DEBOUNCE_MS);
});

document.addEventListener('mousedown', (event) => {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (host && !event.composedPath().includes(host)) hideBubble();
});

chrome.runtime.onMessage.addListener((message: { type?: string }) => {
  if (message?.type === 'HOTKEY_TRANSLATE') void translateCurrentSelection();
});
