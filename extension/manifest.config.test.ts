// @vitest-environment node
//
// Node chứ không jsdom: file này import `manifest.config.ts`, vốn kéo theo `vite` → esbuild.
// esbuild khẳng định `new TextEncoder().encode('') instanceof Uint8Array`, mà `TextEncoder`
// của jsdom là một lớp khác nên khẳng định đó sai và cả suite chết ngay lúc nạp — với một
// thông điệp nói rằng "môi trường JavaScript của bạn hỏng", chẳng liên quan gì tới test.
import { describe, expect, it } from 'vitest';

import manifest from './manifest.config';
import { toHostPermission } from './src/shared/backend-url';
import { DEFAULT_SETTINGS } from './src/shared/settings';

type ManifestFactory = (env: { mode: string; command: string }) => Promise<unknown> | unknown;

async function build(mode = 'production') {
  const ket_qua = await (manifest as unknown as ManifestFactory)({ mode, command: 'build' });
  return ket_qua as { host_permissions: string[] };
}

describe('ràng buộc #10 — manifest và bundle không được lệch nhau', () => {
  it('host_permissions phủ đúng backendUrl mặc định của bundle', async () => {
    // Bất biến quan trọng nhất của cả tính năng này. Chrome chỉ cho gọi origin đã khai
    // trong manifest; lệch nhau thì extension cài được, nhìn bình thường, và MỌI request
    // chết im lặng — không lỗi mạng, không lỗi CORS, `fetch` đơn giản là không bao giờ đi.
    //
    // Test đọc CẢ HAI qua đúng đường production đọc: manifest qua `loadEnv` ở Node,
    // `DEFAULT_SETTINGS` qua `import.meta.env` đã nhúng lúc build. Hai đường khác nhau,
    // cùng một biến — đó chính là thứ cần chứng minh.
    const { host_permissions } = await build();

    expect(host_permissions).toContain(toHostPermission(DEFAULT_SETTINGS.backendUrl));
  });

  it('luôn khai backend local để đổi qua lại mà không phải build lại', async () => {
    const { host_permissions } = await build();

    expect(host_permissions).toContain('http://127.0.0.1:8080/*');
  });

  it('mọi mẫu đều hợp lệ ở mức origin và không trùng nhau', async () => {
    const { host_permissions } = await build();

    for (const pattern of host_permissions) {
      // Chrome từ chối NGUYÊN CẢ manifest nếu một mẫu sai, và không chỉ ra mẫu nào.
      expect(pattern).toMatch(/^https?:\/\/[^/]+\/\*$/);
    }
    expect(new Set(host_permissions).size).toBe(host_permissions.length);
  });
});
