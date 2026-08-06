import { loadSettings } from '../shared/settings';
import type { SrsStats } from '../shared/types';

/** Chỉ cần đúng một method — để test không phải dựng cả ApiClient. */
export interface BadgeSource {
  srsStats(newLimit: number): Promise<SrsStats>;
}

const BADGE_COLOR = '#4f46e5';

/**
 * Cập nhật số thẻ đến hạn trên icon extension.
 *
 * <p>Backend chết thì XOÁ badge chứ không giữ số cũ — một con số lỗi thời còn tệ hơn
 * không có số, vì nó khiến người dùng tưởng vẫn còn bài để ôn.
 */
export async function refreshBadge(source: BadgeSource): Promise<void> {
  let text = '';
  try {
    const { newWordsPerDay } = await loadSettings();
    const stats = await source.srsStats(newWordsPerDay);
    text = stats.dueCount > 0 ? String(stats.dueCount) : '';
  } catch {
    text = '';
  }

  await chrome.action.setBadgeBackgroundColor({ color: BADGE_COLOR });
  await chrome.action.setBadgeText({ text });
}
