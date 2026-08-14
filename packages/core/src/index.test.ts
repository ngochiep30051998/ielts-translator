import { describe, it, expect } from 'vitest';

/**
 * Bất biến của cả package: `@ielts/core` KHÔNG được biết gì về Chrome.
 *
 * Vi phạm ràng buộc này không làm gì đỏ theo cách tự nhiên — extension vẫn chạy ngon, vì
 * `chrome` có thật ở đó. Nó chỉ nổ ở web, lúc chạy, dưới dạng `chrome is not defined` giữa
 * một màn hình trắng. Thứ mình cần luôn là một port mới trong `ports.ts`.
 *
 * `?raw` + `eager` để Vite nhúng thẳng nội dung file lúc build test — không phải đọc đĩa,
 * nên không phải kéo `@types/node` vào chỉ vì một lời gọi (ràng buộc #12).
 */
const SOURCES = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/**
 * Bỏ chú thích trước khi soi.
 *
 * Chú thích NÓI về `chrome.storage` là chuyện bình thường và cần thiết — `ports.ts` giải
 * thích chính xác vì sao từng port tồn tại, và giải thích đó phải nêu tên thứ nó thay thế.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1');
}

describe('bất biến của @ielts/core', () => {
  it('có quét được mã nguồn — nếu không thì mọi khẳng định dưới đây là vô nghĩa', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(20);
    expect(Object.keys(SOURCES)).toContain('./ports.ts');
  });

  it('stripComments giữ lại mã và chỉ bỏ chú thích', () => {
    // Không có test này thì một `stripComments` hỏng (trả chuỗi rỗng) làm hai khẳng định
    // dưới đây xanh vĩnh viễn — đúng loại test tệ nhất: có mặt, luôn xanh, canh không gì.
    const mau = [
      '/* chrome.storage trong chú thích khối */',
      '// chrome.runtime trong chú thích dòng',
      'const url = "https://x/y"; // giữ lại dấu // trong chuỗi',
      'const a = chrome.tabs;',
    ].join('\n');

    const sach = stripComments(mau);

    expect(sach).toContain('const a = chrome.tabs;');
    expect(sach).toContain('https://x/y');
    expect(sach).not.toContain('chrome.storage');
    expect(sach).not.toContain('chrome.runtime');
  });

  it('không file nào chạm `chrome.` trong mã thật', () => {
    const viPham = Object.entries(SOURCES)
      .filter(([, source]) => /\bchrome\s*\./.test(stripComments(source)))
      .map(([path]) => path);

    expect(viPham).toEqual([]);
  });

  it('không file nào chạm `localStorage` hay `sessionStorage` trong mã thật', () => {
    // Cùng lý do với `chrome.`: service worker của extension KHÔNG có hai thứ này, nên
    // dùng chúng trong core là làm hỏng extension theo hướng ngược lại.
    const viPham = Object.entries(SOURCES)
      .filter(([, source]) => /\b(local|session)Storage\b/.test(stripComments(source)))
      .map(([path]) => path);

    expect(viPham).toEqual([]);
  });
});
