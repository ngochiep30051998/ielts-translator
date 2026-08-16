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

<<<<<<< Updated upstream
=======
  /* ================= Hàng chip chủ đề ================= */

  describe('lọc theo chủ đề', () => {
    const TAGS: VocabTag[] = [
      { tag: 'Môi trường', count: 24, mastered: 17 },
      { tag: 'Giáo dục', count: 19, mastered: 10 },
    ];

    it('hiện chip cho từng chủ đề, "Tất cả" luôn đứng đầu', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], { tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');

      const chips = await screen.findAllByRole('button', { name: /Lọc theo/i });
      expect(chips[0]).toHaveAccessibleName(/Tất cả/);
      expect(chips.map((c) => c.textContent)).toEqual(
        expect.arrayContaining([expect.stringContaining('Môi trường')]),
      );
    });

    it('bấm chip gửi SEARCH_VOCAB kèm đúng tag', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], { tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');

      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Môi trường/i }));

      await waitFor(() => expect(lastSearch().tag).toBe('Môi trường'));
    });

    it('bấm "Tất cả" bỏ lọc — tag về null chứ không phải chuỗi rỗng', async () => {
      // Chuỗi rỗng vẫn là một tham số `tag=` trên URL; backend sẽ lọc theo chủ đề tên rỗng
      // và trả về sổ trống. Phải là null để `searchVocab` bỏ hẳn tham số đi.
      mockSearch([entry(1, 'renewable', 'tái tạo')], { tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Môi trường/i }));
      await waitFor(() => expect(lastSearch().tag).toBe('Môi trường'));

      await userEvent.click(screen.getByRole('button', { name: /Lọc theo Tất cả/i }));

      await waitFor(() => expect(lastSearch().tag).toBeNull());
    });

    it('đổi chủ đề thì quay về trang đầu', async () => {
      // Đang ở trang 3 của "tất cả" rồi lọc còn 24 từ thì trang 3 không tồn tại — người
      // dùng nhận một danh sách rỗng cho một chủ đề đang có từ.
      mockSearchPages([
        [entry(1, 'renewable', 'tái tạo')],
        [entry(2, 'mitigate', 'giảm nhẹ')],
      ], { tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Trang sau/i }));
      await screen.findByText('mitigate');

      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Giáo dục/i }));

      await waitFor(() => expect(lastSearch()).toMatchObject({ tag: 'Giáo dục', page: 0 }));
    });

    it('chưa có chủ đề nào thì không vẽ hàng chip trống', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], { tags: [] });
      render(<VocabTab />);
      await screen.findByText('renewable');

      expect(screen.queryByRole('button', { name: /Lọc theo/i })).not.toBeInTheDocument();
    });

    it('bấm chip chủ đề KHÔNG làm đổi con số trên chip "Tất cả"', async () => {
      // "Tất cả" là đường về, và con số của nó là tổng BẤT BIẾN của cả sổ. Đọc
      // `totalElements` của lượt tìm kiếm đang lọc biến nó thành bản sao con số của chính
      // chip vừa bấm — hàng chip đọc thành "Tất cả 1 · Giáo dục 19".
      mockSearchPages([[
        entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }),
        entry(2, 'tuition', 'học phí', { tags: ['Giáo dục'] }),
      ]], { total: 128, untagged: 41, tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');

      expect(await screen.findByRole('button', { name: 'Lọc theo Tất cả, 128 từ' }))
        .toBeInTheDocument();

      await userEvent.click(screen.getByRole('button', { name: /Lọc theo Giáo dục/i }));
      await waitFor(() => expect(lastSearch().tag).toBe('Giáo dục'));

      expect(screen.getByRole('button', { name: 'Lọc theo Tất cả, 128 từ' })).toBeInTheDocument();
    });

    it('hiện chip "Chưa gắn" ở CUỐI hàng khi sổ còn từ chưa gắn thẻ', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] })],
        { total: 128, untagged: 41, tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');

      const chips = await screen.findAllByRole('button', { name: /Lọc theo/i });
      expect(chips[0]).toHaveAccessibleName(/Tất cả/);
      expect(chips[chips.length - 1]).toHaveAccessibleName('Lọc theo Chưa gắn, 41 từ');
    });

    it('không vẽ chip "Chưa gắn" khi mọi từ đều đã có chủ đề', async () => {
      // Chip đếm 0 là một ô bấm vào ra danh sách rỗng.
      mockSearch([entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] })],
        { total: 128, untagged: 0, tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');
      await screen.findByRole('button', { name: /Lọc theo Tất cả/i });

      expect(screen.queryByRole('button', { name: /Chưa gắn/i })).not.toBeInTheDocument();
    });

    it('bấm "Chưa gắn" lọc theo untagged và KHÔNG kèm tag', async () => {
      // Backend trả 400 khi nhận cả `tag` lẫn `untagged=true` — hai điều kiện mâu thuẫn.
      mockSearch([
        entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }),
        entry(2, 'nebulous', 'mơ hồ', { tags: [] }),
      ], { total: 2, untagged: 1, tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');

      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Chưa gắn/i }));

      await waitFor(() => expect(lastSearch()).toMatchObject({ untagged: true, tag: null }));
      expect(await screen.findByText('nebulous')).toBeInTheDocument();
      expect(screen.queryByText('renewable')).not.toBeInTheDocument();
    });

    it('bấm "Tất cả" sau khi lọc "Chưa gắn" thì bỏ luôn điều kiện untagged', async () => {
      mockSearch([
        entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }),
        entry(2, 'nebulous', 'mơ hồ', { tags: [] }),
      ], { total: 2, untagged: 1, tags: TAGS });
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Chưa gắn/i }));
      await waitFor(() => expect(lastSearch().untagged).toBe(true));

      await userEvent.click(screen.getByRole('button', { name: /Lọc theo Tất cả/i }));

      await waitFor(() => expect(lastSearch()).toMatchObject({ untagged: false, tag: null }));
      expect(await screen.findByText('renewable')).toBeInTheDocument();
    });
  });

  /* ================= Hàng chip nạp lại sau khi đổi dữ liệu ================= */

  describe('hàng chip theo kịp dữ liệu vừa đổi', () => {
    /**
     * Mock CÓ TRẠNG THÁI: sửa/xoá đổi luôn phản hồi GET_VOCAB_TAGS của lượt gọi sau.
     *
     * Bắt buộc phải vậy, vì lỗi ở đây là "không gọi lại" — một mock trả hằng số thì gọi lại
     * hay không cũng ra đúng một màn hình, và test sẽ xanh cho cả bản hỏng.
     */
    function mockLiveTags(item: VocabEntryDto) {
      let current = item;
      let removed = false;
      const infoOf = (): VocabTagsResponse => (removed
        ? { total: 0, untagged: 0, tags: [] }
        : {
          total: 1,
          untagged: current.tags.length === 0 ? 1 : 0,
          tags: current.tags.map((tag) => ({ tag, count: 1, mastered: 0 })),
        });

      transportSend.mockImplementation(
        async (request: { type: string; meaningVi?: string | null; tags?: string[] | null }) => {
          if (request.type === 'SEARCH_VOCAB') {
            const content = removed ? [] : [current];
            return { ok: true, data: {
              content, totalElements: content.length, totalPages: content.length, number: 0 } };
          }
          if (request.type === 'GET_VOCAB_TAGS') return { ok: true, data: infoOf() };
          if (request.type === 'UPDATE_VOCAB') {
            current = {
              ...current,
              meaningVi: request.meaningVi ?? current.meaningVi,
              tags: request.tags ?? current.tags,
            };
            return { ok: true, data: current };
          }
          if (request.type === 'DELETE_VOCAB') {
            removed = true;
            return { ok: true, data: null };
          }
          return { ok: true, data: null };
        },
      );
    }

    it('sửa chủ đề của một từ thì chip chủ đề MỚI xuất hiện ngay', async () => {
      // Không nạp lại thì người dùng vừa tạo ra một chủ đề mà không lọc theo nó được cho tới
      // khi đóng/mở lại panel.
      mockLiveTags(entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await screen.findByRole('button', { name: /Lọc theo Môi trường/i });

      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));
      // Nhãn đầy đủ: hàng chip ở trên cũng mang aria-label "Lọc theo chủ đề".
      const o = screen.getByLabelText(/Chủ đề \(cách nhau/i);
      await userEvent.clear(o);
      await userEvent.type(o, 'Năng lượng');
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }));

      expect(await screen.findByRole('button', { name: /Lọc theo Năng lượng/i }))
        .toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Lọc theo Môi trường/i }))
        .not.toBeInTheDocument();
    });

    it('xoá từ cuối cùng của một chủ đề thì chip mồ côi biến mất', async () => {
      // Chip còn lại sau khi chủ đề đó không còn từ nào là một ô bấm vào ra danh sách rỗng.
      mockLiveTags(entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await screen.findByRole('button', { name: /Lọc theo Môi trường/i });

      await userEvent.click(screen.getByRole('button', { name: /Xoá renewable/i }));

      await waitFor(() => expect(
        screen.queryByRole('button', { name: /Lọc theo Môi trường/i }),
      ).not.toBeInTheDocument());
    });

    it('đổi chủ đề TRONG LÚC đang lọc thì dòng đó rời khỏi danh sách', async () => {
      // Thay dòng tại chỗ (đường nhanh, không nhấp nháy) là ĐÚNG khi không lọc, nhưng khi
      // đang lọc theo chính chủ đề vừa bị gỡ thì nó để lại một dòng không còn khớp bộ lọc:
      // hàng chip tụt xuống "1 từ" trong khi danh sách vẫn hai dòng và dòng đếm vẫn "2 từ".
      // Hai con số nói ngược nhau trên cùng màn hình.
      const items = [
        entry(1, 'renewable', 'tái tạo', { tags: ['Môi trường'] }),
        entry(2, 'emission', 'khí thải', { tags: ['Môi trường'] }),
      ];
      transportSend.mockImplementation(
        async (request: { type: string; tag?: string | null; meaningVi?: string | null;
          tags?: string[] | null; id?: number }) => {
          if (request.type === 'SEARCH_VOCAB') {
            const matched = request.tag
              ? items.filter((e) => e.tags.includes(request.tag as string))
              : items;
            return { ok: true, data: {
              content: [...matched], totalElements: matched.length, totalPages: 1, number: 0 } };
          }
          if (request.type === 'GET_VOCAB_TAGS') {
            const tags = [...new Set(items.flatMap((e) => e.tags))]
              .map((tag) => ({
                tag,
                count: items.filter((e) => e.tags.includes(tag)).length,
                mastered: 0,
              }));
            return { ok: true, data: { total: items.length, untagged: 0, tags } };
          }
          if (request.type === 'UPDATE_VOCAB') {
            const at = items.findIndex((e) => e.id === request.id);
            items[at] = { ...items[at], tags: request.tags ?? items[at].tags };
            return { ok: true, data: items[at] };
          }
          return { ok: true, data: null };
        },
      );

      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(await screen.findByRole('button', { name: /Lọc theo Môi trường/i }));
      await waitFor(() => expect(lastSearch().tag).toBe('Môi trường'));

      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));
      const o = screen.getByLabelText(/Chủ đề \(cách nhau/i);
      await userEvent.clear(o);
      await userEvent.type(o, 'Kinh tế');
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }));

      // Dòng vừa đổi chủ đề không còn thuộc bộ lọc "Môi trường" nữa.
      await waitFor(() => expect(screen.queryByText('renewable')).not.toBeInTheDocument());
      expect(screen.getByText('emission')).toBeInTheDocument();
      expect(screen.getByText('1 từ')).toBeInTheDocument();
    });
  });

  /* ================= Thanh thành thạo + trạng thái ================= */

  describe('trạng thái ôn của từng dòng', () => {
    it('từ chưa có thẻ ôn hiện "chưa vào lịch ôn"', async () => {
      // Cả ba field SRS cùng null nghĩa là CHƯA CÓ THẺ, không phải "chưa tải xong".
      mockSearch([entry(1, 'renewable', 'tái tạo', {
        srsState: null, srsDueDate: null, srsRepetitions: null,
      })]);
      render(<VocabTab />);

      expect(await screen.findByText('chưa vào lịch ôn')).toBeInTheDocument();
    });

    it('từ đã ôn đủ nhiều hiện "đã thuộc"', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo', {
        srsState: 'REVIEW', srsDueDate: '2099-01-01', srsRepetitions: 6,
      })]);
      render(<VocabTab />);

      expect(await screen.findByText('đã thuộc')).toBeInTheDocument();
    });

    it('thẻ đang học lại hiện "hay quên"', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo', {
        srsState: 'RELEARNING', srsDueDate: '2026-08-15', srsRepetitions: 0,
      })]);
      render(<VocabTab />);

      expect(await screen.findByText('hay quên')).toBeInTheDocument();
    });
  });

  /* ================= Sửa một mục ================= */

  describe('sửa mục sổ từ', () => {
    /** Search + tags + UPDATE_VOCAB trả về bản ghi đã cập nhật. */
    function mockEditable(item: VocabEntryDto) {
      transportSend.mockImplementation(
        async (request: { type: string; meaningVi?: string | null; tags?: string[] | null }) => {
          if (request.type === 'SEARCH_VOCAB') {
            return { ok: true, data: {
              content: [item], totalElements: 1, totalPages: 1, number: 0 } };
          }
          if (request.type === 'GET_VOCAB_TAGS') {
            return { ok: true, data: { total: 1, untagged: 0, tags: [] } };
          }
          if (request.type === 'UPDATE_VOCAB') {
            return { ok: true, data: {
              ...item,
              meaningVi: request.meaningVi ?? item.meaningVi,
              tags: request.tags ?? item.tags,
            } };
          }
          return { ok: true, data: null };
        },
      );
    }

    function updateCalls() {
      return transportSend.mock.calls
        .map((call) => call[0] as { type: string })
        .filter((request) => request.type === 'UPDATE_VOCAB');
    }

    it('bấm Sửa mở form điền sẵn nghĩa và chủ đề hiện tại', async () => {
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');

      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      expect(screen.getByLabelText(/Nghĩa tiếng Việt/i)).toHaveValue('tái tạo');
      expect(screen.getByLabelText(/Chủ đề/i)).toHaveValue('environment');
    });

    it('sửa nghĩa rồi lưu gửi UPDATE_VOCAB và cập nhật dòng tại chỗ', async () => {
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      const o = screen.getByLabelText(/Nghĩa tiếng Việt/i);
      await userEvent.clear(o);
      await userEvent.type(o, 'có thể tái tạo');
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }));

      expect(await screen.findByText('có thể tái tạo')).toBeInTheDocument();
      expect(updateCalls()[0]).toMatchObject({ id: 1, meaningVi: 'có thể tái tạo' });
    });

    it('chỉ sửa nghĩa thì tags gửi null — KHÔNG động vào thẻ đã gắn', async () => {
      // PATCH: field vắng mặt = không đổi. Gửi lại mảng cũ cũng "đúng" nhưng biến một lượt
      // sửa nghĩa thành một lượt ghi đè thẻ — sai ngay khi hai thiết bị sửa cùng lúc.
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      const o = screen.getByLabelText(/Nghĩa tiếng Việt/i);
      await userEvent.clear(o);
      await userEvent.type(o, 'có thể tái tạo');
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }));

      await waitFor(() => expect(updateCalls()).toHaveLength(1));
      expect(updateCalls()[0]).toMatchObject({ tags: null });
    });

    it('gỡ hết chủ đề thì gửi mảng RỖNG, không phải null', async () => {
      // `[]` = thay thế toàn bộ bằng không có gì. `null` = giữ nguyên. Lẫn hai cái là không
      // còn cách nào gỡ một thẻ gắn nhầm.
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      await userEvent.clear(screen.getByLabelText(/Chủ đề/i));
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }));

      await waitFor(() => expect(updateCalls()).toHaveLength(1));
      expect(updateCalls()[0]).toMatchObject({ meaningVi: null, tags: [] });
    });

    it('nghĩa để trống thì khoá nút Lưu, không tốn một vòng request', async () => {
      // Backend trả 400 cho nghĩa rỗng. Chặn ở đây để người dùng thấy ngay chứ không phải
      // đợi một vòng mạng rồi nhận lỗi.
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      await userEvent.clear(screen.getByLabelText(/Nghĩa tiếng Việt/i));

      expect(screen.getByRole('button', { name: 'Lưu' })).toBeDisabled();
    });

    it('bấm Huỷ đóng form và KHÔNG gửi gì', async () => {
      mockEditable(entry(1, 'renewable', 'tái tạo'));
      render(<VocabTab />);
      await screen.findByText('renewable');
      await userEvent.click(screen.getByRole('button', { name: /Sửa renewable/i }));

      await userEvent.type(screen.getByLabelText(/Nghĩa tiếng Việt/i), 'xxx');
      await userEvent.click(screen.getByRole('button', { name: 'Huỷ' }));

      expect(screen.queryByLabelText(/Nghĩa tiếng Việt/i)).not.toBeInTheDocument();
      expect(updateCalls()).toHaveLength(0);
      expect(screen.getByText('tái tạo')).toBeInTheDocument();
    });
  });

>>>>>>> Stashed changes
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

  /* ================= Ô chủ đề nhiều màu (thiết kế 1b) ================= */

  describe('ô chủ đề', () => {
    const BA_CHU_DE: VocabTagsResponse = {
      total: 128,
      untagged: 41,
      tags: [
        { tag: 'Môi trường', count: 24, mastered: 17 },
        { tag: 'Giáo dục', count: 19, mastered: 10 },
        { tag: 'Kinh tế', count: 17, mastered: 6 },
        { tag: 'Y tế', count: 8, mastered: 8 },
      ],
    };

    it('vẽ tối đa BA ô, theo thứ tự backend trả về', async () => {
      // Backend sắp `count DESC, tag ASC` — thứ tự đó là hợp đồng, client KHÔNG sắp lại.
      mockSearch([entry(1, 'renewable', 'tái tạo')], BA_CHU_DE);
      render(<VocabTab />);
      await screen.findByText('renewable');

      const o = await screen.findAllByRole('button', { name: /^Chủ đề/ });
      expect(o).toHaveLength(3);
      expect(o[0]).toHaveAccessibleName(/Môi trường/);
      expect(o[2]).toHaveAccessibleName(/Kinh tế/);
    });

    it('mỗi ô nói số từ và mức thành thạo', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], BA_CHU_DE);
      render(<VocabTab />);
      await screen.findByText('renewable');

      expect(await screen.findByRole('button', { name: 'Chủ đề Môi trường, 24 từ, thành thạo 71%' }))
        .toBeInTheDocument();
    });

    it('bấm một ô là lọc theo chủ đề đó', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], BA_CHU_DE);
      render(<VocabTab />);
      await screen.findByText('renewable');

      await userEvent.click(await screen.findByRole('button', { name: /^Chủ đề Giáo dục/ }));

      await waitFor(() => expect(lastSearch()).toMatchObject({ tag: 'Giáo dục', page: 0 }));
    });

    it('sổ chưa có chủ đề nào thì không vẽ ô rỗng', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], { tags: [] });
      render(<VocabTab />);
      await screen.findByText('renewable');

      expect(screen.queryByRole('button', { name: /^Chủ đề/ })).not.toBeInTheDocument();
    });

    it('đang lọc theo chủ đề thì tiêu đề nhóm nói mức thành thạo của chủ đề đó', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], BA_CHU_DE);
      render(<VocabTab />);
      await screen.findByText('renewable');

      await userEvent.click(await screen.findByRole('button', { name: /^Chủ đề Kinh tế/ }));

      expect(await screen.findByText('thành thạo 35%')).toBeInTheDocument();
    });

    it('không lọc chủ đề nào thì không có tiêu đề nhóm', async () => {
      mockSearch([entry(1, 'renewable', 'tái tạo')], BA_CHU_DE);
      render(<VocabTab />);
      await screen.findByText('renewable');

      expect(screen.queryByText(/^thành thạo/)).not.toBeInTheDocument();
    });
  });
});
