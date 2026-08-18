import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

/**
 * Đóng dấu vân tay của bản build vào `sw.js`.
 *
 * Trình duyệt chỉ coi là "có bản mới" khi **nội dung file service worker khác đi** — nó so
 * từng byte với bản đã đăng ký. `public/sw.js` là file tĩnh, tên không mang hash, nên deploy
 * một bundle mới toanh mà không đụng tới nó thì `updatefound` KHÔNG BAO GIỜ nổ. Lỗi đó im
 * lặng tuyệt đối: mọi thứ trông vẫn chạy, chỉ là người dùng chạy mã cũ mãi.
 *
 * Vân tay lấy từ TÊN các file asset đã build, mà tên asset đã chứa content hash — nên code
 * không đổi thì id không đổi (không làm phiền bằng một banner vô nghĩa), code đổi thì id đổi.
 *
 * **Viết bằng JS thuần, không phải TS**, và kiểu khai riêng ở `sw-build-id.d.ts`: file này
 * cần `node:fs`/`node:path`, mà gõ kiểu cho chúng đòi `@types/node` — một dependency mới,
 * tức phải hỏi trước (ràng buộc #12). Cùng lối với `scripts/make-icons.mjs`.
 *
 * Đuôi `.js` chứ không `.mjs`: `apps/web/package.json` đã khai `"type": "module"` nên `.js`
 * ở đây vốn là ESM, và esbuild (bộ nạp `vite.config.ts`) không tự thử đuôi `.mjs`.
 */

/** Chỗ giữ chỗ trong `public/sw.js`, thay bằng id thật lúc build. */
export const BUILD_ID_TOKEN = '__BUILD_ID__';

/** 12 hex ký tự — quá đủ để phân biệt các bản build, và vẫn liếc mắt đọc được. */
const DO_DAI = 12;

/**
 * Vân tay của một danh sách tên file. Sắp xếp trước vì Rollup không hứa thứ tự.
 *
 * @param {Iterable<string>} fileNames
 * @returns {string}
 */
export function buildIdFrom(fileNames) {
  return createHash('sha256')
    .update([...fileNames].sort().join('\n'))
    .digest('hex')
    .slice(0, DO_DAI);
}

/**
 * Thay chỗ giữ chỗ trong nguồn `sw.js`. Ném nếu không thấy — xem test để biết vì sao.
 *
 * @param {string} source
 * @param {string} buildId
 * @returns {string}
 */
export function stampBuildId(source, buildId) {
  if (!source.includes(BUILD_ID_TOKEN)) {
    throw new Error(
      `Không thấy ${BUILD_ID_TOKEN} trong sw.js — luồng báo bản mới sẽ chết im lặng.`,
    );
  }
  return source.replaceAll(BUILD_ID_TOKEN, buildId);
}

/**
 * Plugin Vite: đóng vân tay bản build vào `dist/sw.js`.
 *
 * Chạy ở `closeBundle` chứ không sớm hơn: `public/` được chép sang `dist/` ở cuối lượt build,
 * nên sửa sớm hơn là bị chính lượt chép đó ghi đè — và ghi đè kiểu im lặng, build vẫn xanh.
 *
 * @returns {import('vite').Plugin}
 */
export function swBuildId() {
  let outDir = 'dist';
  let buildId = '';

  return {
    name: 'ielts:sw-build-id',
    apply: 'build',

    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir);
    },

    generateBundle(_options, bundle) {
      // Tên file trong bundle đã chứa content hash, nên id chỉ đổi khi code đổi.
      buildId = buildIdFrom(Object.keys(bundle));
    },

    closeBundle() {
      const duongDan = path.join(outDir, 'sw.js');
      if (!existsSync(duongDan)) {
        throw new Error(`Không thấy ${duongDan} — service worker không vào được bản build.`);
      }
      writeFileSync(duongDan, stampBuildId(readFileSync(duongDan, 'utf-8'), buildId), 'utf-8');
    },
  };
}
