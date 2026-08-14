import { describe, it, expect, vi } from 'vitest';

import { readAuthError } from './auth-error';

function gia(search: string) {
  const replaceState = vi.fn();
  const location = { search, pathname: '/' } as Location;
  const history = { replaceState } as unknown as History;
  return { location, history, replaceState };
}

describe('readAuthError', () => {
  it('không có tham số thì trả null và không đụng URL', () => {
    const { location, history, replaceState } = gia('');

    expect(readAuthError(location, history)).toBeNull();
    expect(replaceState).not.toHaveBeenCalled();
  });

  it('đọc được FORBIDDEN kèm thông điệp tiếng Việt', () => {
    const { location, history } = gia('?authError=FORBIDDEN');

    const loi = readAuthError(location, history);

    expect(loi).toMatchObject({ code: 'FORBIDDEN', retryable: false });
    expect(loi?.message).toContain('chưa được cấp quyền');
  });

  it('UNAUTHORIZED là lỗi thử lại được, FORBIDDEN thì không', () => {
    // Phân biệt này quyết định câu hướng dẫn mà LoginScreen hiện ra: một bên "bấm để thử
    // lại", bên kia "nhờ quản trị thêm email". Trộn hai mã là chỉ sai đường hồi phục.
    const a = gia('?authError=UNAUTHORIZED');
    const b = gia('?authError=FORBIDDEN');

    expect(readAuthError(a.location, a.history)).toMatchObject({ retryable: true });
    expect(readAuthError(b.location, b.history)).toMatchObject({ retryable: false });
  });

  it('AUTH_UNAVAILABLE là lỗi tạm thời của Google, thử lại được', () => {
    const { location, history } = gia('?authError=AUTH_UNAVAILABLE');

    expect(readAuthError(location, history)).toMatchObject({
      code: 'AUTH_UNAVAILABLE',
      retryable: true,
    });
  });

  it('xoá tham số khỏi URL sau khi đọc', () => {
    // Không xoá thì F5 sau một lần đăng nhập lỗi lại hiện đúng thông báo đó, kể cả khi lần
    // này đã vào được.
    const { location, history, replaceState } = gia('?authError=UNAUTHORIZED');

    readAuthError(location, history);

    expect(replaceState).toHaveBeenCalledWith({}, '', '/');
  });

  it('giữ lại các tham số khác khi xoá', () => {
    const { location, history, replaceState } = gia('?authError=UNAUTHORIZED&text=hello');

    readAuthError(location, history);

    expect(replaceState).toHaveBeenCalledWith({}, '', '/?text=hello');
  });

  it('mã lạ trả null nhưng vẫn dọn URL', () => {
    // URL sửa tay. Không dựng thông điệp từ chuỗi người ngoài đưa vào.
    const { location, history, replaceState } = gia('?authError=<script>');

    expect(readAuthError(location, history)).toBeNull();
    expect(replaceState).toHaveBeenCalled();
  });
});
