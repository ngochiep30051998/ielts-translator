import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  showLoadingBubble, showResultBubble, showErrorBubble, showIconBubble, hideBubble,
  setBubbleTheme, BUBBLE_HOST_ID,
} from './bubble';
import type { BubbleSummary } from '@ielts/core';

const rect = { left: 100, top: 200, bottom: 220, width: 80, height: 20 } as DOMRect;

function shadow(): ShadowRoot {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (!host?.shadowRoot) throw new Error('Chưa có bubble trong DOM');
  return host.shadowRoot;
}

function handlers() {
  return { onSpeak: vi.fn(), onSave: vi.fn(), onExpand: vi.fn(), onRetry: vi.fn() };
}

/** Các mảnh chữ của bubble kết quả. Mặc định là ca EN→VI tra từ. */
function summary(patch: Partial<BubbleSummary> = {}): BubbleSummary {
  return { term: 'renewable', band: '6.5', meaning: 'tái tạo', meaningLang: 'vi', ...patch };
}

describe('bubble', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    hideBubble();
  });

  it('bubble loading hiện trạng thái đang tải', () => {
    showLoadingBubble(rect);

    expect(shadow().textContent).toContain('Đang dịch');
  });

  it('bubble kết quả hiện nghĩa và 3 nút', () => {
    showResultBubble(rect, summary(), handlers());

    const root = shadow();
    expect(root.textContent).toContain('tái tạo');
    expect(root.querySelector('[data-action="speak"]')).not.toBeNull();
    expect(root.querySelector('[data-action="save"]')).not.toBeNull();
    expect(root.querySelector('[data-action="expand"]')).not.toBeNull();
  });

  it('bubble kết quả hiện từ tiếng Anh và chip band cùng dòng', () => {
    showResultBubble(rect, summary(), handlers());

    const root = shadow();
    expect(root.querySelector('.term')?.textContent).toBe('renewable');
    // Chữ "BAND" nằm trong nội dung chứ không phải một `::before` của CSS: trình đọc màn
    // hình phải đọc được "band 6.5", không phải một con số trơ trọi.
    expect(root.querySelector('.band')?.textContent).toBe('BAND 6.5');
  });

  it('không có band thì KHÔNG vẽ chip rỗng', () => {
    // Chiều VI→EN không có band nào. Một chip rỗng ở đó là một vệt màu vô nghĩa.
    showResultBubble(rect, summary({ band: '' }), handlers());

    expect(shadow().querySelector('.band')).toBeNull();
  });

  it('dòng nghĩa TIẾNG VIỆT mang class .vi để nhận mặt chữ serif', () => {
    showResultBubble(rect, summary(), handlers());

    expect(shadow().querySelector('.meaning')?.classList.contains('vi')).toBe(true);
  });

  it('dòng nghĩa TIẾNG ANH KHÔNG mang class .vi — serif chỉ dành cho tiếng Việt', () => {
    // VI→EN chế độ CÂU trả `band65_version`, một câu tiếng Anh. Lora là mặt chữ dành cho
    // tiếng Việt; gắn class .vi ở đây là hiện tiếng Anh bằng sai mặt chữ.
    showResultBubble(rect, summary({
      term: '', band: '',
      meaning: 'The government should invest more.',
      meaningLang: 'en',
    }), handlers());

    const line = shadow().querySelector('.meaning');
    expect(line?.textContent).toBe('The government should invest more.');
    expect(line?.classList.contains('vi')).toBe(false);
  });

  it('kết quả dịch câu không có dòng từ, chỉ có dòng nghĩa', () => {
    showResultBubble(rect, summary({ term: '', band: '' }), handlers());

    const root = shadow();
    expect(root.querySelector('.term')).toBeNull();
    expect(root.textContent).toContain('tái tạo');
  });

  it('bấm nút gọi đúng handler', () => {
    const h = handlers();
    showResultBubble(rect, summary(), h);

    (shadow().querySelector('[data-action="save"]') as HTMLElement).click();
    (shadow().querySelector('[data-action="expand"]') as HTMLElement).click();

    expect(h.onSave).toHaveBeenCalledOnce();
    expect(h.onExpand).toHaveBeenCalledOnce();
    expect(h.onSpeak).not.toHaveBeenCalled();
  });

  it('chỉ tồn tại một bubble dù gọi nhiều lần', () => {
    showLoadingBubble(rect);
    showResultBubble(rect, summary(), handlers());
    showResultBubble(rect, summary({ meaning: 'khác' }), handlers());

    expect(document.querySelectorAll(`#${BUBBLE_HOST_ID}`)).toHaveLength(1);
    expect(shadow().textContent).toContain('khác');
  });

  it('bubble lỗi hiện thông báo và nút thử lại khi lỗi có thể retry', () => {
    const h = handlers();
    showErrorBubble(rect, 'Backend chưa chạy', true, h);

    expect(shadow().textContent).toContain('Backend chưa chạy');
    (shadow().querySelector('[data-action="retry"]') as HTMLElement).click();
    expect(h.onRetry).toHaveBeenCalledOnce();
  });

  it('bubble lỗi không có nút thử lại khi lỗi không thể retry', () => {
    showErrorBubble(rect, 'Đã hết quota Gemini', false, handlers());

    expect(shadow().querySelector('[data-action="retry"]')).toBeNull();
  });

  it('icon chỉ có đúng một nút, không lộ nghĩa hay text nào', () => {
    showIconBubble(rect, vi.fn());

    const root = shadow();
    expect(root.querySelector('[data-action="translate"]')).not.toBeNull();
    expect(root.querySelectorAll('button')).toHaveLength(1);
    expect(root.querySelector('.text')).toBeNull();
  });

  it('bấm icon gọi handler đúng một lần', () => {
    const onTranslate = vi.fn();
    showIconBubble(rect, onTranslate);

    (shadow().querySelector('[data-action="translate"]') as HTMLElement).click();

    expect(onTranslate).toHaveBeenCalledOnce();
  });

  it('mousedown trên icon bị preventDefault để không mất vùng bôi đen', () => {
    // Trình duyệt collapse selection khi mousedown lên nút. Không chặn thì người dùng
    // thấy vệt bôi đen biến mất ngay lúc bấm — trông như thao tác đã hỏng.
    showIconBubble(rect, vi.fn());

    const event = new MouseEvent('mousedown', { bubbles: true, cancelable: true });
    (shadow().querySelector('[data-action="translate"]') as HTMLElement).dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
  });

  it('icon bị thay thế bởi bubble loading, không chồng lên nhau', () => {
    showIconBubble(rect, vi.fn());
    showLoadingBubble(rect);

    expect(document.querySelectorAll(`#${BUBBLE_HOST_ID}`)).toHaveLength(1);
    expect(shadow().querySelector('[data-action="translate"]')).toBeNull();
    expect(shadow().textContent).toContain('Đang dịch');
  });

  it('hideBubble gỡ hẳn host khỏi DOM', () => {
    showResultBubble(rect, summary(), handlers());
    hideBubble();

    expect(document.getElementById(BUBBLE_HOST_ID)).toBeNull();
  });

  it('nội dung nằm trong shadow root, không lọt ra document', () => {
    showResultBubble(rect, summary(), handlers());

    expect(document.body.textContent).not.toContain('tái tạo');
  });

  /* ========== Chip "+N từ hôm nay" trên thanh hành động (thiết kế 1b) ========== */

  it('chip đếm số từ đã lưu trong ngày', () => {
    showResultBubble(rect, summary(), handlers(), 3);

    expect(shadow().querySelector('.daily')?.textContent).toBe('+3 từ hôm nay');
  });

  it('chưa lưu từ nào hôm nay thì KHÔNG vẽ chip', () => {
    // "+0 từ hôm nay" là một huy hiệu nói rằng bạn chưa làm gì — nhiễu chứ không động viên.
    showResultBubble(rect, summary(), handlers(), 0);

    expect(shadow().querySelector('.daily')).toBeNull();
  });

  it('nút "Lưu vào sổ" là chữ, nằm trên thanh hành động', () => {
    showResultBubble(rect, summary(), handlers(), 1);

    const save = shadow().querySelector('[data-action="save"]');
    expect(save?.textContent).toBe('Lưu vào sổ');
    expect(save?.closest('.bar')).not.toBeNull();
  });
});

describe('giao diện sáng/tối của bubble', () => {
  const host = () => document.getElementById(BUBBLE_HOST_ID)!;

  it('bubble mới dựng mang đúng chế độ đang đặt', () => {
    setBubbleTheme('dark');

    showLoadingBubble(rect);

    expect(host().dataset.theme).toBe('dark');
  });

  it('đổi chế độ khi bubble đang hiện thì đổi luôn, không đợi lần sau', () => {
    setBubbleTheme('light');
    showLoadingBubble(rect);

    setBubbleTheme('dark');

    expect(host().dataset.theme).toBe('dark');
  });

  it('không nổ khi đổi chế độ lúc chưa có bubble nào', () => {
    hideBubble();

    expect(() => setBubbleTheme('dark')).not.toThrow();
  });
});
