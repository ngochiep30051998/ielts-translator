import { beforeEach, describe, expect, it, vi } from 'vitest';
import { refreshBadge } from './badge';

describe('refreshBadge', () => {
  beforeEach(async () => {
    vi.mocked(chrome.action.setBadgeText).mockClear();
    await chrome.storage.local.clear();
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
