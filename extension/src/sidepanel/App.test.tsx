import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import type { TranslateResult } from '../shared/types';

const lastResult: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'was resiliented',
  payload: {
    term: 'resilient', lemma: 'resilient', pos: 'adj', ipa: '/rɪˈzɪliənt/',
    meaning_vi: 'kiên cường', definition_en: 'able to recover quickly', cefr: 'B2',
    band_level: '7.0', register: 'academic', collocations: [], examples: [], synonyms: [],
  },
};

/** Kết quả TRANSLATE_TEXT trả về khi dịch từ ô nhập (khác lastResult để không lẫn với GET_LAST_RESULT). */
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

/** Mock đủ cho App + mọi tab con mà test này chạm tới. */
function mockBackend(last: TranslateResult | null) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      switch (request.type) {
        case 'GET_LAST_RESULT':
          return { ok: true, data: last };
        case 'SEARCH_VOCAB':
          return { ok: true, data: { content: [], totalElements: 0, totalPages: 0, number: 0 } };
        default:
          return { ok: true, data: null };
      }
    },
  );
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('đọc kết quả gần nhất một lần và hiện ở tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);

    expect(await screen.findByText('kiên cường')).toBeInTheDocument();
    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith({ type: 'GET_LAST_RESULT' });
    expect(chrome.runtime.sendMessage).toHaveBeenCalledTimes(1);
  });

  it('không gọi lại GET_LAST_RESULT khi đổi tab rồi quay lại tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);

    await screen.findByText('kiên cường');
    expect(chrome.runtime.sendMessage).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('tab', { name: 'Sổ từ' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Dịch' }));

    expect(await screen.findByText('kiên cường')).toBeInTheDocument();
    expect(chrome.runtime.sendMessage).toHaveBeenCalledTimes(1);
  });

  it('điền sẵn ô nhập bằng text của kết quả gần nhất', async () => {
    mockBackend(lastResult);
    render(<App />);

    expect(await screen.findByDisplayValue('was resiliented')).toBeInTheDocument();
  });

  it('đổi sang tab khác rồi quay lại vẫn giữ nguyên text đang gõ dở', async () => {
    mockBackend(null);
    render(<App />);

    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'resilient');

    await userEvent.click(screen.getByRole('tab', { name: 'Sổ từ' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Dịch' }));

    // Khoá quyết định "state ở App": đẩy state ngược xuống TranslateTab cho gọn
    // sẽ làm ca này đỏ ngay.
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('resilient');
  });

  it('dịch từ ô nhập cập nhật vùng kết quả của panel', async () => {
    // Không dùng mockBackend(): test này cần TRANSLATE_TEXT trả kết quả riêng
    // (enViWord), còn GET_LAST_RESULT trả null để ô nhập bắt đầu trống.
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
      async (request: { type: string }) =>
        request.type === 'TRANSLATE_TEXT' ? { ok: true, data: enViWord } : { ok: true, data: null },
    );
    render(<App />);
    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'renewable');
    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    // Khoá đường nối App → TranslateTab: nếu App không truyền đúng onResult xuống,
    // TranslateTab vẫn gọi được onResult nhưng App không cập nhật state result,
    // nên panel không bao giờ hiện kết quả.
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
    // Dịch xong không được đụng vào nội dung ô nhập (spec §2).
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('renewable');
  });
});
