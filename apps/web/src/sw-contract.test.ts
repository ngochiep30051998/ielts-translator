import { describe, it, expect } from 'vitest';

// `?raw` của Vite: nạp nguyên văn nội dung file thay vì thực thi nó. Đọc bằng `node:fs` +
// `import.meta.url` không dùng được ở đây — dưới jsdom, `import.meta.url` là URL http.
import NGUON from '../public/sw.js?raw';

/**
 * Bỏ chú thích trước khi đếm lời gọi.
 *
 * Chú thích trong `sw.js` có NHẮC TỚI `skipWaiting()` để giải thích vì sao không gọi nó —
 * đếm cả chú thích thì chính lời giải thích đó làm test đỏ, và cách "sửa" hiển nhiên là xoá
 * lời giải thích đi.
 */
const MA = NGUON.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

/**
 * Hợp đồng giữa `public/sw.js` và luồng báo bản mới ở `sw-update.ts`.
 *
 * Đọc mã nguồn bằng regex là cách kiểm thô, nhưng ở đây nó bù cho một khoảng trống thật:
 * service worker chạy trong môi trường không dựng lại được bằng jsdom, mà ba điều dưới đây
 * hỏng thì **không có gì đỏ cả** — app vẫn chạy, vẫn offline được, chỉ là người dùng không
 * bao giờ được báo có bản mới và cứ chạy mã cũ mãi.
 */

describe('hợp đồng của service worker', () => {
  it('có chỗ giữ chỗ __BUILD_ID__ để build đóng dấu vào', () => {
    // Trình duyệt so từng byte file sw.js để biết có bản mới. Không có dấu này thì file
    // giống hệt nhau qua mọi lần deploy và `updatefound` không bao giờ nổ.
    expect(NGUON).toContain('__BUILD_ID__');
  });

  it('KHÔNG tự giành quyền lúc install — phải đợi người dùng bấm', () => {
    // `skipWaiting()` trong `install` làm worker mới nhảy vào ngay, không bao giờ ở trạng
    // thái `waiting`, nên phía client không có gì để phát hiện và banner không bao giờ hiện.
    const soLanGoi = MA.match(/skipWaiting\(\)/g)?.length ?? 0;
    expect(soLanGoi).toBe(1);
    // Lần gọi duy nhất đó phải nằm trong nhánh xử lý message SKIP_WAITING.
    expect(MA).toMatch(/SKIP_WAITING[\s\S]{0,300}skipWaiting\(\)/);
  });

  it('cache vỏ mang BUILD_ID, cache API thì KHÔNG', () => {
    // Vỏ (HTML + asset) phải bị dọn theo từng bản, không thì bản mới vẫn ăn asset cũ.
    // Cache API thì ngược lại: xoá nó theo mỗi bản là mỗi lần deploy lại lấy mất sổ từ đã
    // tải về của người đang offline.
    expect(NGUON).toMatch(/CACHE_SHELL\s*=\s*`ielts-shell-\$\{BUILD_ID\}`/);
    expect(NGUON).toMatch(/CACHE_API\s*=\s*'ielts-api-[^']+'/);
    expect(NGUON).not.toMatch(/CACHE_API\s*=\s*`[^`]*\$\{BUILD_ID\}/);
  });
});
