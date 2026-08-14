import { describe, it, expect, vi } from 'vitest';

import { SHARE_PATH, readSharedText } from './share-target';
import manifestRaw from '../public/manifest.webmanifest?raw';

function gia(pathname: string, search: string) {
  const replaceState = vi.fn();
  return {
    location: { pathname, search } as Location,
    history: { replaceState } as unknown as History,
    replaceState,
  };
}

describe('readSharedText', () => {
  it('lấy text được chia sẻ', () => {
    const { location, history } = gia(SHARE_PATH, '?text=renewable%20energy');

    expect(readSharedText(location, history)).toBe('renewable energy');
  });

  it('ưu tiên `text` hơn `title`', () => {
    // Android đưa đoạn bôi đen vào `text`, còn `title` thường là tiêu đề trang — dịch tiêu
    // đề khi người ta muốn dịch đoạn văn là sai việc.
    const { location, history } = gia(SHARE_PATH, '?title=Tieu%20de&text=doan%20van');

    expect(readSharedText(location, history)).toBe('doan van');
  });

  it('không có `text` thì lui về `title`', () => {
    const { location, history } = gia(SHARE_PATH, '?title=Tieu%20de');

    expect(readSharedText(location, history)).toBe('Tieu de');
  });

  it('KHÔNG dùng `url` — dịch một địa chỉ web không ra nghĩa gì', () => {
    const { location, history } = gia(SHARE_PATH, '?url=https%3A%2F%2Fexample.com');

    expect(readSharedText(location, history)).toBeNull();
  });

  it('dọn URL sau khi đọc — text chia sẻ không nằm lại trong lịch sử trình duyệt', () => {
    // Với một app dịch thuật, đoạn được chia sẻ có thể là thứ riêng tư người dùng vừa bôi
    // đen ở đâu đó. Để nguyên trong thanh địa chỉ là rò nó ra màn hình.
    const { location, history, replaceState } = gia(SHARE_PATH, '?text=bi%20mat');

    readSharedText(location, history);

    expect(replaceState).toHaveBeenCalledWith({}, '', '/');
  });

  it('đường dẫn khác thì không đụng gì', () => {
    const { location, history, replaceState } = gia('/', '?text=abc');

    expect(readSharedText(location, history)).toBeNull();
    expect(replaceState).not.toHaveBeenCalled();
  });

  it('chia sẻ chuỗi rỗng hoặc toàn khoảng trắng trả null', () => {
    const rong = gia(SHARE_PATH, '?text=');
    const khoangTrang = gia(SHARE_PATH, '?text=%20%20%20');

    expect(readSharedText(rong.location, rong.history)).toBeNull();
    expect(readSharedText(khoangTrang.location, khoangTrang.history)).toBeNull();
  });
});

describe('manifest khớp với mã nguồn', () => {
  const manifest = JSON.parse(manifestRaw) as Record<string, any>;

  it('share_target.action trùng SHARE_PATH', () => {
    // Lệch hai chỗ này thì Android gửi người dùng tới một đường dẫn mà `readSharedText`
    // không nhận ra: app mở lên trống trơn, text chia sẻ biến mất, không lỗi nào giải thích.
    expect(manifest.share_target.action).toBe(SHARE_PATH);
  });

  it('share_target dùng GET', () => {
    // POST share target BẮT BUỘC phải có service worker chặn request, nên nó hỏng ở đúng
    // lần dùng đầu tiên — lúc SW chưa active.
    expect(String(manifest.share_target.method ?? 'GET').toUpperCase()).toBe('GET');
  });

  it('khai đúng ba tham số mà readSharedText biết đọc', () => {
    expect(manifest.share_target.params).toMatchObject({ text: 'text', title: 'title' });
  });

  it('cài được vào màn hình chính: standalone + start_url + icon 192 và 512', () => {
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/');
    const co = (n: string) => manifest.icons.some((i: any) => i.sizes === n);
    // 192 và 512 là hai cỡ Chrome đòi để hiện lời mời "Add to Home Screen".
    expect(co('192x192')).toBe(true);
    expect(co('512x512')).toBe(true);
  });
});
