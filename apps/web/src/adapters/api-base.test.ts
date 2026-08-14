import { describe, it, expect } from 'vitest';

import { resolveApiBase } from './api-base';

const TRANG = 'https://ielts-translator.vercel.app';

describe('resolveApiBase', () => {
  it('không đặt gì thì dùng đường dẫn tương đối, không cảnh báo', () => {
    expect(resolveApiBase(undefined, TRANG)).toEqual({ baseUrl: '', canhBao: null });
  });

  it('chuỗi rỗng và chuỗi toàn khoảng trắng cũng vậy', () => {
    expect(resolveApiBase('', TRANG).baseUrl).toBe('');
    expect(resolveApiBase('   ', TRANG).baseUrl).toBe('');
  });

  it('cắt dấu / thừa ở cuối — ApiClient tự nối "/api/..." vào sau', () => {
    // Không cắt thì URL thành `https://x//api/vocab`, và một số proxy coi đó là đường dẫn
    // khác hẳn.
    expect(resolveApiBase('https://ielts-translator.vercel.app///', TRANG).baseUrl).toBe(
      'https://ielts-translator.vercel.app',
    );
  });

  it('cùng origin thì không cảnh báo', () => {
    expect(resolveApiBase(TRANG, TRANG).canhBao).toBeNull();
  });

  it('đường dẫn tương đối vẫn là cùng origin', () => {
    expect(resolveApiBase('/api-v2', TRANG)).toEqual({ baseUrl: '/api-v2', canhBao: null });
  });

  it('khác origin thì CẢNH BÁO, và nói rõ phải sửa gì', () => {
    // Đây là ca thất bại im lặng tệ nhất của cả web app: request vẫn đi, không có lỗi CORS,
    // chỉ là cookie không được gửi kèm nên mọi thứ trả 401 dù đã đăng nhập.
    const { canhBao } = resolveApiBase('https://api.example.com', TRANG);

    expect(canhBao).toContain('https://api.example.com');
    expect(canhBao).toContain(TRANG);
    expect(canhBao).toContain('SameSite');
    expect(canhBao).toContain('allow_credentials');
  });

  it('khác cổng cũng là khác origin', () => {
    // Bẫy hay gặp lúc dev: `localhost:5174` và `localhost:8080` KHÔNG cùng origin.
    expect(resolveApiBase('http://localhost:8080', 'http://localhost:5174').canhBao).not.toBeNull();
  });

  it('khác scheme cũng là khác origin', () => {
    expect(
      resolveApiBase('http://ielts-translator.vercel.app', TRANG).canhBao,
    ).not.toBeNull();
  });

  it('URL rác thì cảnh báo chứ không ném', () => {
    const { canhBao } = resolveApiBase('cái này không phải url', TRANG);

    expect(canhBao).toContain('không phải URL hợp lệ');
  });
});
