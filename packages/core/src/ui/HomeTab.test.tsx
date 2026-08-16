import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HomeTab } from './HomeTab';
import type { AuthUser, DailyPoint, StatsDto, VocabTagsResponse } from '../types';
import { transportSend } from '../../vitest.setup';

const USER: AuthUser = { email: 'hiep@test.local', displayName: 'Hiep', pictureUrl: null };

function day(date: string, reviews: number, practice = 0): DailyPoint {
  return { date, reviews, practice };
}

const WEEK = [
  day('2026-08-09', 5), day('2026-08-10', 4), day('2026-08-11', 6),
  day('2026-08-12', 3), day('2026-08-13', 7), day('2026-08-14', 0, 2),
  day('2026-08-15', 18),
];

function stats(over: Partial<StatsDto> = {}): StatsDto {
  return {
    streak: { current: 12, longest: 20, lastActiveDate: '2026-08-15' },
    totals: {
      reviews: 430,
      learnedWords: 96,
      masteredWords: 62,
      learningWords: 34,
      activeDays: 40,
      avgBand: 7.4,
      introducedLast7: 7,
    },
    daily: WEEK,
    recall: { again: 18, hard: 20, good: 40, easy: 22 },
    quiz: [],
    ...over,
  };
}

const TAGS: VocabTagsResponse = {
  total: 128,
  untagged: 41,
  tags: [
    { tag: 'Môi trường', count: 24, mastered: 17 },
    { tag: 'Giáo dục', count: 19, mastered: 10 },
    { tag: 'Kinh tế', count: 17, mastered: 6 },
  ],
};

/** Ba lượt gọi của màn Hôm nay. `false` = lượt đó lỗi. */
function mockHome(over: {
  due?: number;
  stats?: StatsDto | false;
  tags?: VocabTagsResponse | false;
} = {}) {
  const due = over.due ?? 11;
  const statsData = over.stats === undefined ? stats() : over.stats;
  const tagsData = over.tags === undefined ? TAGS : over.tags;
  const loi = { ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true } };

  transportSend.mockImplementation(async (request: { type: string }) => {
    switch (request.type) {
      case 'GET_SRS_STATS':
        return { ok: true, data: { dueCount: due, newCount: 0, learnedCount: 96 } };
      case 'GET_STATS':
        return statsData === false ? loi : { ok: true, data: statsData };
      case 'GET_VOCAB_TAGS':
        return tagsData === false ? loi : { ok: true, data: tagsData };
      default:
        return { ok: true, data: null };
    }
  });
}

function renderHome(props: Partial<Parameters<typeof HomeTab>[0]> = {}) {
  const onNavigate = vi.fn();
  const onOpenStats = vi.fn();
  const onSignOut = vi.fn();
  render(
    <HomeTab
      user={USER}
      // Mặc định là màn đang mở — đó là trạng thái mọi test ở đây muốn nói tới. `active`
      // điều khiển lúc nào màn nạp lại số (xem HomeTab), nên test nào cần ca "đang ẩn"
      // phải truyền tường minh qua `props`.
      active
      onSignOut={onSignOut}
      onNavigate={onNavigate}
      onOpenStats={onOpenStats}
      {...props}
    />,
  );
  return { onNavigate, onOpenStats, onSignOut };
}

describe('HomeTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /* ================= Đường đăng xuất (mục 1.2 hợp đồng) ================= */

  it('hiện email và nút Đăng xuất — 1b bỏ dải tài khoản ở header nên đường này về đây', async () => {
    mockHome();
    const { onSignOut } = renderHome();

    expect(await screen.findByText('hiep@test.local')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }));
    expect(onSignOut).toHaveBeenCalled();
  });

  it('backend hỏng vẫn còn đường đăng xuất', async () => {
    // Mất đường đăng xuất trên một máy dùng chung là hỏng thật, không phải lỗi hiển thị.
    mockHome({ stats: false, tags: false });
    renderHome();

    expect(await screen.findByRole('button', { name: 'Đăng xuất' })).toBeInTheDocument();
  });

  /* ================= Vòng tròn tiến độ ================= */

  it('vòng tròn nói đã ôn bao nhiêu trên tổng bao nhiêu', async () => {
    // 18 lượt hôm nay (phần tử cuối của `daily`) + 11 thẻ còn đến hạn = 29.
    mockHome();
    renderHome();

    expect(await screen.findByText('18')).toBeInTheDocument();
    expect(screen.getByText('/29 thẻ')).toBeInTheDocument();
    expect(screen.getByText(/Còn 11 thẻ đến hạn/)).toBeInTheDocument();
  });

  it('ước lượng thời gian còn lại', async () => {
    mockHome({ due: 20 });
    renderHome();

    expect(await screen.findByText(/Khoảng 4 phút/)).toBeInTheDocument();
  });

  it('hết thẻ đến hạn thì nói đã xong, không mời ôn tiếp một xấp rỗng', async () => {
    mockHome({ due: 0 });
    renderHome();

    expect(await screen.findByText(/xong mục tiêu hôm nay/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ôn tiếp' })).not.toBeInTheDocument();
  });

  it('"Ôn tiếp" chuyển sang tab Ôn tập', async () => {
    mockHome();
    const { onNavigate } = renderHome();

    await userEvent.click(await screen.findByRole('button', { name: 'Ôn tiếp' }));

    expect(onNavigate).toHaveBeenCalledWith('review');
  });

  /* ================= Lưới 4 ô số ================= */

  it('bốn ô số lấy đúng dữ liệu của backend', async () => {
    mockHome();
    renderHome();

    expect(await screen.findByText('12')).toBeInTheDocument();
    expect(screen.getByText('ngày liên tiếp')).toBeInTheDocument();
    expect(screen.getByText('62')).toBeInTheDocument();
    expect(screen.getByText('+7 từ mới tuần này')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();      // 1 − 18/100
    expect(screen.getByText('7.4')).toBeInTheDocument();
    expect(screen.getByText('128 từ trong sổ')).toBeInTheDocument();
  });

  it('"từ đã thuộc" đếm theo NGƯỠNG THUỘC, không phải mọi thẻ đã ôn một lần', async () => {
    // `learnedWords` là `repetitions >= 1`, còn "đã thuộc" ở mọi chỗ khác của 1b (thanh 5
    // vạch ở Sổ từ, % của chip chủ đề) là `repetitions >= MASTERED_REPETITIONS`. Vẽ
    // `learnedWords` ở đây làm màn này ghi "96 từ đã thuộc" trong khi card "Chủ đề đang
    // yếu" ngay dưới nó vẽ 0% — cùng một màn hình nói hai điều khác nhau.
    mockHome();
    renderHome();

    await screen.findByText('từ đã thuộc');
    expect(screen.getByText('62')).toBeInTheDocument();
    expect(screen.queryByText('96')).not.toBeInTheDocument();
  });

  it('dòng phụ nói "từ MỚI tuần này" — nó không phải phần tăng của số đã thuộc', async () => {
    // `introducedLast7` đếm số từ lần đầu được đưa vào ôn trong 7 ngày. Đặt nó dưới nhãn
    // "+N tuần này" của ô "đã thuộc" là gán cho nó một ý nghĩa mà nó không có.
    mockHome();
    renderHome();

    expect(await screen.findByText('+7 từ mới tuần này')).toBeInTheDocument();
    expect(screen.queryByText('+7 tuần này')).not.toBeInTheDocument();
  });

  it('chưa từ nào có band thì hiện "—", KHÔNG phải 0.0', async () => {
    // `avgBand: null` khác hẳn `0.0`. Vẽ 0.0 là nói với người học rằng vốn từ của họ band 0.
    mockHome({ stats: stats({
      totals: {
        reviews: 430,
        learnedWords: 96,
        masteredWords: 62,
        learningWords: 34,
        activeDays: 40,
        avgBand: null,
        introducedLast7: 7,
      },
    }) });
    renderHome();

    await screen.findByText('band trung bình');
    expect(screen.queryByText('0.0')).not.toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('chưa ôn lượt nào thì tỉ lệ nhớ là "—", không phải 0%', async () => {
    mockHome({ stats: stats({ recall: { again: 0, hard: 0, good: 0, easy: 0 } }) });
    renderHome();

    await screen.findByText('tỉ lệ nhớ');
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  /* ================= Dải streak trong ô ================= */

  it('vẽ 7 ô streak, lấy 7 phần tử CUỐI của daily', async () => {
    // `daily` dài 91 phần tử ở backend thật; lấy 7 phần tử ĐẦU là vẽ tuần của ba tháng trước.
    mockHome({ stats: stats({ daily: [day('2026-05-01', 9), ...WEEK] }) });
    renderHome();

    const cells = await screen.findAllByTestId('streak-cell');
    expect(cells).toHaveLength(7);
    expect(cells[0]).toHaveAttribute('data-level', 'on');
  });

  it('ngày chỉ luyện thêm là mức nửa — luyện KHÔNG nối chuỗi', async () => {
    mockHome();
    renderHome();

    const cells = await screen.findAllByTestId('streak-cell');
    expect(cells[5]).toHaveAttribute('data-level', 'half');
  });

  /* ================= Chủ đề đang yếu ================= */

  it('liệt kê chủ đề thành thạo thấp nhất trước', async () => {
    mockHome();
    renderHome();

    expect(await screen.findByText('Kinh tế')).toBeInTheDocument();
    expect(screen.getByText('35%')).toBeInTheDocument();
    expect(screen.getByText('71%')).toBeInTheDocument();
  });

  it('"Xem cả sổ" chuyển sang tab Sổ từ', async () => {
    mockHome();
    const { onNavigate } = renderHome();

    await userEvent.click(await screen.findByRole('button', { name: 'Xem cả sổ' }));

    expect(onNavigate).toHaveBeenCalledWith('vocab');
  });

  /* ================= Đường sang StatsTab (mục 1.1 hợp đồng) ================= */

  it('"Xem chi tiết" mở màn thống kê đầy đủ', async () => {
    // 1b bỏ tab "Tiến độ" khỏi bottom nav, nhưng heatmap 91 ngày và phân rã tỉ lệ nhớ vẫn
    // phải tới được — nếu không thì đây là xoá tính năng, không phải đổi giao diện.
    mockHome();
    const { onOpenStats } = renderHome();

    await userEvent.click(await screen.findByRole('button', { name: /Xem chi tiết/i }));

    expect(onOpenStats).toHaveBeenCalled();
  });

  it('sổ từ RỖNG vẫn còn đường sang màn thống kê', async () => {
    // Nút này là đường DUY NHẤT tới StatsTab. Trả nó về sau một nhánh return sớm là mất
    // hẳn heatmap và biểu đồ ở đúng trạng thái mà người mới cài rơi vào đầu tiên.
    mockHome({ due: 0, tags: { total: 0, untagged: 0, tags: [] } });
    const { onOpenStats } = renderHome();

    await screen.findByText(/Sổ từ đang trống/i);
    await userEvent.click(screen.getByRole('button', { name: /Xem chi tiết/i }));

    expect(onOpenStats).toHaveBeenCalled();
  });

  it('GET_STATS hỏng vẫn còn đường sang màn thống kê', async () => {
    // StatsTab tự nạp lại GET_STATS và tự báo lỗi của nó — chặn đường sang đó ở đây chỉ
    // làm người dùng mất luôn chỗ bấm thử lại.
    mockHome({ stats: false });
    const { onOpenStats } = renderHome();

    await screen.findByText('Backend chưa chạy');
    await userEvent.click(screen.getByRole('button', { name: /Xem chi tiết/i }));

    expect(onOpenStats).toHaveBeenCalled();
  });

  it('GET_SRS_STATS hỏng vẫn còn đường sang màn thống kê', async () => {
    transportSend.mockImplementation(async (request: { type: string }) => {
      if (request.type === 'GET_SRS_STATS') {
        return {
          ok: false,
          error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
        };
      }
      return { ok: true, data: request.type === 'GET_STATS' ? stats() : TAGS };
    });
    const { onOpenStats } = renderHome();

    await screen.findByText('Backend chưa chạy');
    await userEvent.click(screen.getByRole('button', { name: /Xem chi tiết/i }));

    expect(onOpenStats).toHaveBeenCalled();
  });

  /* ================= Sổ từ rỗng ================= */

  it('sổ từ rỗng thì mời dịch từ đầu tiên, KHÔNG vẽ lưới toàn số 0', async () => {
    mockHome({ due: 0, tags: { total: 0, untagged: 0, tags: [] } });
    renderHome();

    expect(await screen.findByText(/Sổ từ đang trống/i)).toBeInTheDocument();
    expect(screen.queryByText('ngày liên tiếp')).not.toBeInTheDocument();
    expect(screen.queryByText('band trung bình')).not.toBeInTheDocument();
  });

  /* ================= Hỏng thì nói ra ================= */

  it('lỗi retry được thì có nút Thử lại và gọi lại backend', async () => {
    mockHome({ stats: false });
    renderHome();

    await userEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));

    const soLan = transportSend.mock.calls
      .filter((call) => (call[0] as { type: string }).type === 'GET_STATS').length;
    expect(soLan).toBe(2);
  });

  it('gọi mỗi loại đúng MỘT lần cho một lần mở màn', async () => {
    mockHome();
    renderHome();
    await screen.findByText('/29 thẻ');

    const dem = (type: string) => transportSend.mock.calls
      .filter((call) => (call[0] as { type: string }).type === type).length;
    expect(dem('GET_STATS')).toBe(1);
    expect(dem('GET_SRS_STATS')).toBe(1);
    expect(dem('GET_VOCAB_TAGS')).toBe(1);
  });
});
