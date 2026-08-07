import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from './App';
import type { TranslatePayload, TranslateResult } from '../shared/types';

const lastResult: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'was resiliented',
  payload: {
    term: 'resilient', lemma: 'resilient', pos: 'adj', ipa: '/rɪˈzɪliənt/',
    meaning_vi: 'kiên cường', definition_en: 'able to recover quickly', cefr: 'B2',
    band_level: '7.0', register: 'academic', collocations: [], examples: [], synonyms: [],
  } as unknown as TranslatePayload,
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
  });
});
