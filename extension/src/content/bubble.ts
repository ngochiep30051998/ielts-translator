import { BUBBLE_CSS } from './bubble.css';

export const BUBBLE_HOST_ID = 'ielts-translator-bubble-host';

export interface BubbleHandlers {
  onSpeak(): void;
  onSave(): void;
  onExpand(): void;
  onRetry(): void;
}

function mountShadow(): ShadowRoot {
  hideBubble();
  const host = document.createElement('div');
  host.id = BUBBLE_HOST_ID;
  document.body.appendChild(host);

  const root = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = BUBBLE_CSS;
  root.appendChild(style);
  return root;
}

function positionedContainer(rect: DOMRect, extraClass = ''): HTMLDivElement {
  const container = document.createElement('div');
  container.className = `bubble ${extraClass}`.trim();
  container.style.left = `${Math.max(8, rect.left)}px`;
  container.style.top = `${rect.bottom + 8}px`;
  return container;
}

function button(label: string, action: string, title: string, onClick: () => void): HTMLButtonElement {
  const el = document.createElement('button');
  el.textContent = label;
  el.dataset.action = action;
  el.title = title;
  el.addEventListener('click', (event) => {
    event.stopPropagation();
    onClick();
  });
  return el;
}

export function showLoadingBubble(rect: DOMRect): void {
  const root = mountShadow();
  const container = positionedContainer(rect);
  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = 'Đang dịch…';
  container.appendChild(text);
  root.appendChild(container);
}

export function showResultBubble(rect: DOMRect, meaning: string, handlers: BubbleHandlers): void {
  const root = mountShadow();
  const container = positionedContainer(rect);

  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = meaning;
  container.appendChild(text);

  container.appendChild(button('🔊', 'speak', 'Phát âm', handlers.onSpeak));
  container.appendChild(button('+', 'save', 'Lưu vào sổ từ', handlers.onSave));
  container.appendChild(button('⤢', 'expand', 'Mở side panel', handlers.onExpand));

  root.appendChild(container);
}

export function showErrorBubble(
  rect: DOMRect, message: string, retryable: boolean, handlers: BubbleHandlers,
): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'error');

  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = message;
  container.appendChild(text);

  if (retryable) {
    container.appendChild(button('Thử lại', 'retry', 'Gọi lại backend', handlers.onRetry));
  }
  root.appendChild(container);
}

export function hideBubble(): void {
  document.getElementById(BUBBLE_HOST_ID)?.remove();
}
