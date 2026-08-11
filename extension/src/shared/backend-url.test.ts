import { describe, expect, it } from 'vitest';

import {
  DEFAULT_BACKEND_URL,
  hostPermissionsFor,
  normaliseBackendUrl,
  toHostPermission,
} from './backend-url';

describe('normaliseBackendUrl', () => {
  it('chưa đặt thì về backend local', () => {
    expect(normaliseBackendUrl(undefined)).toBe(DEFAULT_BACKEND_URL);
  });

  it('chuỗi rỗng hoặc chỉ khoảng trắng cũng về backend local', () => {
    // Một `.env` có dòng `VITE_BACKEND_URL=` (khai mà quên điền) sẽ dựng ra
    // `fetch('/api/health')` — trỏ vào chính trang người dùng đang mở, và thông điệp lỗi
    // sẽ nói về trang đó chứ không nói gì về cấu hình sai.
    expect(normaliseBackendUrl('')).toBe(DEFAULT_BACKEND_URL);
    expect(normaliseBackendUrl('   ')).toBe(DEFAULT_BACKEND_URL);
  });

  it('cắt dấu / thừa ở cuối', () => {
    expect(normaliseBackendUrl('https://x.vercel.app/')).toBe('https://x.vercel.app');
    expect(normaliseBackendUrl('https://x.vercel.app///')).toBe('https://x.vercel.app');
  });
});

describe('toHostPermission', () => {
  it('rút về origin rồi mới thêm /*', () => {
    // Chrome chỉ nhận mẫu ở mức origin. Nối chuỗi thô một URL có đường dẫn sẽ làm Chrome
    // từ chối NGUYÊN CẢ manifest, và thông báo lỗi của nó không chỉ ra dòng nào sai.
    expect(toHostPermission('https://x.vercel.app/api')).toBe('https://x.vercel.app/*');
    expect(toHostPermission('http://127.0.0.1:8080')).toBe('http://127.0.0.1:8080/*');
  });
});

describe('hostPermissionsFor', () => {
  it('luôn giữ backend local để đổi qua lại mà không phải build lại', () => {
    expect(hostPermissionsFor('https://x.vercel.app')).toEqual([
      'http://127.0.0.1:8080/*',
      'https://x.vercel.app/*',
    ]);
  });

  it('trỏ vào chính local thì không khai trùng hai lần', () => {
    expect(hostPermissionsFor(DEFAULT_BACKEND_URL)).toEqual(['http://127.0.0.1:8080/*']);
  });
});
