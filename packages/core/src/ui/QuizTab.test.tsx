import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QuizTab } from './QuizTab';
import type { AnswerResult, QuizExplanation, QuizItemDto } from '../types';
import { transportSend } from '../../vitest.setup';

/* ---------- Dữ liệu mẫu, bám đúng bảng field theo type của hợp đồng ---------- */

function fillBlank(id: number): QuizItemDto {
  return {
    id,
    type: 'FILL_BLANK',
    vocabEntryId: id * 10,
    // null là CỐ Ý: với FILL_BLANK thì term chính là đáp án, backend không gửi.
    term: null,
    question: 'Điền từ còn thiếu vào chỗ trống. Gợi ý: làm nhẹ bớt tác động',
    sentence: 'Governments must ___ the effects of climate change.',
    options: null,
  };
}

function collocation(id: number, options: string[]): QuizItemDto {
  return {
    id,
    type: 'COLLOCATION_CHOICE',
    vocabEntryId: id * 10,
    term: 'mitigate',
    question: 'Cụm nào đi được với "mitigate"?',
    sentence: null,
    options,
  };
}

function freeWrite(id: number): QuizItemDto {
  return {
    id,
    type: 'FREE_WRITE',
    vocabEntryId: id * 10,
    term: 'resilient',
    question: 'Viết một câu tiếng Anh dùng từ "resilient" (kiên cường).',
    sentence: null,
    options: null,
  };
}

const CORRECT: AnswerResult = {
  correct: true, score: 100, feedback: 'Chính xác.', improvedVersion: null,
};

const EXPLANATION: QuizExplanation = {
  explanation: '"mitigate" đi với "impact"; "reduce" nhạt hơn.',
  answerMeaning: 'mitigate = giảm nhẹ',
  sentenceEn: 'Governments must mitigate the effects of climate change.',
  sentenceVi: 'Các chính phủ phải giảm nhẹ tác động của biến đổi khí hậu.',
};

interface Sent { type: string; [key: string]: unknown }

/**
 * Giả lập service worker. `generate` nhận nguyên message để test tự quyết định
 * loại nào thành công, loại nào hỏng — đó là cách duy nhất dựng được ca hỏng-một-phần.
 */
function mockBackend(opts: {
  generate?: (request: Sent) => unknown;
  answer?: (request: Sent) => unknown;
  explain?: (request: Sent) => unknown;
} = {}) {
  transportSend.mockImplementation(
    async (request: Sent) => {
      if (request.type === 'GENERATE_QUIZ') {
        return opts.generate ? opts.generate(request) : { ok: true, data: [] };
      }
      if (request.type === 'ANSWER_QUIZ') {
        return opts.answer ? opts.answer(request) : { ok: true, data: CORRECT };
      }
      if (request.type === 'EXPLAIN_QUIZ') {
        return opts.explain ? opts.explain(request) : { ok: true, data: EXPLANATION };
      }
      return { ok: true, data: null };
    },
  );
}

function sentOf(type: string): Sent[] {
  return transportSend.mock.calls
    .map((call) => call[0] as Sent)
    .filter((request) => request.type === type);
}

/** Nút lựa chọn mở đầu bằng số thứ tự — cắt đi để so đúng nội dung. */
function optionText(button: HTMLElement): string {
  return (button.textContent ?? '').replace(/^\d+\s*/, '');
}

function optionButtons(): HTMLElement[] {
  return screen.getAllByRole('button', { name: /^\d/ });
}

/** Bỏ tick mọi loại trừ loại muốn giữ, rồi bấm Tạo đề. */
async function generateOnly(keep: 'Điền từ' | 'Chọn cụm từ' | 'Tự viết câu') {
  for (const label of ['Điền từ', 'Chọn cụm từ', 'Tự viết câu'] as const) {
    if (label !== keep) await userEvent.click(screen.getByLabelText(label));
  }
  await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));
}

describe('QuizTab', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  /* ================= Chia số câu cho các loại (Q1) ================= */

  describe('chia số câu và gọi tuần tự', () => {
    it('10 câu chia cho ba loại thành 4/3/3, gửi đúng thứ tự cố định', async () => {
      mockBackend();

      render(<QuizTab />);
      await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

      await waitFor(() => expect(sentOf('GENERATE_QUIZ')).toHaveLength(3));
      expect(sentOf('GENERATE_QUIZ').map((r) => [r.quizType, r.count])).toEqual([
        ['FILL_BLANK', 4],
        ['COLLOCATION_CHOICE', 3],
        ['FREE_WRITE', 3],
      ]);
    });

    it('2 câu chia cho ba loại chỉ gửi 2 request — loại được chia 0 câu KHÔNG được gọi', async () => {
      mockBackend();

      render(<QuizTab />);
      const count = screen.getByLabelText('Số câu');
      await userEvent.clear(count);
      await userEvent.type(count, '2');
      await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

      await waitFor(() => expect(sentOf('GENERATE_QUIZ')).toHaveLength(2));
      expect(sentOf('GENERATE_QUIZ').map((r) => [r.quizType, r.count])).toEqual([
        ['FILL_BLANK', 1],
        ['COLLOCATION_CHOICE', 1],
      ]);
    });

    it('hiện tiến độ thật trong lúc chờ từng loại', async () => {
      let release!: (value: unknown) => void;
      transportSend.mockImplementation(
        async (request: Sent) => {
          if (request.type !== 'GENERATE_QUIZ') return { ok: true, data: null };
          if (request.quizType === 'FILL_BLANK') {
            return new Promise((resolve) => { release = resolve; });
          }
          return { ok: true, data: [] };
        },
      );

      render(<QuizTab />);
      await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

      // Loại đầu chưa trả về: tiến độ phải là 0/3, không phải spinner câm.
      expect(await screen.findByText('Đang sinh đề: 0/3')).toBeInTheDocument();

      release({ ok: true, data: [] });
      await waitFor(() => expect(sentOf('GENERATE_QUIZ')).toHaveLength(3));
    });

    it('gửi count chứ không gửi vocabIds — đúng một selector, không thì backend trả 400', async () => {
      mockBackend();

      render(<QuizTab />);
      await generateOnly('Điền từ');

      await waitFor(() => expect(sentOf('GENERATE_QUIZ')).toHaveLength(1));
      expect(sentOf('GENERATE_QUIZ')[0]).toMatchObject({ vocabIds: null, count: 10 });
    });
  });

  /* ================= R1 — thứ tự options là bất khả xâm phạm ================= */

  describe('COLLOCATION_CHOICE giữ nguyên thứ tự options', () => {
    const OPTIONS = ['take action', 'make action', 'do action', 'have action'];

    async function renderCollocation() {
      mockBackend({
        generate: (r) => (r.quizType === 'COLLOCATION_CHOICE'
          ? { ok: true, data: [collocation(5, OPTIONS)] }
          : { ok: true, data: [] }),
      });
      render(<QuizTab />);
      await generateOnly('Chọn cụm từ');
      await screen.findAllByRole('button', { name: /^\d/ });
    }

    it('bốn lựa chọn hiện ĐÚNG thứ tự backend gửi xuống', async () => {
      await renderCollocation();

      expect(optionButtons().map(optionText)).toEqual(OPTIONS);
    });

    it('bấm lựa chọn thứ ba gửi answer là index 0-based dạng chuỗi "2"', async () => {
      await renderCollocation();

      await userEvent.click(optionButtons()[2]);

      await waitFor(() => expect(sentOf('ANSWER_QUIZ')).toHaveLength(1));
      expect(sentOf('ANSWER_QUIZ')[0]).toMatchObject({ quizItemId: 5, answer: '2' });
    });

    it('bỏ qua được câu trắc nghiệm — không có nút này thì chỉ còn cách đoán bừa', async () => {
      // Loại này không có ô nhập nên cũng không có nút "Nộp". Thiếu "Bỏ qua" thì người
      // dùng buộc phải chọn liều, ghi một quiz_attempt rác và làm lệch tiêu chí xếp
      // ưu tiên ứng viên cho đề sau. Backend đã nhận chuỗi rỗng cho cả ba loại.
      await renderCollocation();

      await userEvent.click(screen.getByRole('button', { name: 'Bỏ qua' }));

      await waitFor(() => expect(sentOf('ANSWER_QUIZ')).toHaveLength(1));
      expect(sentOf('ANSWER_QUIZ')[0]).toMatchObject({ quizItemId: 5, answer: '' });
    });

    it('lỗi khi nộp thì KHÔNG bảo bấm "Nộp" — loại này không có nút đó', async () => {
      // Chỉ sai đường hồi phục: bảo người dùng bấm một nút không tồn tại trên màn hình.
      mockBackend({
        generate: (r) => (r.quizType === 'COLLOCATION_CHOICE'
          ? { ok: true, data: [collocation(5, OPTIONS)] }
          : { ok: true, data: [] }),
        answer: () => ({
          ok: false,
          error: { code: 'GEMINI_UNAVAILABLE', message: 'Backend đang bận.', retryable: true },
        }),
      });
      render(<QuizTab />);
      await generateOnly('Chọn cụm từ');
      await screen.findAllByRole('button', { name: /^\d/ });

      await userEvent.click(optionButtons()[1]);

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Chọn lại một đáp án để gửi lại.');
      expect(alert).not.toHaveTextContent('Bấm "Nộp"');
    });
  });

  /* ================= Hỏng một phần (Q2) ================= */

  it('một loại lỗi thì giữ nguyên câu của loại trước, hiện cảnh báo và VẪN làm được', async () => {
    mockBackend({
      generate: (r) => {
        if (r.quizType === 'FILL_BLANK') return { ok: true, data: [fillBlank(1)] };
        if (r.quizType === 'COLLOCATION_CHOICE') {
          return {
            ok: false,
            error: { code: 'PARSE_ERROR', message: 'AI trả về dữ liệu hỏng', retryable: false },
          };
        }
        return { ok: true, data: [] };
      },
    });

    render(<QuizTab />);
    await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

    expect(await screen.findByText(/Governments must ___/)).toBeInTheDocument();
    expect(screen.getByText(/AI trả về dữ liệu hỏng/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Từ cần điền'), 'mitigate');
    await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));

    await waitFor(() => expect(sentOf('ANSWER_QUIZ')).toHaveLength(1));
    expect(sentOf('ANSWER_QUIZ')[0]).toMatchObject({ quizItemId: 1, answer: 'mitigate' });
  });

  /* ================= FILL_BLANK với term null ================= */

  it('FILL_BLANK có term null vẫn render được câu chứa ___', async () => {
    mockBackend({
      generate: (r) => (r.quizType === 'FILL_BLANK'
        ? { ok: true, data: [fillBlank(1)] }
        : { ok: true, data: [] }),
    });

    render(<QuizTab />);
    await generateOnly('Điền từ');

    expect(await screen.findByText('Governments must ___ the effects of climate change.'))
      .toBeInTheDocument();
    // term là đáp án của loại này — lộ ra màn hình là bài quiz vô nghĩa.
    expect(screen.queryByText('mitigate')).not.toBeInTheDocument();
  });

  /* ================= Nút Nộp: chỉ khoá vì quá dài, không vì trống ================= */

  describe('nút Nộp', () => {
    async function renderFreeWrite() {
      mockBackend({
        generate: (r) => (r.quizType === 'FREE_WRITE'
          ? { ok: true, data: [freeWrite(9)] }
          : { ok: true, data: [] }),
      });
      render(<QuizTab />);
      await generateOnly('Tự viết câu');
      return screen.findByLabelText('Câu tiếng Anh của bạn');
    }

    it('1001 ký tự thì khoá nút Nộp, hiện số đếm và KHÔNG gửi message', async () => {
      const box = await renderFreeWrite();

      await userEvent.click(box);
      await userEvent.paste('x'.repeat(1001));

      expect(screen.getByText('1001/1000')).toBeInTheDocument();
      const submit = screen.getByRole('button', { name: 'Nộp' });
      expect(submit).toBeDisabled();

      await userEvent.click(submit);
      expect(sentOf('ANSWER_QUIZ')).toHaveLength(0);
    });

    it('đúng 1000 ký tự vẫn nộp được — giới hạn là "tối đa", không phải "dưới"', async () => {
      const box = await renderFreeWrite();

      await userEvent.click(box);
      await userEvent.paste('x'.repeat(1000));

      expect(screen.getByRole('button', { name: 'Nộp' })).toBeEnabled();
    });

    it('ô trống VẪN nộp được — bỏ qua câu là hành động học tập hợp lệ', async () => {
      // Backend nhận answer rỗng (@NotNull chứ không @NotBlank) và chấm 0 kèm
      // "Chưa trả lời.". Khoá nút ở đây là làm người học không bỏ qua được câu nào,
      // và câu đó còn quay lại ở đề sau như chưa từng làm.
      await renderFreeWrite();

      const submit = screen.getByRole('button', { name: 'Nộp' });
      expect(submit).toBeEnabled();

      await userEvent.click(submit);

      await waitFor(() => expect(sentOf('ANSWER_QUIZ')).toHaveLength(1));
      expect(sentOf('ANSWER_QUIZ')[0]).toMatchObject({ quizItemId: 9, answer: '' });
    });

    it('FILL_BLANK bỏ trống: gửi answer rỗng rồi hiện đúng feedback "Chưa trả lời."', async () => {
      // Đi hết vòng: UI gửi chuỗi rỗng → backend chấm 0 kèm "Chưa trả lời." → UI render.
      // Chặn cả hai đầu vì nhánh isBlank() phía backend chỉ sống được nếu UI chịu gửi
      // chuỗi rỗng; thêm lại `length > 0` là biến nhánh đó thành code chết.
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1)] }
          : { ok: true, data: [] }),
        answer: () => ({
          ok: true,
          data: { correct: false, score: 0, feedback: 'Chưa trả lời.', improvedVersion: null },
        }),
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');
      await screen.findByLabelText('Từ cần điền');

      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));

      await waitFor(() => expect(sentOf('ANSWER_QUIZ')).toHaveLength(1));
      expect(sentOf('ANSWER_QUIZ')[0]).toMatchObject({ quizItemId: 1, answer: '' });
      expect(await screen.findByText('Chưa trả lời.')).toBeInTheDocument();
      expect(screen.getByText(/0 điểm/)).toBeInTheDocument();
    });
  });

  /* ================= Chấm bài ================= */

  describe('kết quả chấm', () => {
    async function answerFreeWrite(result: AnswerResult) {
      mockBackend({
        generate: (r) => (r.quizType === 'FREE_WRITE'
          ? { ok: true, data: [freeWrite(9)] }
          : { ok: true, data: [] }),
        answer: () => ({ ok: true, data: result }),
      });
      render(<QuizTab />);
      await generateOnly('Tự viết câu');

      await userEvent.type(
        await screen.findByLabelText('Câu tiếng Anh của bạn'),
        'She stayed resilient.',
      );
      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));
    }

    it('improvedVersion null thì KHÔNG render khối câu viết lại', async () => {
      await answerFreeWrite({
        correct: true, score: 90, feedback: 'Câu đúng ngữ pháp.', improvedVersion: null,
      });

      expect(await screen.findByText('Câu đúng ngữ pháp.')).toBeInTheDocument();
      expect(screen.queryByText(/câu viết lại/i)).not.toBeInTheDocument();
    });

    it('improvedVersion có giá trị thì hiện khối câu viết lại', async () => {
      await answerFreeWrite({
        correct: false, score: 55, feedback: 'Thiếu mạo từ.',
        improvedVersion: 'She stayed resilient throughout the crisis.',
      });

      expect(await screen.findByText(/câu viết lại/i)).toBeInTheDocument();
      expect(screen.getByText('She stayed resilient throughout the crisis.')).toBeInTheDocument();
    });

    it('feedback khi sai chứa luôn đáp án — kênh duy nhất người học biết đáp án', async () => {
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1)] }
          : { ok: true, data: [] }),
        answer: () => ({
          ok: true,
          data: {
            correct: false, score: 0,
            feedback: 'Chưa đúng. Đáp án: mitigate', improvedVersion: null,
          },
        }),
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');

      await userEvent.type(await screen.findByLabelText('Từ cần điền'), 'mitigated');
      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));

      expect(await screen.findByText('Chưa đúng. Đáp án: mitigate')).toBeInTheDocument();
    });

    it('đang chấm thì khoá nút Nộp và báo trạng thái', async () => {
      let release!: (value: unknown) => void;
      transportSend.mockImplementation(
        async (request: Sent) => {
          if (request.type === 'GENERATE_QUIZ') {
            return request.quizType === 'FREE_WRITE'
              ? { ok: true, data: [freeWrite(9)] }
              : { ok: true, data: [] };
          }
          if (request.type === 'ANSWER_QUIZ') {
            return new Promise((resolve) => { release = resolve; });
          }
          return { ok: true, data: null };
        },
      );

      render(<QuizTab />);
      await generateOnly('Tự viết câu');
      await userEvent.type(
        await screen.findByLabelText('Câu tiếng Anh của bạn'),
        'She stayed resilient.',
      );
      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));

      expect(await screen.findByText(/đang chấm/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Nộp' })).toBeDisabled();

      release({ ok: true, data: CORRECT });
      expect(await screen.findByText('Chính xác.')).toBeInTheDocument();
    });

    it('hết đề thì hiện tổng kết đúng/tổng', async () => {
      mockBackend({
        generate: (r) => (r.quizType === 'COLLOCATION_CHOICE'
          ? { ok: true, data: [collocation(5, ['a', 'b', 'c', 'd'])] }
          : { ok: true, data: [] }),
      });
      render(<QuizTab />);
      await generateOnly('Chọn cụm từ');
      await screen.findAllByRole('button', { name: /^\d/ });

      await userEvent.click(optionButtons()[0]);
      await userEvent.click(await screen.findByRole('button', { name: /xem kết quả/i }));

      expect(await screen.findByText('Đúng 1/1')).toBeInTheDocument();
    });
  });

  /* ================= Lỗi và trạng thái rỗng ================= */

  describe('lỗi và trạng thái rỗng', () => {
    it('không có ứng viên nào thì hiện empty state, KHÔNG phải lỗi đỏ', async () => {
      mockBackend();

      render(<QuizTab />);
      await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

      expect(await screen.findByText(/chưa có từ nào đủ điều kiện/i)).toBeInTheDocument();
    });

    it('PARSE_ERROR retryable=false vẫn cho bấm "Tạo đề" lại', async () => {
      // AppException.of() chỉ đặt retryable=true cho GEMINI_UNAVAILABLE, nên PARSE_ERROR
      // về tới panel với retryable=false dù bấm lại rất có thể thành công.
      mockBackend({
        generate: () => ({
          ok: false,
          error: { code: 'PARSE_ERROR', message: 'AI trả về dữ liệu hỏng', retryable: false },
        }),
      });

      render(<QuizTab />);
      await userEvent.click(screen.getByRole('button', { name: 'Tạo đề' }));

      expect(await screen.findByText(/AI trả về dữ liệu hỏng/)).toBeInTheDocument();
      const retry = screen.getByRole('button', { name: 'Tạo đề' });
      expect(retry).toBeEnabled();

      await userEvent.click(retry);
      await waitFor(() => expect(sentOf('GENERATE_QUIZ').length).toBe(6));
    });

    it('không tick loại nào thì không cho tạo đề', async () => {
      mockBackend();

      render(<QuizTab />);
      for (const label of ['Điền từ', 'Chọn cụm từ', 'Tự viết câu'] as const) {
        await userEvent.click(screen.getByLabelText(label));
      }

      expect(screen.getByRole('button', { name: 'Tạo đề' })).toBeDisabled();
    });
  });

  /* ================= Giải thích đáp án ================= */

  describe('giải thích đáp án', () => {
    /** Dựng một đề đúng hai câu FILL_BLANK rồi trả lời câu đầu. */
    async function answerFirstFillBlank(opts: {
      answer?: (request: Sent) => unknown;
      explain?: (request: Sent) => unknown;
    } = {}) {
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1), fillBlank(2)] }
          : { ok: true, data: [] }),
        answer: opts.answer,
        explain: opts.explain,
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');

      await userEvent.type(await screen.findByLabelText('Từ cần điền'), 'reduce');
      await userEvent.click(screen.getByRole('button', { name: 'Nộp' }));
      await screen.findByRole('button', { name: 'Giải thích' });
    }

    it('chưa trả lời thì KHÔNG có nút Giải thích — nó tiết lộ đáp án', async () => {
      mockBackend({
        generate: (r) => (r.quizType === 'FILL_BLANK'
          ? { ok: true, data: [fillBlank(1)] }
          : { ok: true, data: [] }),
      });
      render(<QuizTab />);
      await generateOnly('Điền từ');
      await screen.findByLabelText('Từ cần điền');

      expect(screen.queryByRole('button', { name: 'Giải thích' })).not.toBeInTheDocument();
    });

    it('trả lời ĐÚNG vẫn có nút Giải thích — đoán trúng cũng cần biết vì sao', async () => {
      await answerFirstFillBlank({ answer: () => ({ ok: true, data: CORRECT }) });

      expect(screen.getByRole('button', { name: 'Giải thích' })).toBeEnabled();
    });

    it('bấm Giải thích gửi EXPLAIN_QUIZ đúng quizItemId và hiện đủ ba khối', async () => {
      await answerFirstFillBlank();

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      await waitFor(() => expect(sentOf('EXPLAIN_QUIZ')).toHaveLength(1));
      // Body chỉ có quizItemId: câu trả lời KHÔNG được gửi kèm.
      expect(sentOf('EXPLAIN_QUIZ')[0]).toEqual({ type: 'EXPLAIN_QUIZ', quizItemId: 1 });

      expect(await screen.findByText(EXPLANATION.explanation)).toBeInTheDocument();
      expect(screen.getByText('mitigate = giảm nhẹ')).toBeInTheDocument();
      expect(screen.getByText(EXPLANATION.sentenceEn as string)).toBeInTheDocument();
      expect(screen.getByText(EXPLANATION.sentenceVi as string)).toBeInTheDocument();
      // Đã có giải thích thì nút biến mất — bấm lại chỉ tốn thêm một lượt gọi Gemini.
      expect(screen.queryByRole('button', { name: 'Giải thích' })).not.toBeInTheDocument();
    });

    it('cặp câu null thì KHÔNG render khối "Dịch câu"', async () => {
      await answerFirstFillBlank({
        explain: () => ({
          ok: true,
          data: {
            explanation: 'Bạn đã bỏ qua câu này.',
            answerMeaning: 'mitigate = giảm nhẹ',
            sentenceEn: null,
            sentenceVi: null,
          } satisfies QuizExplanation,
        }),
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByText('Bạn đã bỏ qua câu này.')).toBeInTheDocument();
      expect(screen.queryByText('Dịch câu')).not.toBeInTheDocument();
    });

    it('lỗi hiện thông báo và nút Giải thích vẫn bấm lại được', async () => {
      let calls = 0;
      await answerFirstFillBlank({
        explain: () => {
          calls += 1;
          return calls === 1
            ? { ok: false, error: { code: 'GEMINI_UNAVAILABLE', message: 'Gemini đang bận.', retryable: true } }
            : { ok: true, data: EXPLANATION };
        },
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByRole('alert')).toHaveTextContent('Gemini đang bận.');
      const retry = screen.getByRole('button', { name: 'Giải thích' });
      expect(retry).toBeEnabled();

      await userEvent.click(retry);

      expect(await screen.findByText(EXPLANATION.explanation)).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('đang giải thích thì nút Tiếp bị KHOÁ — response về muộn sẽ ghi nhầm sang câu sau', async () => {
      let release!: (value: unknown) => void;
      await answerFirstFillBlank({
        explain: () => new Promise((resolve) => { release = resolve; }),
      });

      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));

      expect(await screen.findByRole('button', { name: 'Đang giải thích…' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Tiếp' })).toBeDisabled();

      release({ ok: true, data: EXPLANATION });
      await screen.findByText(EXPLANATION.explanation);
      expect(screen.getByRole('button', { name: 'Tiếp' })).toBeEnabled();
    });

    it('sang câu mới thì khối giải thích biến sạch', async () => {
      await answerFirstFillBlank();
      await userEvent.click(screen.getByRole('button', { name: 'Giải thích' }));
      await screen.findByText(EXPLANATION.explanation);

      await userEvent.click(screen.getByRole('button', { name: 'Tiếp' }));

      expect(screen.queryByText(EXPLANATION.explanation)).not.toBeInTheDocument();
      expect(screen.queryByText('Giải thích')).not.toBeInTheDocument();
      expect(await screen.findByLabelText('Từ cần điền')).toHaveValue('');
    });
  });
});
