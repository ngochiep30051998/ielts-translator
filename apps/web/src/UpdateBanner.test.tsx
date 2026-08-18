import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { UpdateBanner } from './UpdateBanner';

/**
 * Banner "đã có bản mới".
 *
 * Cố ý KHÔNG tự tải lại trang: người dùng có thể đang gõ dở đoạn cần dịch hoặc đang làm dở
 * một câu quiz, mà cả hai chỉ nằm trong bộ nhớ. Tự reload là xoá đúng thứ họ đang làm.
 */

/** `subscribe` giả — trả về hàm bắn tín hiệu để test tự quyết định lúc nào "có bản mới". */
function taoSubscribe() {
  const nguoiNghe = new Set<() => void>();
  const huy = vi.fn();
  return {
    subscribe: (cb: () => void) => {
      nguoiNghe.add(cb);
      return () => {
        nguoiNghe.delete(cb);
        huy();
      };
    },
    bao: () => nguoiNghe.forEach((cb) => cb()),
    huy,
  };
}

describe('UpdateBanner', () => {
  it('chưa có bản mới thì không chiếm chỗ nào trên màn hình', () => {
    const { container } = render(<UpdateBanner subscribe={taoSubscribe().subscribe} apply={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('có bản mới thì hiện lời mời tải lại', async () => {
    const nguon = taoSubscribe();
    render(<UpdateBanner subscribe={nguon.subscribe} apply={vi.fn()} />);

    nguon.bao();

    expect(await screen.findByRole('status')).toHaveTextContent(/bản mới/i);
    expect(screen.getByRole('button', { name: 'Tải lại' })).toBeInTheDocument();
  });

  it('bấm "Tải lại" mới áp dụng bản mới', async () => {
    const nguon = taoSubscribe();
    const apply = vi.fn();
    render(<UpdateBanner subscribe={nguon.subscribe} apply={apply} />);
    nguon.bao();

    await userEvent.click(await screen.findByRole('button', { name: 'Tải lại' }));

    expect(apply).toHaveBeenCalledTimes(1);
  });

  it('"Để sau" đóng banner mà KHÔNG tải lại', async () => {
    const nguon = taoSubscribe();
    const apply = vi.fn();
    render(<UpdateBanner subscribe={nguon.subscribe} apply={apply} />);
    nguon.bao();

    await userEvent.click(await screen.findByRole('button', { name: 'Để sau' }));

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(apply).not.toHaveBeenCalled();
  });

  it('gỡ người nghe khi unmount — không giữ tham chiếu tới component đã chết', () => {
    const nguon = taoSubscribe();
    const { unmount } = render(<UpdateBanner subscribe={nguon.subscribe} apply={vi.fn()} />);

    unmount();

    expect(nguon.huy).toHaveBeenCalled();
  });
});
