import { BUBBLE_CSS } from './bubble.css';
import type { BubbleSummary, ResolvedTheme } from '@ielts/core';

export const BUBBLE_HOST_ID = 'ielts-translator-bubble-host';

/** Chế độ màu của bubble. Bubble được dựng lại mỗi lần hiện, nên biến này là nơi duy nhất
 *  nhớ được lựa chọn giữa hai lần dựng. Mặc định sáng cho tới khi `content/index.ts` đọc
 *  xong cài đặt. */
let bubbleTheme: ResolvedTheme = 'light';

/** Đặt chế độ màu cho bubble. Cập nhật luôn bubble ĐANG hiện — người dùng đổi giao diện ở
 *  trang Options trong lúc một bubble còn trên màn hình thì nó phải đổi theo ngay, chứ
 *  không nằm sai màu tới lần dịch sau. */
export function setBubbleTheme(theme: ResolvedTheme): void {
  bubbleTheme = theme;
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (host) host.dataset.theme = theme;
}

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
  // Sách mở: hai trang và gáy ở giữa. Cố ý KHÔNG dùng glyph chữ tượng hình như các bộ
  // icon "translate" thông dụng — nét chữ Hán trong một app học tiếng Anh gây hiểu nhầm.
  translate:
    '<path d="M12 7v14"/>'
    + '<path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5'
    + 'a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3Z"/>',
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
  host.dataset.theme = bubbleTheme;
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

/**
 * Chip "+N từ hôm nay".
 *
 * Dùng chung cho bubble kết quả (đứng cạnh nút "Lưu vào sổ") và bubble báo đã lưu (mang
 * con số VỪA tăng) — hai chỗ phải là cùng một thứ trong mắt người dùng, nên cùng một hàm
 * dựng và cùng một class.
 */
function dailyChip(count: number): HTMLSpanElement {
  const chip = document.createElement('span');
  chip.className = 'daily';
  chip.textContent = `+${count} từ hôm nay`;
  return chip;
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

/**
 * Chỉ một icon, không chữ — trạng thái đầu tiên sau khi bôi đen. Dịch chỉ chạy khi
 * người dùng bấm vào đây, nên bôi đen để copy hay đọc lại không tốn lượt gọi nào.
 *
 * `mousedown` bị chặn vì trình duyệt collapse selection của trang khi nhấn chuột lên
 * một nút. Không chặn thì vệt bôi đen biến mất ngay lúc bấm, trông như thao tác hỏng.
 * (Dữ liệu để dịch đã được chụp từ trước nên không phụ thuộc vào selection còn hay mất
 * — chặn ở đây thuần tuý cho phần nhìn.)
 */
export function showIconBubble(rect: DOMRect, onTranslate: () => void): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'icon-only');

  const el = button('translate', 'Dịch đoạn đã chọn', onTranslate, ICONS.translate);
  el.addEventListener('mousedown', (event) => event.preventDefault());

  container.appendChild(el);
  root.appendChild(container);
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

/**
 * Bubble kết quả theo thiết kế 1b: khối chữ ở trên, thanh hành động nền xanh đặc ở dưới,
 * card không viền chỉ có bóng nổi.
 *
 * `summary.term` rỗng (kết quả dịch CÂU) thì bỏ hẳn dòng đầu — nhét cả câu vào ô dành cho
 * một từ là phá bố cục ở ca thường gặp nhất của chế độ đó.
 *
 * @param savedToday số từ đã lưu vào sổ trong ngày, cho chip "+N từ hôm nay". 0 = ẩn chip.
 */
export function showResultBubble(
  rect: DOMRect, summary: BubbleSummary, handlers: BubbleHandlers, savedToday = 0,
): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'result');

  const body = document.createElement('div');
  body.className = 'body';

  if (summary.term) {
    const head = document.createElement('div');
    head.className = 'head';

    const term = document.createElement('span');
    term.className = 'term';
    term.textContent = summary.term;
    head.appendChild(term);

    // Không có band thì KHÔNG vẽ chip: một ô màu rỗng chỉ là nhiễu.
    if (summary.band) {
      const band = document.createElement('span');
      band.className = 'band';
      band.title = 'Band do AI ước lượng, chỉ mang tính tham khảo';
      // Chữ "BAND" nằm trong nội dung chứ không phải `::before` của CSS: một con số 6.5
      // trơ trọi không nói được gì với trình đọc màn hình.
      band.textContent = `BAND ${summary.band}`;
      head.appendChild(band);
    }
    body.appendChild(head);
  }

  // `.text` giữ nguyên tên class của mọi trạng thái bubble khác (loading, lỗi, đã lưu) để
  // một chỗ khai báo màu chữ là đủ cho tất cả; `.meaning` mang phần bố cục của riêng dòng
  // này.
  //
  // `.vi` CHỈ thêm khi dòng đó thật sự là tiếng Việt: nó là class bật serif (Lora), mặt chữ
  // mà thiết kế 1a dành riêng cho tiếng Việt. Ca VI→EN chế độ CÂU trả về một câu tiếng Anh
  // và phải giữ mặt chữ sans.
  const meaning = textNode(summary.meaning);
  meaning.classList.add('meaning');
  if (summary.meaningLang === 'vi') meaning.classList.add('vi');
  body.appendChild(meaning);
  container.appendChild(body);

  // Thanh hành động nền xanh đặc chạy hết bề ngang đáy card. "Lưu vào sổ" là hành động
  // chính nên nó là CHỮ chiếm hết chỗ trống, không phải một trong ba icon giống nhau.
  const bar = document.createElement('div');
  bar.className = 'bar';
  bar.appendChild(button('save', 'Lưu vào sổ', handlers.onSave));

  // Chip chỉ hiện khi đã lưu được từ nào hôm nay — "+0 từ hôm nay" là một huy hiệu nói
  // rằng bạn chưa làm gì.
  if (savedToday > 0) bar.appendChild(dailyChip(savedToday));

  bar.appendChild(button('speak', 'Phát âm', handlers.onSpeak, ICONS.speak));
  // Không có trong khung 1b, nhưng đây là đường DUY NHẤT mở side panel kèm kết quả — bỏ đi
  // là mất tính năng, không phải gọn hơn.
  bar.appendChild(button('expand', 'Mở side panel', handlers.onExpand, ICONS.expand));
  container.appendChild(bar);

  root.appendChild(container);
}

/**
 * Bubble chỉ có một dòng thông báo, không nút — dùng sau khi lưu xong.
 *
 * @param savedToday số từ đã lưu trong ngày TÍNH CẢ lượt vừa rồi. Đây là lần vẽ DUY NHẤT
 *   mà người dùng thấy con số đã tăng: bubble kết quả bị thay hẳn bằng thông báo này, và
 *   chip trên đó đọc số từ trước lúc bấm Lưu. 0 = ẩn chip (ca "Đã có trong sổ" — không từ
 *   nào được thêm vào sổ nên không có gì vừa tăng).
 */
export function showNoticeBubble(rect: DOMRect, message: string, savedToday = 0): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'saved');
  container.appendChild(textNode(message));
  if (savedToday > 0) container.appendChild(dailyChip(savedToday));
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
