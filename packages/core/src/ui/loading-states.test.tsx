import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import type { TranslatePayload, TranslateResult, VocabEntryDto } from '../types';
import { transportSend } from '../../vitest.setup';

/**
 * Trạng thái chờ của các thao tác đổi dữ liệu.
 *
 * Điểm của những test này KHÔNG phải là "có hiện vòng quay không" — mà là **bấm hai lần chỉ
 * gửi một request**. Trên điện thoại, bấm nhanh hơn một nhịp render là chuyện thường, và hậu
 * quả thật: lưu hai lần, xoá hai lần (lượt sau nhận NOT_FOUND nên người dùng thấy một lỗi
 * cho đúng việc họ vừa làm thành công), hoặc hai lượt nạp trang đua nhau.
 */

/** Promise mà test tự quyết định lúc nào cho xong — để bắt được trạng thái ĐANG chờ. */
function treo<T>() {
  let xong!: (value: T) => void;
  const promise = new Promise<T>((resolve) => {
    xong = resolve;
  });
  return { promise, xong };
}

/** Payload ĐỦ field: `PayloadViews` map thẳng `collocations`/`examples`, thiếu là ném. */
const KET_QUA: TranslateResult = {
  direction: 'EN_VI',
  mode: 'WORD',
  cached: false,
  sourceText: 'mitigate',
  payload: {
    term: 'mitigate', lemma: 'mitigate', pos: 'verb', ipa: '/ˈmɪtɪɡeɪt/',
    meaning_vi: 'giảm nhẹ', definition_en: 'make less severe', cefr: 'C1',
    band_level: '7.0', register: 'academic',
    collocations: ['mitigate risk'],
    examples: [{ en: 'Measures to mitigate risk.', vi: 'Biện pháp giảm nhẹ rủi ro.' }],
    synonyms: [{ term: 'alleviate', band: '7.5' }],
  } as unknown as TranslatePayload,
};

/** Bản ghi sổ từ tối thiểu để VocabTab render được một dòng: có `tags` và ba field SRS. */
const TU: VocabEntryDto = {
  id: 7,
  term: 'mitigate',
  meaningVi: 'giảm nhẹ',
  tags: [],
  srsState: null,
  srsDueDate: null,
  srsRepetitions: null,
} as unknown as VocabEntryDto;

function trangSoTu(content: VocabEntryDto[], totalPages = 1) {
  return { ok: true, data: { content, totalElements: content.length, totalPages, number: 0 } };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('TranslateTab — lưu từ', () => {
  it('bấm Lưu hai lần chỉ gửi MỘT lượt SAVE_WORD', async () => {
    const cho = treo<unknown>();
    transportSend.mockReturnValue(cho.promise);

    render(
      <TranslateTab draft="" onDraftChange={() => {}} result={KET_QUA} onResult={() => {}} loaded />,
    );
    const nut = screen.getByRole('button', { name: /Lưu từ/ });

    await userEvent.click(nut);
    await userEvent.click(nut);

    expect(transportSend).toHaveBeenCalledTimes(1);
    cho.xong({ ok: true, data: { id: 1, alreadyExists: false } });
  });

  it('trong lúc chờ thì nút đổi nhãn và mang aria-busy', async () => {
    const cho = treo<unknown>();
    transportSend.mockReturnValue(cho.promise);

    render(
      <TranslateTab draft="" onDraftChange={() => {}} result={KET_QUA} onResult={() => {}} loaded />,
    );
    await userEvent.click(screen.getByRole('button', { name: /Lưu từ/ }));

    const dangLuu = screen.getByRole('button', { name: /Đang lưu/ });
    expect(dangLuu).toBeDisabled();
    expect(dangLuu).toHaveAttribute('aria-busy', 'true');

    cho.xong({ ok: true, data: { id: 1, alreadyExists: false } });
    expect(await screen.findByRole('button', { name: /Lưu từ/ })).toBeEnabled();
  });
});

describe('VocabTab — xoá từ', () => {
  it('bấm ✕ hai lần chỉ gửi MỘT lượt DELETE_VOCAB', async () => {
    const cho = treo<unknown>();
    transportSend.mockImplementation(async (req: { type: string }) => {
      if (req.type === 'SEARCH_VOCAB') return trangSoTu([TU]);
      if (req.type === 'GET_VOCAB_TAGS') {
        return { ok: true, data: { total: 1, untagged: 1, tags: [] } };
      }
      return cho.promise;
    });

    render(<VocabTab />);
    const nut = await screen.findByRole('button', { name: 'Xoá mitigate' });

    await userEvent.click(nut);
    await userEvent.click(nut);

    const soLanXoa = transportSend.mock.calls.filter(
      (c) => (c[0] as { type: string }).type === 'DELETE_VOCAB',
    ).length;
    expect(soLanXoa).toBe(1);
    cho.xong({ ok: true, data: null });
  });

  it('đang xoá thì chính dòng đó mang aria-busy', async () => {
    const cho = treo<unknown>();
    transportSend.mockImplementation(async (req: { type: string }) => {
      if (req.type === 'SEARCH_VOCAB') return trangSoTu([TU]);
      if (req.type === 'GET_VOCAB_TAGS') {
        return { ok: true, data: { total: 1, untagged: 1, tags: [] } };
      }
      return cho.promise;
    });

    render(<VocabTab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Xoá mitigate' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Xoá mitigate' })).toHaveAttribute(
        'aria-busy',
        'true',
      ),
    );
    cho.xong({ ok: true, data: null });
  });
});

describe('VocabTab — xuất CSV', () => {
  it('đi qua EXPORT_VOCAB_CSV chứ KHÔNG mở window tới backend', async () => {
    // `window.open` không mang được token Bearer lẫn header X-IELTS-Web, nên cách cũ luôn
    // nhận 401 — người dùng tải về một trang JSON lỗi thay vì file.
    const openMock = vi.fn();
    vi.stubGlobal('open', openMock);
    // jsdom chưa có createObjectURL.
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => {} });

    transportSend.mockImplementation(async (req: { type: string }) => {
      if (req.type === 'SEARCH_VOCAB') return trangSoTu([TU]);
      if (req.type === 'GET_VOCAB_TAGS') {
        return { ok: true, data: { total: 1, untagged: 1, tags: [] } };
      }
      return { ok: true, data: 'term,meaning\nmitigate,giảm nhẹ\n' };
    });

    render(<VocabTab />);
    await userEvent.click(await screen.findByRole('button', { name: /CSV/ }));

    await waitFor(() =>
      expect(
        transportSend.mock.calls.some(
          (c) => (c[0] as { type: string }).type === 'EXPORT_VOCAB_CSV',
        ),
      ).toBe(true),
    );
    expect(openMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
