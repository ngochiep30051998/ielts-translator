import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import type { AuthUser, TranslateResult } from '../types';
import { transportSend } from '../../vitest.setup';

const USER: AuthUser = { email: 'hiep@test.local', displayName: 'Hiep', pictureUrl: null };

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
        default:
          return { ok: true, data: null };
      }
    },
  );
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

    expect(await screen.findByDisplayValue('renewable energy')).toBeInTheDocument();
  });

  it('initialDraft THẮNG kết quả dịch lần trước', async () => {
    // Ghi đè đoạn người dùng vừa cố ý chia sẻ bằng nháp cũ là vứt đi đúng thứ họ vừa gửi tới.
    mockBackend(lastResult);

    render(<App initialDraft="doan moi chia se" />);

    expect(await screen.findByDisplayValue('doan moi chia se')).toBeInTheDocument();
    expect(screen.queryByDisplayValue(lastResult.sourceText)).not.toBeInTheDocument();
  });

  it('không có initialDraft thì vẫn tự điền từ kết quả gần nhất như cũ', async () => {
    mockBackend(lastResult);

    render(<App />);

    expect(await screen.findByDisplayValue(lastResult.sourceText)).toBeInTheDocument();
  });

  it('đọc kết quả gần nhất một lần và hiện ở tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);

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

    expect(await screen.findByDisplayValue('was resiliented')).toBeInTheDocument();
  });

  it('đổi sang tab khác rồi quay lại vẫn giữ nguyên text đang gõ dở', async () => {
    mockBackend(null);
    render(<App />);

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
    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'renewable');
    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    // Khoá đường nối App → TranslateTab: nếu App không truyền đúng onResult xuống,
    // TranslateTab vẫn gọi được onResult nhưng App không cập nhật state result,
    // nên panel không bao giờ hiện kết quả.
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
    // Dịch xong không được đụng vào nội dung ô nhập (spec §2).
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('renewable');
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
      await screen.findByText('kiên cường');

      await userEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }));

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

  it('có tab Thống kê và bấm vào thì chuyển sang đó', async () => {
    mockBackend(null);
    render(<App />);

    const tab = await screen.findByRole('tab', { name: 'Thống kê' });
    await userEvent.click(tab);

    expect(tab).toHaveAttribute('aria-selected', 'true');
  });
});
