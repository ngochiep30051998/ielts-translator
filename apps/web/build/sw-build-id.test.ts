import { describe, it, expect } from 'vitest';

import { BUILD_ID_TOKEN, buildIdFrom, stampBuildId } from './sw-build-id';

/**
 * Dấu vân tay của một bản build, đóng vào `sw.js` lúc build.
 *
 * Đây là điều kiện CẦN của cả luồng báo bản mới: trình duyệt chỉ coi là "có bản mới" khi
 * NỘI DUNG file service worker khác đi. Deploy code mới mà `sw.js` giống hệt byte cũ thì
 * không có sự kiện `updatefound` nào cả — banner sẽ không bao giờ hiện, và lỗi đó im lặng
 * tuyệt đối: mọi thứ trông vẫn chạy, chỉ là người dùng chạy mã cũ mãi mãi.
 */
describe('buildIdFrom', () => {
  it('cùng một danh sách asset → cùng một id', () => {
    const a = buildIdFrom(['assets/index-abc123.js', 'assets/index-def456.css']);
    const b = buildIdFrom(['assets/index-abc123.js', 'assets/index-def456.css']);

    expect(a).toBe(b);
  });

  it('không phụ thuộc thứ tự — Rollup không hứa thứ tự file trong bundle', () => {
    const xuoi = buildIdFrom(['a-1.js', 'b-2.css']);
    const nguoc = buildIdFrom(['b-2.css', 'a-1.js']);

    expect(xuoi).toBe(nguoc);
  });

  it('đổi một hash asset → đổi id', () => {
    const cu = buildIdFrom(['assets/index-abc123.js']);
    const moi = buildIdFrom(['assets/index-zzz999.js']);

    expect(moi).not.toBe(cu);
  });

  it('id ngắn và chỉ gồm ký tự an toàn cho tên cache', () => {
    expect(buildIdFrom(['assets/index-abc123.js'])).toMatch(/^[0-9a-f]{12}$/);
  });
});

describe('stampBuildId', () => {
  it('thay chỗ giữ chỗ bằng id thật', () => {
    const nguon = `const BUILD_ID = '${BUILD_ID_TOKEN}';`;

    expect(stampBuildId(nguon, 'deadbeef1234')).toBe("const BUILD_ID = 'deadbeef1234';");
  });

  it('NÉM khi không tìm thấy chỗ giữ chỗ', () => {
    // Không ném thì một lần đổi tên biến trong `sw.js` sẽ lặng lẽ tắt luồng báo bản mới:
    // build vẫn xanh, deploy vẫn chạy, chỉ là không ai được báo có bản mới nữa.
    expect(() => stampBuildId('const BUILD_ID = "v1";', 'deadbeef1234')).toThrow(/__BUILD_ID__/);
  });
});
