import { describe, it, expect, beforeEach, vi } from 'vitest';
import { bumpDailySaves, readDailySaves, todayKey } from './daily-saves';

const HOM_NAY = new Date(2026, 7, 15);
const NGAY_MAI = new Date(2026, 7, 16);

describe('todayKey', () => {
  it('theo NGÀY của máy, không phải UTC', () => {
    // `toISOString()` đổi sang UTC, nên ở múi giờ +07 thì 06:00 ngày 15 thành 23:00 ngày 14
    // — chip "hôm nay" về 0 vào giữa buổi sáng mà không có lỗi nào.
    expect(todayKey(new Date(2026, 7, 15, 6, 0))).toBe('2026-08-15');
  });
});

describe('đếm số từ đã lưu trong ngày', () => {
  beforeEach(async () => {
    await chrome.storage.local.clear();
  });

  it('chưa lưu từ nào thì đếm 0', async () => {
    expect(await readDailySaves(HOM_NAY)).toBe(0);
  });

  it('mỗi lượt lưu cộng một', async () => {
    expect(await bumpDailySaves(HOM_NAY)).toBe(1);
    expect(await bumpDailySaves(HOM_NAY)).toBe(2);
    expect(await readDailySaves(HOM_NAY)).toBe(2);
  });

  it('sang ngày mới thì về 0', async () => {
    await bumpDailySaves(HOM_NAY);
    await bumpDailySaves(HOM_NAY);

    expect(await readDailySaves(NGAY_MAI)).toBe(0);
  });

  it('lượt lưu đầu tiên của ngày mới đếm lại từ 1, không cộng dồn vào ngày cũ', async () => {
    await bumpDailySaves(HOM_NAY);

    expect(await bumpDailySaves(NGAY_MAI)).toBe(1);
  });

  it('storage ném thì trả 0 chứ KHÔNG nổ ra ngoài', async () => {
    // Reload extension biến content script trên các tab đang mở thành mồ côi, và
    // `chrome.storage.local` của chúng ném "Extension context invalidated". Một con số
    // động viên không được phép làm chết cả luồng dịch.
    // Context mồ côi làm hỏng CẢ hai chiều, nên giả lập cả hai — mock mỗi `get` sẽ cho
    // `bumpDailySaves` một đường thoát không tồn tại ngoài đời.
    const loi = new Error('Extension context invalidated');
    const get = vi.spyOn(chrome.storage.local, 'get').mockRejectedValue(loi);
    const set = vi.spyOn(chrome.storage.local, 'set').mockRejectedValue(loi);

    expect(await readDailySaves(HOM_NAY)).toBe(0);
    expect(await bumpDailySaves(HOM_NAY)).toBe(0);

    get.mockRestore();
    set.mockRestore();
  });
});
