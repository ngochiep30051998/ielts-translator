import { beforeEach, describe, expect, it, vi } from 'vitest';
import { refreshBadge } from './badge';
import { saveAuth } from '../shared/auth-storage';

describe('refreshBadge', () => {
  beforeEach(async () => {
    vi.mocked(chrome.action.setBadgeText).mockClear();
    await chrome.storage.local.clear();
    // Badge chỉ có nghĩa khi đã đăng nhập; ca chưa đăng nhập có test riêng bên dưới.
    await saveAuth('test-token', { email: 'a@b.com', displayName: null, pictureUrl: null });
  });

  it('chưa đăng nhập thì KHÔNG gọi API và xoá số trên badge', async () => {
    await chrome.storage.local.clear();
    const srsStats = vi.fn();

    await refreshBadge({ srsStats });

    // Alarm chạy 30 phút một lần. Không chặn ở đây là cứ 30 phút một request 401, log rác,
    // và badge treo số cũ — con số của NGƯỜI DÙNG TRƯỚC trên một máy dùng chung.
    expect(srsStats).not.toHaveBeenCalled();
    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '' });
  });

  it('hiện số thẻ đến hạn', async () => {
    await refreshBadge({ srsStats: async () => ({ dueCount: 7, newCount: 2, learnedCount: 30 }) });

    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '7' });
  });

  it('không còn thẻ nào thì xoá badge thay vì hiện số 0', async () => {
    await refreshBadge({ srsStats: async () => ({ dueCount: 0, newCount: 0, learnedCount: 30 }) });

    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '' });
  });

  it('backend chết thì xoá badge, không ném lỗi và không giữ số cũ đã lỗi thời', async () => {
    await expect(
      refreshBadge({
        srsStats: async () => {
          throw new Error('backend down');
        },
      }),
    ).resolves.toBeUndefined();

    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '' });
  });

  it('truyền hạn mức từ mới trong cài đặt xuống backend', async () => {
    const srsStats = vi.fn(async () => ({ dueCount: 1, newCount: 1, learnedCount: 0 }));
    await chrome.storage.local.set({ settings: { newWordsPerDay: 5 } });

    await refreshBadge({ srsStats });

    expect(srsStats).toHaveBeenCalledWith(5);
  });
});
