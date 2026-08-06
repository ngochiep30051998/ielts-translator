import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BUBBLE_HOST_ID } from './bubble';
import { sendToBackground } from '../shared/messages';
import { DEFAULT_SETTINGS, type Settings } from '../shared/settings';

vi.mock('../shared/messages', () => ({ sendToBackground: vi.fn() }));
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
});
