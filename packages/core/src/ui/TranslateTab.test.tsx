import { useState } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TranslateTab } from './TranslateTab';
import type { TranslateResult } from '../types';
import { transportSend } from '../../vitest.setup';

function mockSave(response: unknown) {
  transportSend.mockImplementation(
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
  transportSend.mockImplementation(
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

    // Chỉ khẳng định phần chung của cả hai surface. Câu đầy đủ khác nhau giữa extension
    // (có bôi đen text trên trang) và web (không) — chỗ đó có test riêng ở
    // `surface-copy.test.tsx`.
    expect(await screen.findByText(/rồi bấm Dịch/i)).toBeInTheDocument();
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
    expect(transportSend).not.toHaveBeenCalled();
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
    expect(transportSend).toHaveBeenCalledWith(
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

/* ================= Nút "Lưu N từ đáng học" ================= */

/** Kết quả EN→VI chế độ CÂU — tổ hợp DUY NHẤT có `key_vocab`. */
function enViSentence(
  keyVocab: { term: string; meaning_vi: string; band_level: string }[],
): TranslateResult {
  return {
    direction: 'EN_VI', mode: 'SENTENCE', cached: false,
    sourceText: 'The government should allocate more funding.',
    payload: {
      translation_vi: 'Chính phủ nên phân bổ nhiều ngân sách hơn.',
      key_vocab: keyVocab,
      structure_note: 'Câu dùng mệnh đề quan hệ.',
    },
  };
}

const THREE_VOCAB = enViSentence([
  { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
  { term: 'funding', meaning_vi: 'ngân sách', band_level: '6.5' },
  { term: 'mitigate', meaning_vi: 'giảm nhẹ', band_level: '7.5' },
]);

const KEY_VOCAB_BUTTON = /từ đáng học/i;

/** Phản hồi cho SAVE_KEY_VOCAB; mọi message khác trả ok rỗng. */
function mockKeyVocabSave(data: {
  saved: number; existed: number; failures: { term: string; error: unknown }[];
}) {
  transportSend.mockImplementation(async (request: { type: string }) =>
    request.type === 'SAVE_KEY_VOCAB' ? { ok: true, data } : { ok: true, data: null });
}

describe('nút Lưu từ đáng học', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hiện với EN→VI chế độ CÂU, nhãn đếm đúng số từ', async () => {
    mockKeyVocabSave({ saved: 3, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    expect(await screen.findByRole('button', { name: 'Lưu 3 từ đáng học' })).toBeInTheDocument();
  });

  it('nhãn đếm số từ THẬT sau khi bỏ trùng và lọc phần tử rỗng', async () => {
    mockKeyVocabSave({ saved: 2, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded result={enViSentence([
      { term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' },
      { term: 'Allocate', meaning_vi: 'cấp phát', band_level: '7.5' },
      { term: '   ', meaning_vi: 'rỗng', band_level: '6.0' },
      { term: 'funding', meaning_vi: 'ngân sách', band_level: '6.5' },
    ])} />);

    // 4 phần tử thô, nhưng chỉ 2 từ thật sự gửi đi được.
    expect(await screen.findByRole('button', { name: 'Lưu 2 từ đáng học' })).toBeInTheDocument();
  });

  it('KHÔNG hiện với EN→VI chế độ TỪ — nút "Lưu từ" đã làm đúng việc đó', async () => {
    mockKeyVocabSave({ saved: 0, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={enViWord} onResult={() => {}} loaded />);

    expect(await screen.findByRole('button', { name: /Lưu từ/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: KEY_VOCAB_BUTTON })).not.toBeInTheDocument();
  });

  it('KHÔNG hiện với VI→EN chế độ CÂU — key_phrases không có nghĩa tiếng Việt', async () => {
    mockKeyVocabSave({ saved: 0, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded result={{
      direction: 'VI_EN', mode: 'SENTENCE', cached: false, sourceText: 'câu tiếng Việt',
      payload: {
        band65_version: 'The government should allocate more funding.',
        why_notes: [], key_phrases: ['allocate funding'], avoid: [],
      },
    }} />);

    expect(screen.queryByRole('button', { name: KEY_VOCAB_BUTTON })).not.toBeInTheDocument();
  });

  it('KHÔNG hiện khi câu không có từ đáng học nào dùng được', async () => {
    mockKeyVocabSave({ saved: 0, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} onResult={() => {}} loaded
      result={enViSentence([{ term: '  ', meaning_vi: '  ', band_level: '7.0' }])} />);

    expect(screen.queryByRole('button', { name: KEY_VOCAB_BUTTON })).not.toBeInTheDocument();
  });

  it('bấm thì gửi SAVE_KEY_VOCAB kèm cả kết quả dịch', async () => {
    mockKeyVocabSave({ saved: 3, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    await waitFor(() => expect(transportSend).toHaveBeenCalledWith(
      { type: 'SAVE_KEY_VOCAB', result: THREE_VOCAB, tags: [] },
    ));
  });

  it('lưu trọn vẹn toàn từ mới: báo số từ đã lưu', async () => {
    mockKeyVocabSave({ saved: 3, existed: 0, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    expect(await screen.findByText('Đã lưu 3 từ vào sổ')).toBeInTheDocument();
  });

  it('có từ đã tồn tại: nói rõ bao nhiêu mới, bao nhiêu đã có', async () => {
    mockKeyVocabSave({ saved: 2, existed: 1, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    expect(await screen.findByText('Đã lưu 2 từ, 1 từ đã có sẵn')).toBeInTheDocument();
  });

  it('tất cả đều đã có: nói thẳng, KHÔNG báo "đã lưu 0 từ"', async () => {
    mockKeyVocabSave({ saved: 0, existed: 3, failures: [] });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    expect(await screen.findByText('Cả 3 từ đều đã có trong sổ')).toBeInTheDocument();
  });

  it('có từ lỗi: kind bad, nêu số lưu được kèm thông điệp lỗi đầu tiên', async () => {
    mockKeyVocabSave({
      saved: 1, existed: 0, failures: [
        { term: 'funding', error: { code: 'GEMINI_QUOTA', message: 'Hết quota hôm nay', retryable: false } },
        { term: 'mitigate', error: { code: 'INTERNAL', message: 'Lỗi khác', retryable: false } },
      ],
    });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    const status = await screen.findByText('Đã lưu 1 từ, 2 từ lỗi: Hết quota hôm nay');
    expect(status).toHaveClass('bad');
  });

  it('transport hỏng: hiện thông điệp lỗi của transport', async () => {
    transportSend.mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('đang lưu thì nút đổi nhãn, bị disable, và chặn lượt gửi thứ hai', async () => {
    let resolveSave: (value: unknown) => void = () => {};
    transportSend.mockImplementation(async () => new Promise((resolve) => { resolveSave = resolve; }));
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    const button = await screen.findByRole('button', { name: 'Đang lưu…' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(transportSend).toHaveBeenCalledTimes(1);

    resolveSave({ ok: true, data: { saved: 3, existed: 0, failures: [] } });
    await screen.findByText('Đã lưu 3 từ vào sổ');
  });

  it('hai nút khoá ĐỘC LẬP: đang lưu mẻ từ đáng học thì nút "Lưu từ" vẫn bấm được', async () => {
    // Dùng chung một cờ `saving` sẽ khoá cả hai nút cùng lúc — người dùng bấm nhầm một nút
    // là mất luôn nút kia cho tới khi mẻ chạy xong.
    let resolveBatch: (value: unknown) => void = () => {};
    transportSend.mockImplementation(async (request: { type: string }) =>
      request.type === 'SAVE_KEY_VOCAB'
        ? new Promise((resolve) => { resolveBatch = resolve; })
        : { ok: true, data: { id: 1, alreadyExists: false } });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: KEY_VOCAB_BUTTON }));

    const saveWord = screen.getByRole('button', { name: 'Lưu từ' });
    expect(saveWord).toBeEnabled();

    await userEvent.click(saveWord);
    expect(transportSend).toHaveBeenCalledWith(expect.objectContaining({ type: 'SAVE_WORD' }));

    resolveBatch({ ok: true, data: { saved: 3, existed: 0, failures: [] } });
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Lưu 3 từ đáng học' }),
    ).toBeEnabled());
  });

  it('ngược lại: đang lưu cả câu thì nút từ đáng học vẫn bấm được', async () => {
    let resolveWord: (value: unknown) => void = () => {};
    transportSend.mockImplementation(async (request: { type: string }) =>
      request.type === 'SAVE_WORD'
        ? new Promise((resolve) => { resolveWord = resolve; })
        : { ok: true, data: { saved: 3, existed: 0, failures: [] } });
    render(<TranslateTab draft="" onDraftChange={() => {}} result={THREE_VOCAB} onResult={() => {}} loaded />);

    await userEvent.click(await screen.findByRole('button', { name: 'Lưu từ' }));

    expect(screen.getByRole('button', { name: 'Lưu 3 từ đáng học' })).toBeEnabled();

    resolveWord({ ok: true, data: { id: 1, alreadyExists: false } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu từ' })).toBeEnabled());
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

    expect(transportSend)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
  });

  it('ô trống thì nút Dịch tắt', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab />);

    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();
    expect(transportSend).not.toHaveBeenCalled();
  });

  it('vượt 1500 ký tự: đếm chuyển đỏ, nút tắt, Ctrl+Enter cũng KHÔNG gửi message', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab initialDraft={'a'.repeat(1501)} />);

    expect(screen.getByText('1501/1500')).toHaveClass('over');
    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();

    // Phím tắt không đi qua nút, nên nút disabled một mình không chặn được nó.
    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(transportSend).not.toHaveBeenCalled();
  });

  it('Ctrl+Enter gửi giống bấm nút', async () => {
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? { ok: true, data: enViWord }
      : { ok: true, data: null });
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(transportSend)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
  });

  it('đang dịch thì nút đổi nhãn "Đang dịch…", bị disable, và giữ nguyên kết quả cũ trên màn hình', async () => {
    let resolveTranslate: (value: unknown) => void = () => {};
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? new Promise((resolve) => { resolveTranslate = resolve; })
      : { ok: true, data: null });
    // Có sẵn kết quả cũ trên màn hình (mô phỏng dịch lại): dịch lần mới KHÔNG được
    // xoá/nháy trắng kết quả đang hiện trong lúc chờ.
    render(<StatefulTab initialResult={enViWord} initialDraft="renewable" />);

    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    const button = await screen.findByRole('button', { name: 'Đang dịch…' });
    expect(button).toBeDisabled();
    expect(screen.getByText('tái tạo')).toBeInTheDocument();

    // Resolve để không rò promise treo sang test khác.
    resolveTranslate({ ok: true, data: enViWord });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dịch' })).toBeInTheDocument());
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

    expect(transportSend)
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
