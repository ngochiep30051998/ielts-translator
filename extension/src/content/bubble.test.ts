import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  showLoadingBubble, showResultBubble, showErrorBubble, showIconBubble, hideBubble, BUBBLE_HOST_ID,
} from './bubble';

const rect = { left: 100, top: 200, bottom: 220, width: 80, height: 20 } as DOMRect;

function shadow(): ShadowRoot {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (!host?.shadowRoot) throw new Error('Chưa có bubble trong DOM');
  return host.shadowRoot;
}

function handlers() {
  return { onSpeak: vi.fn(), onSave: vi.fn(), onExpand: vi.fn(), onRetry: vi.fn() };
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
    showResultBubble(rect, 'tái tạo', handlers());

    const root = shadow();
    expect(root.textContent).toContain('tái tạo');
    expect(root.querySelector('[data-action="speak"]')).not.toBeNull();
    expect(root.querySelector('[data-action="save"]')).not.toBeNull();
    expect(root.querySelector('[data-action="expand"]')).not.toBeNull();
  });

  it('bấm nút gọi đúng handler', () => {
    const h = handlers();
    showResultBubble(rect, 'tái tạo', h);

    (shadow().querySelector('[data-action="save"]') as HTMLElement).click();
    (shadow().querySelector('[data-action="expand"]') as HTMLElement).click();

    expect(h.onSave).toHaveBeenCalledOnce();
    expect(h.onExpand).toHaveBeenCalledOnce();
    expect(h.onSpeak).not.toHaveBeenCalled();
  });

  it('chỉ tồn tại một bubble dù gọi nhiều lần', () => {
    showLoadingBubble(rect);
    showResultBubble(rect, 'tái tạo', handlers());
    showResultBubble(rect, 'khác', handlers());

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
    showResultBubble(rect, 'tái tạo', handlers());
    hideBubble();

    expect(document.getElementById(BUBBLE_HOST_ID)).toBeNull();
  });

  it('nội dung nằm trong shadow root, không lọt ra document', () => {
    showResultBubble(rect, 'tái tạo', handlers());

    expect(document.body.textContent).not.toContain('tái tạo');
  });
});
