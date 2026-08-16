import { it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StatsTab } from './StatsTab';
import type { StatsDto } from '../types';
import { transportSend } from '../../vitest.setup';

function stats(patch: Partial<StatsDto> = {}): StatsDto {
  const end = new Date(2026, 7, 11);
  return {
    streak: { current: 5, longest: 23, lastActiveDate: '2026-08-11' },
    totals: {
      reviews: 1284, learnedWords: 312, masteredWords: 208, learningWords: 104,
      activeDays: 87, avgBand: 7.2, introducedLast7: 9,
    },
    daily: Array.from({ length: 91 }, (_, i) => {
      const d = new Date(end.getFullYear(), end.getMonth(), end.getDate() - (90 - i));
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      return { date: iso, reviews: 2, practice: 0 };
    }),
    recall: { again: 20, hard: 20, good: 40, easy: 20 },
    quiz: [
      { type: 'FILL_BLANK', attempts: 4, correct: 3, avgScore: null },
      { type: 'COLLOCATION_CHOICE', attempts: 0, correct: 0, avgScore: null },
      { type: 'FREE_WRITE', attempts: 5, correct: 3, avgScore: 72 },
    ],
    ...patch,
  };
}

function mockStats(response: unknown) {
  transportSend.mockImplementation(
    async (request: { type: string }) =>
      (request.type === 'GET_STATS' ? response : { ok: true, data: null }),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

it('hiện "Đang tải…" trong lúc chờ service worker phản hồi', () => {
  // Promise treo mãi mãi trong phạm vi test này — đủ để bắt được trạng thái loading
  // ban đầu mà không phải đợi hay giả lập response thật.
  transportSend.mockImplementation(
    () => new Promise(() => {}),
  );
  render(<StatsTab />);

  expect(screen.getByText('Đang tải…')).toBeInTheDocument();
});

it('hiện bốn khối khi có dữ liệu', async () => {
  mockStats({ ok: true, data: stats() });
  render(<StatsTab />);

  expect(await screen.findByText('ngày liên tiếp')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /30 ngày gần nhất/ })).toBeInTheDocument();
  expect(screen.getByRole('img', { name: /Lịch học 91 ngày gần nhất/ })).toBeInTheDocument();
  expect(screen.getByText('Độ chính xác')).toBeInTheDocument();
});

it('chưa ôn lượt nào thì mời đi ôn, không vẽ bốn khối rỗng', async () => {
  // Tường số 0 và heatmap trắng trơn không nói được gì cho người vừa cài.
  mockStats({
    ok: true,
    data: stats({
      streak: { current: 0, longest: 0, lastActiveDate: null },
      totals: {
        reviews: 0, learnedWords: 0, masteredWords: 0, learningWords: 0,
        activeDays: 0, avgBand: null, introducedLast7: 0,
      },
    }),
  });
  render(<StatsTab />);

  expect(await screen.findByText(/Chưa có lượt ôn nào/)).toBeInTheDocument();
  expect(screen.queryByRole('img', { name: /Lịch học/ })).not.toBeInTheDocument();
});

it('lỗi retry được thì hiện nút Thử lại và gọi lại', async () => {
  mockStats({ ok: false, error: { code: 'GEMINI_UNAVAILABLE', message: 'Backend đang bận', retryable: true } });
  render(<StatsTab />);

  expect(await screen.findByText('Backend đang bận')).toBeInTheDocument();

  mockStats({ ok: true, data: stats() });
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }));

  expect(await screen.findByText('ngày liên tiếp')).toBeInTheDocument();
});

it('lỗi không retry được thì không có nút Thử lại', async () => {
  mockStats({ ok: false, error: { code: 'UNAUTHORIZED', message: 'Cần đăng nhập', retryable: false } });
  render(<StatsTab />);

  expect(await screen.findByText('Cần đăng nhập')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Thử lại' })).not.toBeInTheDocument();
});
