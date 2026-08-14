import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewTab } from './ReviewTab';
import type { CardDto } from '../types';
import { transportSend } from '../../vitest.setup';
import { FALLBACK_SETTINGS, setSettingsProvider } from '../settings';

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
  transportSend.mockImplementation(
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
  return transportSend.mock.calls
    .map((call) => call[0])
    .filter((request: { type: string }) => request.type === 'SUBMIT_REVIEW');
}

/** Ghi lại mọi message gửi đi để đếm và kiểm thứ tự. */
function mockWithLog(cards: CardDto[], practice: CardDto[] = []) {
  const sent: { type: string; cardId?: number }[] = [];
  transportSend.mockImplementation(
    async (request: { type: string; cardId?: number }) => {
      sent.push({ type: request.type, cardId: request.cardId });
      if (request.type === 'GET_DUE_CARDS') return { ok: true, data: cards };
      if (request.type === 'GET_PRACTICE_CARDS') return { ok: true, data: practice };
      if (request.type === 'SUBMIT_REVIEW') return OK_REVIEW;
      return { ok: true, data: null };
    },
  );
  return sent;
}

/** Nút lựa chọn mở đầu bằng số thứ tự. Trả nút SAI cho thẻ `term`. */
async function nutSai(term: string): Promise<HTMLElement> {
  const nut = (await screen.findAllByRole('button')).find(
    (b) => /^\d/.test(b.textContent ?? '') && !isCorrectFor(term, b),
  );
  if (!nut) throw new Error(`Không tìm thấy nút sai cho "${term}"`);
  return nut;
}

describe('ReviewTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
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
    // Chọn ĐÚNG một cách tất định (không phải options[0]): từ khi thẻ trả lời sai chèn
    // lại vào xấp, bấm trúng nút sai sẽ làm questions.length tăng lên 3 và phá vỡ '2/2'.
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')]);

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    const correct = options.find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(correct);
    await userEvent.click(screen.getByRole('button', { name: /tiếp/i }));

    expect(await screen.findByText('2/2')).toBeInTheDocument();
  });

  it('SUBMIT_REVIEW lỗi thì giữ nguyên thẻ và có nút Thử lại', async () => {
    mockQueue([card(1, 'mitigate'), card(2, 'resilient')],
      { ok: false, error: { code: 'INTERNAL', message: 'Backend chết', retryable: true } });

    render(<ReviewTab />);
    const options = await screen.findAllByRole('button', { name: /^\d/ });
    // Chọn ĐÚNG một cách tất định — lý do như test "bấm Tiếp" ở trên: chọn sai sẽ chèn
    // lại thẻ và đổi tổng số câu, phá '1/2'. Test này nhắm vào việc hiển thị lỗi/Thử lại,
    // không phải nhánh đúng/sai.
    const correct = options.find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(correct);

    expect(await screen.findByText(/backend chết/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /thử lại/i })).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    // Chưa chấm được thì không cho đi tiếp, bỏ qua lúc này là mất luôn lượt chấm
    expect(screen.queryByRole('button', { name: /^tiếp$/i })).not.toBeInTheDocument();
  });

  it('SUBMIT_REVIEW lỗi thì Thử lại vẫn gửi SUBMIT_REVIEW, không tụt sang SUBMIT_PRACTICE', async () => {
    // Đánh dấu "đã gửi lượt theo lịch" TRƯỚC KHI biết nó có tới nơi không sẽ làm lượt Thử
    // lại đi nhầm sang nhánh SUBMIT_PRACTICE — lịch SM-2 của thẻ đó im lặng không bao giờ
    // được cập nhật trong buổi ấy, dù người dùng đã bấm Thử lại thành công.
    const sent: { type: string; cardId?: number }[] = [];
    let reviewAttempts = 0;
    transportSend.mockImplementation(
      async (request: { type: string; cardId?: number }) => {
        sent.push({ type: request.type, cardId: request.cardId });
        if (request.type === 'GET_DUE_CARDS') return { ok: true, data: [card(1, 'mitigate')] };
        if (request.type === 'SUBMIT_REVIEW') {
          reviewAttempts += 1;
          // Lần gửi đầu hỏng vì mạng, lần thứ hai (qua nút Thử lại) mới thành công.
          return reviewAttempts === 1
            ? { ok: false, error: { code: 'INTERNAL', message: 'Backend chết', retryable: true } }
            : OK_REVIEW;
        }
        return { ok: true, data: null };
      },
    );

    render(<ReviewTab />);
    const correct = (await screen.findAllByRole('button')).find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(correct);
    await userEvent.click(await screen.findByRole('button', { name: /thử lại/i }));

    expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(2);
    expect(sent.filter((s) => s.type === 'SUBMIT_PRACTICE')).toHaveLength(0);
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
    setSettingsProvider(async () => ({ ...FALLBACK_SETTINGS, newWordsPerDay: 7 }));

    render(<ReviewTab />);
    await screen.findAllByRole('button', { name: /^\d/ });

    expect(transportSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'GET_DUE_CARDS', newLimit: 7 }),
    );
  });

  it('trả lời sai rồi trả lời lại gửi đúng một SUBMIT_REVIEW rồi một SUBMIT_PRACTICE', async () => {
    // QUY TẮC TRUNG TÂM của cả tính năng: mỗi thẻ đóng góp NHIỀU NHẤT MỘT lượt SCHEDULED
    // trong một buổi. Mọi lần hiện lại đều là PRACTICE.
    //
    // Nếu lượt thứ hai cũng gửi SUBMIT_REVIEW, nó tính tiếp từ trạng thái vừa lapse và đẩy
    // interval lên lại — tức là trả lời đúng ở lần thứ hai XOÁ MẤT dấu vết đã quên.
    //
    // Dùng ĐÚNG MỘT thẻ: với xấp 1 phần tử, thẻ chèn lại rơi vào index 1 nên chỉ cần bấm
    // "Tiếp" một lần là nó quay lại. Ba thẻ thì phải bấm ba lần và test dài gấp đôi mà không
    // kiểm thêm được gì.
    const sent = mockWithLog([card(1, 'mitigate')]);
    render(<ReviewTab />);

    await userEvent.click(await nutSai('mitigate'));
    await userEvent.click(screen.getByRole('button', { name: 'Tiếp' }));
    await userEvent.click(await nutSai('mitigate'));

    expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(1);
    expect(sent.filter((s) => s.type === 'SUBMIT_PRACTICE')).toHaveLength(1);
    // Thứ tự cũng là hợp đồng: lượt theo lịch phải đi TRƯỚC.
    const chiHaiLoai = sent
      .map((s) => s.type)
      .filter((t) => t === 'SUBMIT_REVIEW' || t === 'SUBMIT_PRACTICE');
    expect(chiHaiLoai).toEqual(['SUBMIT_REVIEW', 'SUBMIT_PRACTICE']);
  });

  it('thẻ trả lời sai hiện lại trong xấp', async () => {
    // Bộ đếm render dạng `{index + 1}/{questions.length}` (ReviewTab.tsx:147).
    mockWithLog([card(1, 'mitigate'), card(2, 'robust')]);
    render(<ReviewTab />);
    expect(await screen.findByText('1/2')).toBeInTheDocument();

    await userEvent.click(await nutSai('mitigate'));

    // Xấp 2 thẻ; sai một thẻ thì tổng phải thành 3, vị trí hiện tại vẫn là 1.
    expect(screen.getByText('1/3')).toBeInTheDocument();
  });

  it('hết hàng đợi thì hiện nút Luyện thêm', async () => {
    mockWithLog([]);
    render(<ReviewTab />);

    expect(await screen.findByRole('button', { name: 'Luyện thêm' })).toBeInTheDocument();
  });

  it('vào chế độ luyện thì hiện dòng cảnh báo không ảnh hưởng lịch', async () => {
    mockWithLog([], [card(9, 'resilient')]);
    render(<ReviewTab />);

    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

    expect(await screen.findByText(/không ảnh hưởng lịch ôn/)).toBeInTheDocument();
  });

  it('trả lời trong chế độ luyện chỉ gửi SUBMIT_PRACTICE', async () => {
    const sent = mockWithLog([], [card(9, 'resilient'), card(10, 'coherent')]);
    render(<ReviewTab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

    const nut = (await screen.findAllByRole('button')).find((b) => /^\d/.test(b.textContent ?? ''));
    await userEvent.click(nut!);

    expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(0);
    expect(sent.filter((s) => s.type === 'SUBMIT_PRACTICE')).toHaveLength(1);
  });

  it('quay lại từ chế độ luyện thì ôn cùng thẻ đó vẫn gửi SUBMIT_REVIEW', async () => {
    // `load()` xoá `scheduledSent` mỗi lần nạp. Mất dòng đó thì thẻ đã ôn trong buổi sẽ
    // vĩnh viễn đi nhánh PRACTICE, kể cả sau khi quay về chế độ theo lịch — lịch SM-2 của
    // nó không bao giờ được cập nhật nữa trong buổi ấy. Đi qua ĐÚNG nút "Quay lại" (không
    // gọi load() trực tiếp) để test canh luôn cả sự tồn tại của nút.
    const sent = mockWithLog([card(1, 'mitigate')], [card(1, 'mitigate')]);
    render(<ReviewTab />);

    // Lượt 1: ôn theo lịch, đúng → SUBMIT_REVIEW.
    const firstCorrect = (await screen.findAllByRole('button')).find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(firstCorrect);
    await userEvent.click(screen.getByRole('button', { name: 'Tiếp' }));

    // Hàng đợi lịch chỉ có một thẻ nên giờ đã hết — sang chế độ luyện.
    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

    // Trả lời thẻ trong chế độ luyện — đúng/sai không quan trọng ở bước này.
    const practiceOption = (await screen.findAllByRole('button')).find((b) => /^\d/.test(b.textContent ?? ''))!;
    await userEvent.click(practiceOption);

    // Quay lại chế độ theo lịch qua ĐÚNG nút "Quay lại".
    await userEvent.click(screen.getByRole('button', { name: 'Quay lại' }));

    // Lượt 2: cùng thẻ, ôn lại theo lịch, đúng → phải LẠI là SUBMIT_REVIEW, không tụt
    // sang SUBMIT_PRACTICE vì scheduledSent còn nhớ cardId từ lượt 1.
    const secondCorrect = (await screen.findAllByRole('button')).find((b) => isCorrectFor('mitigate', b))!;
    await userEvent.click(secondCorrect);

    expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(2);
  });

  it('Quay lại thất bại thì vẫn ở chế độ luyện, trả lời không gửi SUBMIT_REVIEW', async () => {
    // Kịch bản C1: đang ở chế độ luyện → bấm Quay lại → GET_DUE_CARDS lỗi mạng. Nếu `mode`
    // đổi thành 'scheduled' trong khi xấp thẻ vẫn là thẻ luyện (và scheduledSent bị xoá
    // theo), lượt trả lời sau đó sẽ bị tính là "lượt đầu tiên theo lịch" và bắn SUBMIT_REVIEW
    // cho một thẻ luyện — đẩy lịch SM-2 của nó dù bối cảnh là luyện thêm.
    const sent: { type: string; cardId?: number }[] = [];
    let dueCalls = 0;
    transportSend.mockImplementation(
      async (request: { type: string; cardId?: number }) => {
        sent.push({ type: request.type, cardId: request.cardId });
        if (request.type === 'GET_DUE_CARDS') {
          dueCalls += 1;
          // Lượt nạp đầu tiên (lúc mở panel) thành công với hàng đợi rỗng để hiện nút
          // "Luyện thêm". Lượt thứ hai — do bấm "Quay lại" — hỏng vì mạng.
          return dueCalls === 1
            ? { ok: true, data: [] }
            : { ok: false, error: { code: 'GEMINI_UNAVAILABLE', message: 'Mất mạng', retryable: true } };
        }
        if (request.type === 'GET_PRACTICE_CARDS') return { ok: true, data: [card(9, 'resilient')] };
        return { ok: true, data: null };
      },
    );

    render(<ReviewTab />);

    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));
    await screen.findByText(/không ảnh hưởng lịch ôn/);

    await userEvent.click(screen.getByRole('button', { name: 'Quay lại' }));

    // Quay lại hỏng — panel vẫn phải ở chế độ luyện với ĐÚNG xấp thẻ luyện cũ.
    expect(await screen.findByText(/không ảnh hưởng lịch ôn/)).toBeInTheDocument();

    const nut = (await screen.findAllByRole('button')).find((b) => /^\d/.test(b.textContent ?? ''));
    await userEvent.click(nut!);

    expect(sent.filter((s) => s.type === 'SUBMIT_REVIEW')).toHaveLength(0);
  });

  it('xấp luyện rỗng hiện thông báo riêng cho chế độ luyện kèm nút Quay lại', async () => {
    mockWithLog([], []);
    render(<ReviewTab />);

    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));

    // KHÔNG được đứng yên (triệu chứng 1 của I2) và KHÔNG được lặp lại chữ "đến hạn" —
    // đó là ngôn ngữ của chế độ theo lịch, sai bối cảnh khi đang luyện thêm.
    expect(await screen.findByText(/luyện thêm/i)).toBeInTheDocument();
    expect(screen.queryByText(/đến hạn/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Quay lại' })).toBeInTheDocument();
  });

  it('nút Tải lại ở chế độ luyện nạp lại đúng chế độ luyện, không tụt về theo lịch', async () => {
    const sent = mockWithLog([], []);
    render(<ReviewTab />);

    await userEvent.click(await screen.findByRole('button', { name: 'Luyện thêm' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Tải lại' }));

    const goiSau = sent.filter((s) => s.type === 'GET_DUE_CARDS' || s.type === 'GET_PRACTICE_CARDS');
    expect(goiSau.map((s) => s.type)).toEqual([
      'GET_DUE_CARDS', 'GET_PRACTICE_CARDS', 'GET_PRACTICE_CARDS',
    ]);
  });
});
