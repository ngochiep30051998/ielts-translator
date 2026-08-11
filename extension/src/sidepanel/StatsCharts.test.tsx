import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Accuracy, DailyBars, Heatmap, StatRow } from './StatsCharts';
import type { DailyPoint, QuizTypeStats } from '../shared/types';

function daily(n: number, reviewsFor: (i: number) => number): DailyPoint[] {
  const today = new Date(2026, 7, 11);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (n - 1 - i));
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { date: iso, reviews: reviewsFor(i) };
  });
}

const EMPTY_QUIZ_STATS: QuizTypeStats[] = [
  { type: 'FILL_BLANK', attempts: 0, correct: 0, avgScore: null },
  { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
  { type: 'FREE_WRITE', attempts: 0, correct: 0, avgScore: null },
];

describe('StatRow', () => {
  it('hiện đủ bốn con số', () => {
    render(
      <StatRow
        streak={{ current: 5, longest: 23, lastActiveDate: '2026-08-11' }}
        totals={{ reviews: 1284, learnedWords: 312, activeDays: 87 }}
      />,
    );

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('23')).toBeInTheDocument();
    expect(screen.getByText('1284')).toBeInTheDocument();
    expect(screen.getByText('312')).toBeInTheDocument();
  });
});

describe('DailyBars', () => {
  it('vẽ đúng 30 cột dù nhận vào 91 ngày', () => {
    render(<DailyBars daily={daily(91, () => 3)} />);

    expect(screen.getByRole('img', { name: /30 ngày gần nhất/ })).toBeInTheDocument();
    expect(screen.getAllByTestId('bar')).toHaveLength(30);
  });

  it('không chia cho 0 khi 30 ngày qua không ôn lượt nào', () => {
    // Ca này KHÔNG bị trạng thái rỗng của StatsTab chặn: người dùng có thể có lượt ôn từ
    // 200 ngày trước (totals.reviews > 0) mà 30 ngày qua trắng trơn. `count/max` khi đó là
    // 0/0 = NaN, và `height: NaN%` là cột biến mất — hỏng lặng lẽ, không exception.
    render(<DailyBars daily={daily(30, () => 0)} />);

    const bars = screen.getAllByTestId('bar');
    expect(bars).toHaveLength(30);
    for (const bar of bars) {
      // Không so `not.toContain('NaN')`: jsdom (và trình duyệt thật, theo spec CSSOM) âm thầm
      // BỎ QUA giá trị style không hợp lệ như "NaN%" — `style.height` sau đó là chuỗi rỗng,
      // không phải "NaN%", nên phép so đó xanh cả khi code bị sập bẫy chia cho 0. Phải so
      // đúng giá trị sàn 2% mà nhánh chống-chia-0 phải tạo ra thì mới bắt được lỗi thật.
      expect(bar.style.height).toBe('2%');
    }
  });
});

describe('Heatmap', () => {
  it('vẽ đủ 91 ô có dữ liệu', () => {
    render(<Heatmap daily={daily(91, () => 2)} />);

    expect(screen.getByRole('img', { name: /91 ngày gần nhất/ })).toBeInTheDocument();
    // Ô đệm không mang testid, nên con số này đúng bằng số ngày có dữ liệu.
    expect(screen.getAllByTestId('cell')).toHaveLength(91);
  });
});

describe('Accuracy', () => {
  it('tỉ lệ nhớ là phần không phải AGAIN', () => {
    render(
      <Accuracy recall={{ again: 20, hard: 20, good: 40, easy: 20 }} quiz={EMPTY_QUIZ_STATS} />,
    );

    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('chưa ôn lượt nào thì hiện gạch ngang, không phải 0% hay NaN', () => {
    render(<Accuracy recall={{ again: 0, hard: 0, good: 0, easy: 0 }} quiz={EMPTY_QUIZ_STATS} />);

    expect(screen.getByTestId('recall-rate')).toHaveTextContent('—');
  });

  it('loại quiz chưa làm hiện gạch ngang chứ không phải 0%', () => {
    // "Chưa làm" và "làm sai hết" là hai chuyện khác nhau. Hiện 0% cho loại chưa đụng tới
    // là nói dối người học rằng họ đã thử và trượt.
    render(<Accuracy recall={{ again: 0, hard: 0, good: 1, easy: 0 }} quiz={EMPTY_QUIZ_STATS} />);

    expect(screen.getAllByTestId('quiz-rate')).toHaveLength(3);
    for (const el of screen.getAllByTestId('quiz-rate')) {
      expect(el).toHaveTextContent('—');
    }
  });

  it('điểm trung bình chỉ hiện với Tự viết câu', () => {
    render(
      <Accuracy
        recall={{ again: 0, hard: 0, good: 1, easy: 0 }}
        quiz={[
          { type: 'FILL_BLANK', attempts: 4, correct: 3, avgScore: null },
          { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
          { type: 'FREE_WRITE', attempts: 5, correct: 3, avgScore: 72 },
        ]}
      />,
    );

    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText(/72/)).toBeInTheDocument();
  });
});
