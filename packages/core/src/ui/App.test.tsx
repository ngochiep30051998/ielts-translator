import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import type { AuthUser, TranslateResult } from '../types';
import { transportSend } from '../../vitest.setup';

const USER: AuthUser = { email: 'hiep@test.local', displayName: 'Hiep', pictureUrl: null };

<<<<<<< Updated upstream
=======
function day(date: string, reviews: number, practice = 0): DailyPoint {
  return { date, reviews, practice };
}

/** StatsDto đủ để `StatsTab` vẽ ra được — dùng cho màn con "Xem chi tiết tiến độ". */
function stats(): StatsDto {
  return {
    streak: { current: 12, longest: 20, lastActiveDate: '2026-08-15' },
    totals: {
      reviews: 430, learnedWords: 96, masteredWords: 62, learningWords: 34,
      activeDays: 40, avgBand: 7.4, introducedLast7: 7,
    },
    daily: [day('2026-08-14', 4), day('2026-08-15', 18)],
    recall: { again: 1, hard: 1, good: 5, easy: 3 },
    quiz: [],
  };
}

>>>>>>> Stashed changes
const lastResult: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'was resiliented',
  payload: {
    term: 'resilient', lemma: 'resilient', pos: 'adj', ipa: '/rɪˈzɪliənt/',
    meaning_vi: 'kiên cường', definition_en: 'able to recover quickly', cefr: 'B2',
    band_level: '7.0', register: 'academic', collocations: [], examples: [], synonyms: [],
  },
};

/** Kết quả TRANSLATE_TEXT trả về khi dịch từ ô nhập (khác lastResult để không lẫn với GET_LAST_RESULT). */
const enViWord: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'renewable',
  payload: {
    term: 'renewable', lemma: 'renewable', pos: 'adj', ipa: '/rɪˈnjuːəbl/',
    meaning_vi: 'tái tạo', definition_en: 'able to be renewed', cefr: 'B2',
    band_level: '6.5', register: 'academic',
    collocations: ['renewable energy', 'renewable resources'],
    examples: [{ en: 'We rely on renewable energy.', vi: 'Chúng ta dựa vào năng lượng tái tạo.' }],
    synonyms: [{ term: 'sustainable', band: '7.0' }],
  },
};

/** Mock đủ cho App + mọi tab con mà test này chạm tới. */
function mockBackend(last: TranslateResult | null, auth: AuthUser | null = USER) {
  transportSend.mockImplementation(
    async (request: { type: string }) => {
      switch (request.type) {
        case 'GET_AUTH_STATE':
          return { ok: true, data: auth };
        case 'SIGN_OUT':
          return { ok: true, data: null };
        case 'GET_LAST_RESULT':
          return { ok: true, data: last };
        case 'SEARCH_VOCAB':
          return { ok: true, data: { content: [], totalElements: 0, totalPages: 0, number: 0 } };
<<<<<<< Updated upstream
=======
        case 'GET_VOCAB_TAGS':
          return { ok: true, data: { total: 128, untagged: 41, tags: [] } };
        case 'GET_SRS_STATS':
          return { ok: true, data: { dueCount: 11, newCount: 0, learnedCount: 96 } };
        case 'GET_STATS':
          return { ok: true, data: stats() };
        // Tab Ôn tập nạp hàng đợi ngay khi mount; `null` làm nó ném ở chỗ chẳng liên quan.
        case 'GET_DUE_CARDS':
        case 'GET_PRACTICE_CARDS':
          return { ok: true, data: [] };
>>>>>>> Stashed changes
        default:
          return { ok: true, data: null };
      }
    },
  );
}

/** Sang tab Dịch. 1b mở ở "Hôm nay", nên mọi test của ô dịch phải đi qua đây trước. */
async function moTabDich() {
  await userEvent.click(await screen.findByRole('tab', { name: 'Dịch' }));
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initialDraft điền sẵn vào ô Dịch', async () => {
    // Web dùng cái này cho Web Share Target: người dùng vừa bôi đen một đoạn ở app khác rồi
    // chia sẻ sang, và mong thấy nó ở đây ngay.
    mockBackend(null);

    render(<App initialDraft="renewable energy" />);
    await moTabDich();

    expect(await screen.findByDisplayValue('renewable energy')).toBeInTheDocument();
  });

  it('initialDraft THẮNG kết quả dịch lần trước', async () => {
    // Ghi đè đoạn người dùng vừa cố ý chia sẻ bằng nháp cũ là vứt đi đúng thứ họ vừa gửi tới.
    mockBackend(lastResult);

    render(<App initialDraft="doan moi chia se" />);
    await moTabDich();

    expect(await screen.findByDisplayValue('doan moi chia se')).toBeInTheDocument();
    expect(screen.queryByDisplayValue(lastResult.sourceText)).not.toBeInTheDocument();
  });

  it('không có initialDraft thì vẫn tự điền từ kết quả gần nhất như cũ', async () => {
    mockBackend(lastResult);

    render(<App />);
    await moTabDich();

    expect(await screen.findByDisplayValue(lastResult.sourceText)).toBeInTheDocument();
  });

  it('đọc kết quả gần nhất một lần và hiện ở tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);
    await moTabDich();

    expect(await screen.findByText('kiên cường')).toBeInTheDocument();
    expect(transportSend).toHaveBeenCalledWith({ type: 'GET_LAST_RESULT' });
    // Đúng MỘT lần: hiệu ứng đọc kết quả cũ không được chạy lại mỗi lần đổi tab.
    expect(countOf('GET_LAST_RESULT')).toBe(1);
  });

  /** Đếm riêng một loại message. Đếm TỔNG thì mọi luồng mới (auth, VocabTab) đều làm đỏ. */
  function countOf(type: string): number {
    return transportSend.mock.calls
      .filter((call) => (call[0] as { type: string }).type === type).length;
  }

  it('không gọi lại GET_LAST_RESULT khi đổi tab rồi quay lại tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);
    await moTabDich();

    await screen.findByText('kiên cường');
    expect(countOf('GET_LAST_RESULT')).toBe(1);

    await userEvent.click(screen.getByRole('tab', { name: 'Sổ từ' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Dịch' }));

    expect(await screen.findByText('kiên cường')).toBeInTheDocument();
    expect(countOf('GET_LAST_RESULT')).toBe(1);
  });

  it('điền sẵn ô nhập bằng text của kết quả gần nhất', async () => {
    mockBackend(lastResult);
    render(<App />);
    await moTabDich();

    expect(await screen.findByDisplayValue('was resiliented')).toBeInTheDocument();
  });

  it('đổi sang tab khác rồi quay lại vẫn giữ nguyên text đang gõ dở', async () => {
    mockBackend(null);
    render(<App />);
    await moTabDich();

    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'resilient');

    await userEvent.click(screen.getByRole('tab', { name: 'Sổ từ' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Dịch' }));

    // Khoá quyết định "state ở App": đẩy state ngược xuống TranslateTab cho gọn
    // sẽ làm ca này đỏ ngay.
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('resilient');
  });

  it('dịch từ ô nhập cập nhật vùng kết quả của panel', async () => {
    // Không dùng mockBackend(): test này cần TRANSLATE_TEXT trả kết quả riêng
    // (enViWord), còn GET_LAST_RESULT trả null để ô nhập bắt đầu trống.
    transportSend.mockImplementation(
      async (request: { type: string }) => {
        if (request.type === 'GET_AUTH_STATE') return { ok: true, data: USER };
        return request.type === 'TRANSLATE_TEXT'
          ? { ok: true, data: enViWord }
          : { ok: true, data: null };
      },
    );
    render(<App />);
    await moTabDich();
    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'renewable');
    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    // Khoá đường nối App → TranslateTab: nếu App không truyền đúng onResult xuống,
    // TranslateTab vẫn gọi được onResult nhưng App không cập nhật state result,
    // nên panel không bao giờ hiện kết quả.
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
    // Dịch xong không được đụng vào nội dung ô nhập (spec §2).
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('renewable');
  });

  /* ================= Bottom nav của 1b ================= */

  describe('bottom nav', () => {
    it('đúng năm mục, theo thứ tự của thiết kế 1b', async () => {
      mockBackend(null);
      render(<App />);

      const tabs = await screen.findAllByRole('tab');
      expect(tabs.map((t) => t.textContent)).toEqual([
        'Hôm nay', 'Dịch', 'Sổ từ', 'Ôn tập', 'Quiz',
      ]);
    });

    it('mở panel là vào thẳng Hôm nay, không phải tab Dịch', async () => {
      mockBackend(null);
      render(<App />);

      expect(await screen.findByRole('tab', { name: 'Hôm nay' }))
        .toHaveAttribute('aria-selected', 'true');
    });

    it('KHÔNG còn tab "Tiến độ" trên nav', async () => {
      mockBackend(null);
      render(<App />);

      await screen.findByRole('tab', { name: 'Hôm nay' });
      expect(screen.queryByRole('tab', { name: 'Tiến độ' })).not.toBeInTheDocument();
    });

    it('vẫn giữ vai trò a11y: tab đang chọn mang aria-selected', async () => {
      mockBackend(null);
      render(<App />);

      const tab = await screen.findByRole('tab', { name: 'Ôn tập' });
      await userEvent.click(tab);

      expect(tab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByRole('tab', { name: 'Hôm nay' }))
        .toHaveAttribute('aria-selected', 'false');
    });
  });

  /* ================= StatsTab thành màn con của Hôm nay ================= */

  describe('màn thống kê đầy đủ', () => {
    it('"Xem chi tiết tiến độ" mở StatsTab và có đường quay lại', async () => {
      // 1b bỏ tab "Tiến độ" khỏi nav, nhưng nội dung của nó KHÔNG được mất: heatmap 91
      // ngày, biểu đồ cột và phân rã tỉ lệ nhớ chỉ có ở màn này.
      mockBackend(null);
      render(<App />);

      await userEvent.click(await screen.findByRole('button', { name: /Xem chi tiết/i }));

      expect(await screen.findByText('kỷ lục')).toBeInTheDocument();
      expect(screen.getByText('lượt ôn')).toBeInTheDocument();

      await userEvent.click(screen.getByRole('button', { name: /Hôm nay/ }));

      expect(await screen.findByText('hiep@test.local')).toBeInTheDocument();
      expect(screen.queryByText('kỷ lục')).not.toBeInTheDocument();
    });

    it('màn con đang mở thì tabpanel được gắn nhãn theo màn ĐANG hiện', async () => {
      // `aria-labelledby` trỏ tab "Hôm nay" trong khi nội dung là màn "Tiến độ" thì trình
      // đọc màn hình đọc sai tên vùng người dùng vừa mở.
      mockBackend(null);
      render(<App />);
      await userEvent.click(await screen.findByRole('button', { name: /Xem chi tiết/i }));
      await screen.findByText('kỷ lục');

      const panel = screen.getByRole('tabpanel');
      const nhan = panel.getAttribute('aria-labelledby');
      expect(nhan).not.toBe('tab-home');
      expect(document.getElementById(nhan ?? '')).toHaveTextContent('Tiến độ');
    });

    it('đổi tab thì đóng luôn màn con, không để nó treo lại ở lần sau', async () => {
      mockBackend(null);
      render(<App />);
      await userEvent.click(await screen.findByRole('button', { name: /Xem chi tiết/i }));
      await screen.findByText('kỷ lục');

      await userEvent.click(screen.getByRole('tab', { name: 'Quiz' }));
      await userEvent.click(screen.getByRole('tab', { name: 'Hôm nay' }));

      expect(await screen.findByText('hiep@test.local')).toBeInTheDocument();
      expect(screen.queryByText('kỷ lục')).not.toBeInTheDocument();
    });
  });

  /* ================= Nhịp nạp của màn Hôm nay ================= */

  describe('ba lượt gọi của Hôm nay', () => {
    it('quay về Hôm nay thì nạp LẠI số — đây là bảng điểm, không phải ảnh chụp', async () => {
      // Người dùng sang Ôn tập, ôn hết thẻ, rồi quay về đây chính là để xem con số vừa đổi.
      // Giữ nguyên số của lần mở đầu tiên là sai ngay ở chỗ người ta nhìn vào để biết mình
      // vừa làm được gì.
      mockBackend(null);
      render(<App />);
      await screen.findByText('hiep@test.local');
      expect(countOf('GET_STATS')).toBe(1);

      // Quiz chứ không Sổ từ: `VocabTab` cũng gọi GET_VOCAB_TAGS, nên nó sẽ làm phép đếm
      // đỏ vì một lý do khác hẳn.
      await userEvent.click(screen.getByRole('tab', { name: 'Quiz' }));
      await userEvent.click(screen.getByRole('tab', { name: 'Hôm nay' }));
      await screen.findByText('hiep@test.local');

      await waitFor(() => expect(countOf('GET_STATS')).toBe(2));
      expect(countOf('GET_SRS_STATS')).toBe(2);
      expect(countOf('GET_VOCAB_TAGS')).toBe(2);
    });

    it('mở màn con rồi quay lại là ĐÚNG MỘT lượt nạp nữa, không phải mỗi lần render', async () => {
      // Nạp lại theo LƯỢT MỞ, không phải theo lượt render. Nếu effect bám nhầm dependency
      // thì phép đếm sẽ nhảy nhiều hơn một.
      //
      // Đếm GET_SRS_STATS chứ không GET_STATS: `StatsTab` cũng tự gọi GET_STATS khi màn con
      // mở ra, nên con số đó là 3 (Hôm nay → StatsTab → Hôm nay) và không tách được lượt
      // nạp của Hôm nay ra khỏi lượt nạp của màn con. GET_SRS_STATS chỉ Hôm nay gọi.
      mockBackend(null);
      render(<App />);
      await screen.findByText('hiep@test.local');
      expect(countOf('GET_SRS_STATS')).toBe(1);

      await userEvent.click(screen.getByRole('button', { name: 'Xem chi tiết tiến độ' }));
      await userEvent.click(screen.getByRole('button', { name: /Hôm nay/i }));
      await screen.findByText('hiep@test.local');

      await waitFor(() => expect(countOf('GET_SRS_STATS')).toBe(2));
      expect(countOf('GET_VOCAB_TAGS')).toBe(2);
    });
  });

  /* ================= Cổng chặn đăng nhập ================= */

  describe('cổng chặn đăng nhập', () => {
    it('chưa đăng nhập thì KHÔNG render tab nào', async () => {
      mockBackend(null, null);
      render(<App />);

      expect(await screen.findByRole('button', { name: 'Đăng nhập với Google' }))
        .toBeInTheDocument();
      expect(screen.queryByRole('tab', { name: 'Dịch' })).not.toBeInTheDocument();
      expect(screen.queryByRole('tab', { name: 'Sổ từ' })).not.toBeInTheDocument();
    });

    it('trong lúc đang đọc trạng thái thì KHÔNG nháy màn đăng nhập', async () => {
      // Nhảy thẳng vào màn đăng nhập rồi mới biết là đã đăng nhập sẽ nháy một cái ở MỖI
      // lần mở panel. Trạng thái "đang đọc" tồn tại vì lý do đó.
      let release!: (value: unknown) => void;
      transportSend.mockImplementation(
        async (request: { type: string }) => {
          if (request.type === 'GET_AUTH_STATE') {
            return new Promise((resolve) => { release = resolve; });
          }
          return { ok: true, data: null };
        },
      );
      render(<App />);

      expect(screen.queryByRole('button', { name: 'Đăng nhập với Google' }))
        .not.toBeInTheDocument();

      release({ ok: true, data: USER });
      expect(await screen.findByRole('tab', { name: 'Dịch' })).toBeInTheDocument();
    });

    it('đăng nhập rồi thì hiện email và đủ năm tab', async () => {
      mockBackend(null);
      render(<App />);

      expect(await screen.findByText('hiep@test.local')).toBeInTheDocument();
      expect(screen.getAllByRole('tab')).toHaveLength(5);
    });

    it('không lấy được trạng thái cũng coi như chưa đăng nhập, không treo màn trắng', async () => {
      transportSend.mockResolvedValue({
        ok: false, error: { code: 'BACKEND_DOWN', message: 'x', retryable: true },
      });
      render(<App />);

      expect(await screen.findByRole('button', { name: 'Đăng nhập với Google' }))
        .toBeInTheDocument();
    });

    it('đăng xuất đưa về màn đăng nhập và xoá kết quả dịch đang hiện', async () => {
      mockBackend(lastResult);
      render(<App />);
      await moTabDich();
      await screen.findByText('kiên cường');

      // Đường đăng xuất ở 1b nằm trên màn Hôm nay, không còn ở header.
      await userEvent.click(screen.getByRole('tab', { name: 'Hôm nay' }));
      await userEvent.click(await screen.findByRole('button', { name: 'Đăng xuất' }));

      expect(await screen.findByRole('button', { name: 'Đăng nhập với Google' }))
        .toBeInTheDocument();
      // Giữ lại kết quả của người vừa đăng xuất trên máy dùng chung là rò dữ liệu ngay
      // trên màn hình.
      expect(screen.queryByText('kiên cường')).not.toBeInTheDocument();
    });

    it('lỗi FORBIDDEN hiện hướng dẫn riêng, KHÔNG mời thử lại', async () => {
      transportSend.mockImplementation(
        async (request: { type: string }) => {
          if (request.type === 'GET_AUTH_STATE') return { ok: true, data: null };
          if (request.type === 'SIGN_IN') {
            return {
              ok: false,
              error: {
                code: 'FORBIDDEN',
                message: 'Tài khoản này chưa được cấp quyền dùng hệ thống',
                retryable: false,
              },
            };
          }
          return { ok: true, data: null };
        },
      );
      render(<App />);

      await userEvent.click(await screen.findByRole('button', { name: 'Đăng nhập với Google' }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('chưa được cấp quyền');
      // FORBIDDEN là trạng thái vĩnh viễn — bấm lại mười lần vẫn thế.
      expect(alert).not.toHaveTextContent('thử lại');
    });
  });
<<<<<<< Updated upstream

  it('có tab Thống kê và bấm vào thì chuyển sang đó', async () => {
    mockBackend(null);
    render(<App />);

    const tab = await screen.findByRole('tab', { name: 'Thống kê' });
    await userEvent.click(tab);

    expect(tab).toHaveAttribute('aria-selected', 'true');
  });
=======
>>>>>>> Stashed changes
});
