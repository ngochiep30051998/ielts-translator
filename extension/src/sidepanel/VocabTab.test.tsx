import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VocabTab } from './VocabTab';
import type { VocabEntryDto } from '../shared/types';

function entry(id: number, term: string, meaningVi: string): VocabEntryDto {
  return {
    id, term, lemma: term, lang: 'en', pos: 'adj', ipa: '/test/', meaningVi,
    definitionEn: null, cefr: 'B2', bandLevel: '6.5', tags: ['environment'],
    sourceUrl: 'https://example.com', sourceSentence: null,
    collocations: [], examples: [], createdAt: '2026-08-03T10:00:00Z',
  };
}

function mockSearch(entries: VocabEntryDto[]) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      if (request.type === 'SEARCH_VOCAB') {
        return { ok: true, data: {
          content: entries, totalElements: entries.length, totalPages: 1, number: 0 } };
      }
      return { ok: true, data: null };
    },
  );
}

describe('VocabTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('tải và hiện danh sách từ khi mở tab', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo'), entry(2, 'mitigate', 'giảm nhẹ')]);
    render(<VocabTab />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('mitigate')).toBeInTheDocument();
  });

  it('hiện trạng thái rỗng khi sổ chưa có từ nào', async () => {
    mockSearch([]);
    render(<VocabTab />);

    expect(await screen.findByText(/Sổ từ đang trống/i)).toBeInTheDocument();
  });

  it('gõ vào ô tìm kiếm sẽ gửi SEARCH_VOCAB kèm từ khoá', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.type(screen.getByPlaceholderText(/Tìm từ/i), 'renew');

    await waitFor(() => expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', query: 'renew' }),
    ));
  });

  it('bấm xoá sẽ gửi DELETE_VOCAB rồi tải lại danh sách', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: /Xoá renewable/i }));

    await waitFor(() => expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      { type: 'DELETE_VOCAB', id: 1 },
    ));
  });

  it('hiện lỗi khi backend chết', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<VocabTab />);

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('có nút Thử lại khi lỗi có thể retry', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<VocabTab />);

    expect(await screen.findByRole('button', { name: /Thử lại/i })).toBeInTheDocument();
  });

  it('hiện tổng số từ trong sổ', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);

    expect(await screen.findByText(/1 từ/i)).toBeInTheDocument();
  });
});
