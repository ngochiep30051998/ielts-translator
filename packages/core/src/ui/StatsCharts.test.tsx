import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Accuracy, DailyBars, Heatmap, StatRow } from './StatsCharts';
import type { DailyPoint, QuizTypeStats } from '../types';

function daily(n: number, reviewsFor: (i: number) => number): DailyPoint[] {
  const today = new Date(2026, 7, 11);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (n - 1 - i));
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { date: iso, reviews: reviewsFor(i), practice: 0 };
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
        totals={{
          reviews: 1284, learnedWords: 312, masteredWords: 208, learningWords: 104,
          activeDays: 87, avgBand: 7.2, introducedLast7: 9,
        }}
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

  it('lấy 30 NGÀY GẦN NHẤT (nửa cuối mảng), không phải 30 ngày cũ nhất', () => {
    // Ca "vẽ đúng 30 cột dù nhận vào 91 ngày" ở trên dùng `reviewsFor: () => 3` hằng số nên
    // 30 phần tử đầu và 30 phần tử cuối của mảng 91 ngày giống hệt nhau — đổi code thành
    // `daily.slice(0, BAR_DAYS)` (lấy nhầm 30 ngày CŨ NHẤT) vẫn qua ca đó. Ở đây dùng
    // `reviewsFor: (i) => i` để hai đầu mảng phân biệt được, rồi đọc `title` của cột đầu
    // tiên (dạng "dd/mm: N lượt ôn") thay vì đếm số cột.
    render(<DailyBars daily={daily(91, (i) => i)} />);

    const bars = screen.getAllByTestId('bar');
    // `daily()` sinh chỉ số 0..90 tăng dần theo ngày (0 = cũ nhất, 90 = hôm nay).
    // slice(-30) đúng phải lấy chỉ số 61..90, nên cột đầu tiên ứng với i=61 → "61 lượt ôn".
    // slice(0, 30) (bug) sẽ cho cột đầu tiên ứng với i=0 → "0 lượt ôn".
    expect(bars[0].title).toMatch(/: 61 lượt ôn$/);
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

  it('chiều cao cột tính cả lượt luyện thêm', () => {
    render(
      <DailyBars
        daily={[
          { date: '2026-08-10', reviews: 2, practice: 0 },
          { date: '2026-08-11', reviews: 2, practice: 8 },
        ]}
      />,
    );

    const bars = screen.getAllByTestId('bar');
    // Ngày sau có 10 lượt so với 2 lượt của ngày trước — cột phải cao hơn hẳn.
    expect(parseFloat(bars[1].style.height)).toBeGreaterThan(parseFloat(bars[0].style.height));
  });

  it('aria-label dùng cùng một cơ sở cho tổng và cao nhất', () => {
    // Trước đây `max` tính cả luyện thêm còn `total` thì không, nên nhãn nói "tổng 2 lượt,
    // cao nhất 10 lượt" — cao nhất MỘT NGÀY lại lớn hơn tổng CẢ THÁNG, vô lý. Test này không
    // bám vào chữ "ôn" hay "học" cụ thể — chỉ chốt bất biến số học: tổng không thể nhỏ hơn max.
    const days = daily(30, () => 0);
    days[days.length - 1] = { ...days[days.length - 1], reviews: 2, practice: 8 };
    render(<DailyBars daily={days} />);

    const img = screen.getByRole('img', { name: /30 ngày gần nhất/ });
    const label = img.getAttribute('aria-label') ?? '';
    const total = Number(label.match(/tổng (\d+) lượt/)?.[1]);
    const max = Number(label.match(/cao nhất (\d+) lượt/)?.[1]);
    expect(total).toBeGreaterThanOrEqual(max);
  });
});

describe('Heatmap', () => {
  it('vẽ đủ 91 ô có dữ liệu', () => {
    render(<Heatmap daily={daily(91, () => 2)} />);

    expect(screen.getByRole('img', { name: /91 ngày gần nhất/ })).toBeInTheDocument();
    // Ô đệm không mang testid, nên con số này đúng bằng số ngày có dữ liệu.
    expect(screen.getAllByTestId('cell')).toHaveLength(91);
  });

  it('title tách riêng lượt ôn và lượt luyện thêm', () => {
    render(<Heatmap daily={[{ date: '2026-08-11', reviews: 12, practice: 5 }]} />);

    expect(screen.getByTestId('cell')).toHaveAttribute(
      'title',
      '11/08: 12 lượt ôn · 5 lượt luyện thêm',
    );
  });

  it('ngày không luyện thêm thì title không nhắc tới nó', () => {
    render(<Heatmap daily={[{ date: '2026-08-11', reviews: 12, practice: 0 }]} />);

    expect(screen.getByTestId('cell')).toHaveAttribute('title', '11/08: 12 lượt ôn');
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
