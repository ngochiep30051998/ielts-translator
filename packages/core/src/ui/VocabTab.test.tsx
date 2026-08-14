import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VocabTab } from './VocabTab';
import type { VocabEntryDto } from '../types';
import { transportSend } from '../../vitest.setup';

function entry(id: number, term: string, meaningVi: string): VocabEntryDto {
  return {
    id, term, lemma: term, lang: 'en', pos: 'adj', ipa: '/test/', meaningVi,
    definitionEn: null, cefr: 'B2', bandLevel: '6.5', tags: ['environment'],
    sourceUrl: 'https://example.com', sourceSentence: null,
    collocations: [], examples: [], createdAt: '2026-08-03T10:00:00Z',
  };
}

/** Giả lập server phân trang: trả đúng trang mà request hỏi, kèm tổng đếm trên MỌI trang. */
function mockSearchPages(pages: VocabEntryDto[][]) {
  const totalElements = pages.reduce((sum, p) => sum + p.length, 0);
  transportSend.mockImplementation(
    async (request: { type: string; page?: number }) => {
      if (request.type === 'SEARCH_VOCAB') {
        const page = request.page ?? 0;
        return { ok: true, data: {
          content: pages[page] ?? [], totalElements, totalPages: pages.length, number: page } };
      }
      return { ok: true, data: null };
    },
  );
}

function mockSearch(entries: VocabEntryDto[]) {
  mockSearchPages([entries]);
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

    await waitFor(() => expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', query: 'renew' }),
    ));
  });

  it('bấm xoá sẽ gửi DELETE_VOCAB rồi tải lại danh sách', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: /Xoá renewable/i }));

    await waitFor(() => expect(transportSend).toHaveBeenCalledWith(
      { type: 'DELETE_VOCAB', id: 1 },
    ));
  });

  it('hiện lỗi khi backend chết', async () => {
    transportSend.mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<VocabTab />);

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('có nút Thử lại khi lỗi có thể retry', async () => {
    transportSend.mockResolvedValue({
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

  it('đánh dấu trang đang xem và khoá nút Trước khi đang ở trang đầu', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
      [entry(3, 'scarce', 'khan hiếm')],
    ]);
    render(<VocabTab />);

    expect(await screen.findByRole('button', { name: 'Trang 1', current: 'page' }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Trang trước/i })).toBeDisabled();
  });

  it('bấm thẳng vào số trang sẽ nhảy tới trang đó', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
      [entry(3, 'scarce', 'khan hiếm')],
    ]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: 'Trang 3' }));

    expect(await screen.findByText('scarce')).toBeInTheDocument();
    expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', page: 2 }),
    );
  });

  it('rút gọn dãy số bằng dấu … khi sổ từ có rất nhiều trang', async () => {
    mockSearchPages(Array.from({ length: 40 }, (_, i) => [entry(i + 1, `từ${i}`, `nghĩa${i}`)]));
    render(<VocabTab />);
    await screen.findByText('từ0');

    // Trang đầu và trang cuối luôn bấm được, phần giữa bị cắt bằng dấu …
    expect(screen.getByRole('button', { name: 'Trang 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Trang 40' })).toBeInTheDocument();
    expect(screen.getByText('…')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Trang 20' })).not.toBeInTheDocument();
  });

  it('bấm Sau sẽ tải trang kế tiếp', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
    ]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: /Trang sau/i }));

    expect(await screen.findByText('mitigate')).toBeInTheDocument();
    expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', page: 1 }),
    );
  });

  it('khoá nút Sau khi đang ở trang cuối', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
    ]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: /Trang sau/i }));

    await screen.findByText('mitigate');
    expect(screen.getByRole('button', { name: /Trang sau/i })).toBeDisabled();
  });

  it('không hiện thanh phân trang khi cả sổ chỉ có một trang', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    expect(screen.queryByRole('navigation', { name: /Phân trang/i })).not.toBeInTheDocument();
  });

  it('gõ tìm kiếm mới sẽ quay về trang đầu', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
    ]);
    render(<VocabTab />);
    await screen.findByText('renewable');
    await userEvent.click(screen.getByRole('button', { name: /Trang sau/i }));
    await screen.findByText('mitigate');
    transportSend.mockClear();

    await userEvent.type(screen.getByPlaceholderText(/Tìm từ/i), 'renew');

    await waitFor(() => expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', query: 'renew', page: 0 }),
    ));
  });

  it('xoá từ cuối cùng của trang cuối sẽ lùi về trang trước', async () => {
    mockSearchPages([
      [entry(1, 'renewable', 'tái tạo')],
      [entry(2, 'mitigate', 'giảm nhẹ')],
    ]);
    render(<VocabTab />);
    await screen.findByText('renewable');
    await userEvent.click(screen.getByRole('button', { name: /Trang sau/i }));
    await screen.findByText('mitigate');

    await userEvent.click(screen.getByRole('button', { name: /Xoá mitigate/i }));

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', page: 0 }),
    );
  });
});
