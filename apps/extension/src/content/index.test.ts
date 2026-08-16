import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BUBBLE_HOST_ID } from './bubble';
import { sendToBackground } from '@ielts/core';
import { DEFAULT_SETTINGS, type Settings } from '../shared/settings';
import { bumpDailySaves } from '../shared/daily-saves';

// `importOriginal` chứ không thay cả module: content script còn dùng `validateSelection`,
// `shortMeaning` và `speak` thật từ core.
vi.mock('@ielts/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@ielts/core')>()),
  sendToBackground: vi.fn(),
}));
vi.mock('../shared/settings', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../shared/settings')>();
  return { ...actual, loadSettings: vi.fn() };
});

const { loadSettings } = await import('../shared/settings');

const DEBOUNCE_MS = 250;

function mockSelection(text: string): void {
  vi.spyOn(window, 'getSelection').mockReturnValue({
    toString: () => text,
    rangeCount: text.length > 0 ? 1 : 0,
    anchorNode: document.body.firstChild,
    getRangeAt: () => ({
      getBoundingClientRect: () =>
        ({ left: 100, top: 200, bottom: 220, width: 80, height: 20 }) as DOMRect,
    }),
  } as unknown as Selection);
}

function shadow(): ShadowRoot {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (!host?.shadowRoot) throw new Error('Chưa có gì trong DOM');
  return host.shadowRoot;
}

function iconButton(): HTMLElement | null {
  return document.getElementById(BUBBLE_HOST_ID)
    ?.shadowRoot?.querySelector('[data-action="translate"]') ?? null;
}

/** Bôi đen xong và để debounce chạy hết. */
async function selectText(text: string): Promise<void> {
  mockSelection(text);
  document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  // Nhường microtask cho loadSettings() và các await bên trong handler.
  await vi.advanceTimersByTimeAsync(0);
}

function settings(patch: Partial<Settings> = {}): Settings {
  return { ...DEFAULT_SETTINGS, ...patch };
}

describe('content script — bôi đen hiện icon, bấm icon mới dịch', () => {
  beforeEach(async () => {
    vi.useFakeTimers();
    vi.resetModules();
    document.body.innerHTML = '<p>một đoạn văn bản để bôi đen</p>';
    vi.mocked(loadSettings).mockResolvedValue(settings());
    vi.mocked(sendToBackground).mockResolvedValue({
      ok: true,
      data: {
        direction: 'EN_VI',
        mode: 'WORD',
        cached: false,
        payload: { meaning_vi: 'giảm nhẹ' },
        sourceText: 'mitigate',
      },
    } as never);
    await import('./index');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.getElementById(BUBBLE_HOST_ID)?.remove();
  });

  it('bôi đen KHÔNG gọi dịch — chỉ hiện icon', async () => {
    // Đây là toàn bộ mục đích của thay đổi: bôi đen để copy hay đọc lại thì không
    // được tốn một lượt Gemini nào. Thiếu test này thì lần refactor sau ai đó gọi lại
    // translate trong nhánh auto mà không có gì đỏ.
    await selectText('mitigate');

    expect(iconButton()).not.toBeNull();
    expect(sendToBackground).not.toHaveBeenCalled();
  });

  it('bấm icon mới gửi TRANSLATE_SELECTION, đúng một lần', async () => {
    await selectText('mitigate');

    iconButton()!.click();
    await vi.advanceTimersByTimeAsync(0);

    const calls = vi.mocked(sendToBackground).mock.calls
      .filter(([msg]) => (msg as { type: string }).type === 'TRANSLATE_SELECTION');
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toMatchObject({ type: 'TRANSLATE_SELECTION', text: 'mitigate' });
  });

  it('vùng bôi đen bị xoá sau khi hiện icon thì bấm icon VẪN dịch đúng đoạn cũ', async () => {
    // Trình duyệt collapse selection khi mousedown lên nút, nên handler click không được
    // đọc lại window.getSelection(). Test này là chỗ duy nhất bắt được lỗi đó — jsdom
    // không tự collapse, nên cách đọc-lại-DOM vẫn xanh ở mọi test khác rồi hỏng thật.
    await selectText('mitigate');
    mockSelection('');

    iconButton()!.click();
    await vi.advanceTimersByTimeAsync(0);

    expect(sendToBackground).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'TRANSLATE_SELECTION', text: 'mitigate' }),
    );
  });

  /**
   * Bấm chuột thật: mousedown → mouseup → click. `.click()` chỉ phát mỗi `click`, nên
   * dùng nó là bỏ sót đúng sự kiện gây lỗi — `mouseup` nổi từ trong shadow DOM ra
   * `document` và khởi động lại debounce chọn-chữ.
   */
  function realClick(el: HTMLElement): void {
    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true, cancelable: true }));
    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, composed: true }));
    el.click();
  }

  it('kết quả từ cache không bị debounce của chính cú bấm icon đè mất', async () => {
    // Cache trả gần như tức thì nên kết quả hiện TRƯỚC mốc 250ms; nếu mouseup của cú
    // bấm icon khởi động lại debounce thì tới 250ms icon sẽ vẽ đè lên kết quả và người
    // dùng thấy nó "hiện xong rồi biến mất". Đường Gemini che được lỗi này vì nó trả về
    // sau 250ms nên kết quả đè ngược lại icon.
    await selectText('mitigate');

    realClick(iconButton()!);
    await vi.advanceTimersByTimeAsync(0);
    expect(shadow().textContent).toContain('giảm nhẹ');

    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);

    expect(iconButton()).toBeNull();
    expect(shadow().textContent).toContain('giảm nhẹ');
  });

  it('bấm Lưu vào sổ không kích hoạt một lượt dịch lại đè lên thông báo', async () => {
    // Lỗi có sẵn từ trước, cùng gốc với ca trên: mọi mouseup trong bubble đều khởi
    // động lại debounce. Thông báo "Đã lưu vào sổ" biến mất sau 250ms mà không ai
    // hiểu vì sao.
    await selectText('mitigate');
    realClick(iconButton()!);
    await vi.advanceTimersByTimeAsync(0);

    const save = shadow().querySelector('[data-action="save"]') as HTMLElement;
    realClick(save);
    await vi.advanceTimersByTimeAsync(0);
    expect(shadow().textContent).toContain('Đã lưu vào sổ');

    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);

    expect(shadow().textContent).toContain('Đã lưu vào sổ');
    expect(iconButton()).toBeNull();
  });

  /* ========== Chip "+N từ hôm nay" sau khi lưu (thiết kế 1b) ========== */

  /**
   * Giả lập đúng thứ tự của service worker: nó `bumpDailySaves()` TRƯỚC khi trả lời
   * SAVE_WORD (xem `noteVocabSaved`), nên content script đọc lại là thấy số mới.
   */
  function mockSaveFlow(alreadyExists = false): void {
    vi.mocked(sendToBackground).mockImplementation(async (message) => {
      if ((message as { type: string }).type === 'SAVE_WORD') {
        if (!alreadyExists) await bumpDailySaves();
        return { ok: true, data: { id: 1, alreadyExists } } as never;
      }
      return {
        ok: true,
        data: {
          direction: 'EN_VI',
          mode: 'WORD',
          cached: false,
          payload: { meaning_vi: 'giảm nhẹ' },
          sourceText: 'mitigate',
        },
      } as never;
    });
  }

  /** Bôi đen → bấm icon → bấm "Lưu vào sổ". */
  async function dichRoiLuu(): Promise<void> {
    await selectText('mitigate');
    realClick(iconButton()!);
    await vi.advanceTimersByTimeAsync(0);
    realClick(shadow().querySelector('[data-action="save"]') as HTMLElement);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
  }

  it('lượt lưu ĐẦU TIÊN trong ngày vẫn hiện chip số vừa tăng', async () => {
    // Ca hỏng cũ: chip đọc số TRƯỚC khi lưu, nên lượt đầu tiên của ngày luôn là 0 (ẩn
    // chip) và số mới không có lần vẽ lại nào — người dùng không bao giờ thấy nó tăng.
    await chrome.storage.local.clear();
    mockSaveFlow();

    await dichRoiLuu();

    expect(shadow().textContent).toContain('Đã lưu vào sổ');
    expect(shadow().querySelector('.daily')?.textContent).toBe('+1 từ hôm nay');
  });

  it('lưu thêm từ nữa thì chip đi lên theo', async () => {
    await chrome.storage.local.clear();
    await bumpDailySaves();          // đã lưu 1 từ trước đó trong ngày
    mockSaveFlow();

    await dichRoiLuu();

    expect(shadow().querySelector('.daily')?.textContent).toBe('+2 từ hôm nay');
  });

  it('từ ĐÃ CÓ trong sổ thì không có chip — không có số nào vừa tăng', async () => {
    await chrome.storage.local.clear();
    mockSaveFlow(true);

    await dichRoiLuu();

    expect(shadow().textContent).toContain('Đã có trong sổ');
    expect(shadow().querySelector('.daily')).toBeNull();
  });

  it('đoạn quá dài ra bubble lỗi, không ra icon', async () => {
    await selectText('x'.repeat(1501));

    expect(iconButton()).toBeNull();
    expect(shadow().textContent).toContain('quá dài');
    expect(sendToBackground).not.toHaveBeenCalled();
  });

  it('bỏ bôi đen thì ẩn hết', async () => {
    await selectText('mitigate');
    expect(iconButton()).not.toBeNull();

    await selectText('');

    expect(document.getElementById(BUBBLE_HOST_ID)).toBeNull();
  });

  it('chế độ hotkey: bôi đen không hiện gì cả', async () => {
    vi.mocked(loadSettings).mockResolvedValue(settings({ triggerMode: 'hotkey' }));

    await selectText('mitigate');

    expect(document.getElementById(BUBBLE_HOST_ID)).toBeNull();
    expect(sendToBackground).not.toHaveBeenCalled();
  });

  it('chưa đăng nhập thì bong bóng nói rõ nguyên nhân, không phải thông điệp chung chung', async () => {
    vi.mocked(sendToBackground).mockResolvedValue({
      ok: false,
      error: {
        code: 'UNAUTHORIZED',
        message: 'Cần đăng nhập để dùng chức năng này',
        retryable: false,
      },
    });
    await import('./index');

    await selectText('mitigate');
    iconButton()?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await vi.advanceTimersByTimeAsync(0);

    const text = shadow().textContent ?? '';
    expect(text).toContain('Cần đăng nhập');
    expect(text).toContain('side panel');
    // retryable = false nên KHÔNG có nút "Thử lại": bấm lại mười lần vẫn thế.
    expect(text).not.toContain('Thử lại');
  });
});
