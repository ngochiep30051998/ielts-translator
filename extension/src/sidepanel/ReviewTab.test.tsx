import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewTab } from './ReviewTab';
import type { CardDto } from '../shared/types';

function card(id: number, term: string): CardDto {
  return {
    id, vocabEntryId: id * 10, term, ipa: '/test/', pos: 'verb',
    meaningVi: `nghĩa của ${term}`, definitionEn: null, cefr: null, bandLevel: null,
    collocations: [], examples: [], state: 'NEW', dueDate: '2026-08-06',
    // Mồi nhử cố ý KHÔNG chứa term làm chuỗi con — nếu chứa thì phép so chuỗi trong
    // test sẽ dính nhầm mồi nhử và test "chọn đúng" trở nên vô nghĩa.
    viDistractors: [`sai một ${id}`, `sai hai ${id}`, `sai ba ${id}`],
    enDistractors: [`alpha${id}`, `beta${id}`, `gamma${id}`],
  };
}

/** Nút lựa chọn mở đầu bằng số thứ tự (cũng là phím tắt) — cắt đi để so đúng nội dung. */
function optionText(button: HTMLElement): string {
  return (button.textContent ?? '').replace(/^\d+\s*/, '');
}

/** Đáp án đúng là meaningVi (chiều EN → VI) hoặc term (chiều VI → EN), tuỳ lượt bốc. */
function isCorrectFor(term: string, button: HTMLElement): boolean {
  const text = optionText(button);
  return text === `nghĩa của ${term}` || text === term;
}

const OK_REVIEW = {
  ok: true, data: { nextDueDate: '2026-08-07', intervalDays: 1, easeFactor: 2.5 },
};

/** Giả lập service worker: hàng đợi cho GET_DUE_CARDS, kết quả chấm cho SUBMIT_REVIEW. */
function mockQueue(cards: CardDto[] | { ok: false; error: unknown }, review: unknown = OK_REVIEW) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      if (request.type === 'GET_DUE_CARDS') {
        return Array.isArray(cards) ? { ok: true, data: cards } : cards;
      }
      if (request.type === 'SUBMIT_REVIEW') return review;
      return { ok: true, data: null };
    },
  );
}

function submittedReviews() {
  return (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mock.calls
    .map((call) => call[0])
    .filter((request: { type: string }) => request.type === 'SUBMIT_REVIEW');
}

describe('ReviewTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await chrome.storage.local.clear();
  });

  it('hiện bốn lựa chọn và không lộ đáp án ở chỗ nào khác', async () => {
    mockQueue([card(1, 'mitigate')]);

    render(<ReviewTab />);

    const options = await screen.findAllByRole('button', { name: /^\d/ });
    expect(options).toHaveLength(4);
  });

  it('chiều VI → EN không lộ term và không có nút phát âm', async () => {
    // random cố định 0.99 đẩy buildQuestion sang chiều VI_EN.
    // Khôi phục thủ công ở cuối test: vi.clearAllMocks() KHÔNG gỡ spy, để rò rỉ thì mọi
    // test sau đều bị ép sang một chiều duy nhất.
    const randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0.99);
    mockQueue([card(1, 'mitigate')]);

    render(<ReviewTab />);
    await screen.findAllByRole('button', { name: /^\d/ });

    expect(screen.getByText('nghĩa của mitigate')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /phát âm/i })).not.toBeInTheDocument();

    randomSpy.mockRestore();
  });

  it('chọn đúng thật nhanh thì gửi SUBMIT_REVIEW mức EASY', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    const correct = options.find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(correct);

    expect(submittedReviews()).toHaveLength(1);
    expect(submittedReviews()[0]).toMatchObject({ cardId: 1, rating: 'EASY' });
  });

  it('chọn sai thì gửi mức AGAIN', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    const wrong = options.find((b) => !isCorrectFor('mitigate', b))!;
    await userEvent.click(wrong);

    expect(submittedReviews()[0]).toMatchObject({ cardId: 1, rating: 'AGAIN' });
  });

  it('một thẻ chỉ gửi đúng một SUBMIT_REVIEW dù bấm thêm lựa chọn khác', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    await userEvent.click(options[0]);
    await userEvent.click(options[1]);
    await userEvent.click(options[2]);

    expect(submittedReviews()).toHaveLength(1);
  });

  it('chọn xong mới hiện phần chi tiết và nút Tiếp', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    expect(screen.queryByRole('button', { name: /tiếp/i })).not.toBeInTheDocument();

    const options = await screen.findAllByRole('button', { name: /^\d/ });
    await userEvent.click(options[0]);

    expect(screen.getByRole('button', { name: /tiếp/i })).toBeInTheDocument();
  });

  it('bấm Tiếp thì sang thẻ sau', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    await userEvent.click(options[0]);
    await userEvent.click(screen.getByRole('button', { name: /tiếp/i }));

    expect(await screen.findByText('2/2')).toBeInTheDocument();
  });

  it('SUBMIT_REVIEW lỗi thì giữ nguyên thẻ và có nút Thử lại', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')],
      { ok: false, error: { code: 'INTERNAL', message: 'Backend chết', retryable: true } });

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    await userEvent.click(options[0]);

    expect(await screen.findByText(/backend chết/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /thử lại/i })).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    // Chưa chấm được thì không cho đi tiếp, bỏ qua lúc này là mất luôn lượt chấm
    expect(screen.queryByRole('button', { name: /^tiếp$/i })).not.toBeInTheDocument();
  });

  it('hàng đợi rỗng hiện empty state', async () => {
    mockQueue([]);

    render(<ReviewTab />);

    expect(await screen.findByText(/không còn thẻ nào đến hạn/i)).toBeInTheDocument();
  });

  it('thẻ không dựng được câu hỏi thì bị bỏ qua và KHÔNG gửi SUBMIT_REVIEW', async () => {
    const bare: CardDto = { ...card(1, 'mitigate'), viDistractors: [], enDistractors: [] };
    mockQueue([bare]);

    render(<ReviewTab />);

    expect(await screen.findByText(/chưa tạo được câu hỏi/i)).toBeInTheDocument();
    expect(submittedReviews()).toHaveLength(0);
  });

  it('nạp hàng đợi theo đúng hạn mức từ mới trong cài đặt', async () => {
    mockQueue([card(1, 'mitigate')]);
    await chrome.storage.local.set({ settings: { newWordsPerDay: 7 } });

    render(<ReviewTab />);
    await screen.findAllByRole('button', { name: /^\d/ });

    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'GET_DUE_CARDS', newLimit: 7 }),
    );
  });
});
