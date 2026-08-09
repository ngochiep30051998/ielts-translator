import { useState } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TranslateTab } from './TranslateTab';
import type { TranslateResult } from '../shared/types';

function mockSave(response: unknown) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async () => response,
  );
}

const SAVE_OK = { ok: true, data: { id: 1, alreadyExists: false } };

const enViWord: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'renewable',
  payload: {
    term: 'renewable', lemma: 'renewable', pos: 'adj', ipa: '/rɪˈnjuːəbl/',
    meaning_vi: 'tái tạo', definition_en: 'able to be renewed', cefr: 'B2',
    band_level: '6.5', register: 'academic',
    collocations: ['renewable energy', 'renewable resources'],
    examples: [{ en: 'We rely on renewable energy.', vi: 'Chúng ta dựa vào năng lượng tái tạo.' }],
    synonyms: [{ term: 'sustainable', band: '7.0' }],
  },
};

/** Harness có state thật cho các test cần ô nhập cập nhật được (props của TranslateTab đều là controlled). */
function StatefulTab({ initialDraft = '', initialResult = null }: {
  initialDraft?: string;
  initialResult?: TranslateResult | null;
}) {
  const [draft, setDraft] = useState(initialDraft);
  const [result, setResult] = useState<TranslateResult | null>(initialResult);
  return (
    <TranslateTab
      draft={draft} onDraftChange={setDraft}
      result={result} onResult={setResult} loaded
    />
  );
}

function mockSend(handler: (request: { type: string }) => unknown) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => handler(request),
  );
}

const BOX = /Text cần dịch/i;

describe('TranslateTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hiện trạng thái rỗng khi chưa dịch gì', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} result={null} onResult={() => {}} loaded />);

    expect(await screen.findByText(/nhập vào ô trên rồi bấm Dịch/i)).toBeInTheDocument();
  });

  it('hiện đầy đủ thông tin cho EN→VI tra từ', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('/rɪˈnjuːəbl/')).toBeInTheDocument();
    expect(screen.getByText('tái tạo')).toBeInTheDocument();
    expect(screen.getByText('able to be renewed')).toBeInTheDocument();
    expect(screen.getByText('renewable energy')).toBeInTheDocument();
    expect(screen.getByText('We rely on renewable energy.')).toBeInTheDocument();
    expect(screen.getByText('sustainable')).toBeInTheDocument();
    // TranslateTab giờ là component thuần: không được tự gọi GET_LAST_RESULT (hay bất kỳ
    // message nào) khi chỉ render — result/loaded phải đến từ props do App truyền xuống.
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it('hiện band kèm chú thích đây là ước lượng', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    // Payload có 2 chỗ gắn band (band_level của từ và band của từ đồng nghĩa),
    // cả hai đều phải mang chú thích ước lượng; chỗ đầu là band của chính từ.
    const bands = await screen.findAllByTitle(/ước lượng/i);
    expect(bands[0]).toHaveTextContent('6.5');
    expect(bands).toHaveLength(2);
  });

  it('hiện bản dịch và từ khoá cho EN→VI tra câu', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded result={{
      direction: 'EN_VI', mode: 'SENTENCE', cached: false, sourceText: 'a sentence',
      payload: {
        translation_vi: 'Chính phủ nên đầu tư nhiều hơn.',
        key_vocab: [{ term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' }],
        structure_note: 'Câu dùng mệnh đề quan hệ.',
      },
    }} />);

    expect(await screen.findByText('Chính phủ nên đầu tư nhiều hơn.')).toBeInTheDocument();
    expect(screen.getByText('allocate')).toBeInTheDocument();
    expect(screen.getByText('Câu dùng mệnh đề quan hệ.')).toBeInTheDocument();
  });

  it('hiện lựa chọn thay thế cho VI→EN tra từ', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded result={{
      direction: 'VI_EN', mode: 'WORD', cached: false, sourceText: 'tái tạo',
      payload: {
        best_en: 'renewable',
        alternatives: [{ term: 'sustainable', band: '7.0', register: 'academic',
                        when_to_use: 'Khi nói về phát triển bền vững.' }],
        collocations: ['renewable energy'],
        examples: ['We need renewable energy.'],
      },
    }} />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('sustainable')).toBeInTheDocument();
    expect(screen.getByText('Khi nói về phát triển bền vững.')).toBeInTheDocument();
  });

  it('hiện bản band 6.5 kèm giải thích và mục nên tránh cho VI→EN tra câu', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded result={{
      direction: 'VI_EN', mode: 'SENTENCE', cached: false, sourceText: 'câu tiếng Việt',
      payload: {
        band65_version: 'The government should allocate more funding.',
        why_notes: ['Dùng allocate thay cho give để trang trọng hơn.'],
        key_phrases: ['allocate funding'],
        avoid: [{ phrase: 'give more money', reason: 'Quá thông tục cho văn viết học thuật.' }],
      },
    }} />);

    expect(await screen.findByText('The government should allocate more funding.')).toBeInTheDocument();
    expect(screen.getByText('Dùng allocate thay cho give để trang trọng hơn.')).toBeInTheDocument();
    expect(screen.getByText('give more money')).toBeInTheDocument();
    expect(screen.getByText('Quá thông tục cho văn viết học thuật.')).toBeInTheDocument();
  });

  it('bấm Lưu từ gửi SAVE_WORD và báo đã lưu', async () => {
    mockSave(SAVE_OK);
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText(/Đã lưu/i)).toBeInTheDocument());
    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SAVE_WORD' }),
    );
  });

  it('báo Đã có trong sổ khi backend trả alreadyExists', async () => {
    mockSave({ ok: true, data: { id: 1, alreadyExists: true } });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText(/Đã có trong sổ/i)).toBeInTheDocument());
  });

  it('hiện thông báo lỗi khi lưu thất bại', async () => {
    mockSave({ ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true } });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText('Backend chưa chạy')).toBeInTheDocument());
  });
});

describe('ô nhập text trong tab Dịch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('bấm Dịch gửi TRANSLATE_TEXT với text đã trim và hiện kết quả', async () => {
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? { ok: true, data: enViWord }
      : { ok: true, data: null });
    render(<StatefulTab />);

    await userEvent.type(screen.getByLabelText(BOX), '  renewable  ');
    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    expect(chrome.runtime.sendMessage)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
  });

  it('ô trống thì nút Dịch tắt', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab />);

    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it('vượt 1500 ký tự: đếm chuyển đỏ, nút tắt, Ctrl+Enter cũng KHÔNG gửi message', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab initialDraft={'a'.repeat(1501)} />);

    expect(screen.getByText('1501/1500')).toHaveClass('over');
    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();

    // Phím tắt không đi qua nút, nên nút disabled một mình không chặn được nó.
    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it('Ctrl+Enter gửi giống bấm nút', async () => {
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? { ok: true, data: enViWord }
      : { ok: true, data: null });
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(chrome.runtime.sendMessage)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
  });

  it('lỗi retry được: hiện Thử lại và gửi lại ĐÚNG text đã gửi, không phải text trong ô', async () => {
    mockSend(() => ({
      ok: false,
      error: { code: 'GEMINI_UNAVAILABLE', message: 'Gemini tạm thời lỗi', retryable: true },
    }));
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));
    expect(await screen.findByText(/Gemini tạm thời lỗi/)).toBeInTheDocument();

    // Người dùng gõ thêm vào ô TRƯỚC khi bấm Thử lại.
    await userEvent.type(screen.getByLabelText(BOX), ' energy');
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }));

    expect(chrome.runtime.sendMessage)
      .toHaveBeenLastCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
  });

  it('lỗi không retry được thì không có nút Thử lại', async () => {
    mockSend(() => ({
      ok: false,
      error: { code: 'TEXT_TOO_LONG', message: 'Đoạn text quá dài', retryable: false },
    }));
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    expect(await screen.findByText(/Đoạn text quá dài/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thử lại' })).not.toBeInTheDocument();
  });
});
