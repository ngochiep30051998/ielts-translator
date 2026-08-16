/**
 * Đếm số từ đã lưu vào sổ TRONG NGÀY — con số của chip "+N từ hôm nay" trên bubble.
 *
 * Nó là một con số động viên, không phải dữ liệu học: sống trong `chrome.storage.local`,
 * không đi đâu cả, và sang ngày mới thì về 0. Vì thế nó KHÔNG hỏi backend — thêm một
 * endpoint cho một dòng chữ nhỏ trên bubble là đổi sai thứ lấy đúng thứ.
 */

const STORAGE_KEY = 'dailySaves';

interface DailySaves {
  /** "YYYY-MM-DD" theo ngày của MÁY. */
  date: string;
  count: number;
}

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/**
 * "YYYY-MM-DD" theo ngày của máy người dùng.
 *
 * Tự ghép chứ KHÔNG dùng `toISOString()`: hàm đó đổi sang UTC, nên ở múi giờ +07 thì
 * 06:00 ngày 15 thành 23:00 ngày 14 — chip về 0 vào giữa buổi sáng mà không có lỗi nào.
 */
export function todayKey(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/**
 * Đọc bản ghi đang lưu. **Không bao giờ ném.**
 *
 * Reload extension biến content script trên các tab đang mở thành mồ côi, và
 * `chrome.storage.local` của chúng ném "Extension context invalidated".
 */
async function readRaw(): Promise<DailySaves | null> {
  try {
    const stored = await chrome.storage.local.get([STORAGE_KEY]);
    const raw = stored[STORAGE_KEY] as Partial<DailySaves> | undefined;
    if (!raw || typeof raw.date !== 'string' || typeof raw.count !== 'number') return null;
    return { date: raw.date, count: raw.count };
  } catch {
    return null;
  }
}

/** Số từ đã lưu trong ngày `now`. Bản ghi của ngày khác đọc thành 0. */
export async function readDailySaves(now: Date = new Date()): Promise<number> {
  const saved = await readRaw();
  return saved && saved.date === todayKey(now) ? saved.count : 0;
}

/**
 * Ghi nhận thêm một từ vừa lưu, trả về số mới của ngày hôm nay.
 *
 * Bản ghi của ngày cũ bị GHI ĐÈ chứ không cộng dồn — đó chính là cách chip về 0 lúc sang
 * ngày, không cần alarm hay dọn dẹp gì.
 */
export async function bumpDailySaves(now: Date = new Date()): Promise<number> {
  const today = todayKey(now);
  const saved = await readRaw();
  const next = (saved && saved.date === today ? saved.count : 0) + 1;
  try {
    await chrome.storage.local.set({ [STORAGE_KEY]: { date: today, count: next } satisfies DailySaves });
  } catch {
    // Ghi hỏng thì coi như chưa đếm được: trả 0 để bubble ẩn chip đi, thay vì hiện một
    // con số sẽ biến mất ở lần dịch sau.
    return 0;
  }
  return next;
}
