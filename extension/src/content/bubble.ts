import { BUBBLE_CSS } from './bubble.css';

export const BUBBLE_HOST_ID = 'ielts-translator-bubble-host';

export interface BubbleHandlers {
  onSpeak(): void;
  onSave(): void;
  onExpand(): void;
  onRetry(): void;
}

/** Icon 24x24 stroke-based, vẽ bằng SVG để không phụ thuộc font emoji của máy. */
const ICONS = {
  speak: '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>',
  save: '<path d="M12 5v14M5 12h14"/>',
  expand: '<path d="M15 3h6v6M21 3l-7 7M9 21H3v-6M3 21l7-7"/>',
};

function icon(path: string): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '15');
  svg.setAttribute('height', '15');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.innerHTML = path;
  return svg;
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

function textNode(content: string): HTMLSpanElement {
  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = content;
  return text;
}

function separator(): HTMLSpanElement {
  const sep = document.createElement('span');
  sep.className = 'sep';
  return sep;
}

function button(
  action: string, title: string, onClick: () => void, glyph?: string,
): HTMLButtonElement {
  const el = document.createElement('button');
  el.dataset.action = action;
  el.title = title;
  el.setAttribute('aria-label', title);
  if (glyph) {
    el.appendChild(icon(glyph));
  } else {
    el.textContent = title;
  }
  el.addEventListener('click', (event) => {
    event.stopPropagation();
    onClick();
  });
  return el;
}

export function showLoadingBubble(rect: DOMRect): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'loading');

  const dots = document.createElement('span');
  dots.className = 'dots';
  for (let i = 0; i < 3; i++) dots.appendChild(document.createElement('i'));

  container.appendChild(dots);
  container.appendChild(textNode('Đang dịch…'));
  root.appendChild(container);
}

export function showResultBubble(rect: DOMRect, meaning: string, handlers: BubbleHandlers): void {
  const root = mountShadow();
  const container = positionedContainer(rect);

  container.appendChild(textNode(meaning));
  container.appendChild(separator());
  container.appendChild(button('speak', 'Phát âm', handlers.onSpeak, ICONS.speak));
  container.appendChild(button('save', 'Lưu vào sổ từ', handlers.onSave, ICONS.save));
  container.appendChild(button('expand', 'Mở side panel', handlers.onExpand, ICONS.expand));

  root.appendChild(container);
}

/** Bubble chỉ có một dòng thông báo, không nút — dùng sau khi lưu xong. */
export function showNoticeBubble(rect: DOMRect, message: string): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'saved');
  container.appendChild(textNode(message));
  root.appendChild(container);
}

export function showErrorBubble(
  rect: DOMRect, message: string, retryable: boolean, handlers: BubbleHandlers,
): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'error');

  container.appendChild(textNode(message));

  if (retryable) {
    container.appendChild(separator());
    container.appendChild(button('retry', 'Thử lại', handlers.onRetry));
  }
  root.appendChild(container);
}

export function hideBubble(): void {
  document.getElementById(BUBBLE_HOST_ID)?.remove();
}
