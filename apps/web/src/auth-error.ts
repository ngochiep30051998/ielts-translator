import type { ApiError } from '@ielts/core';

/**
 * Thông điệp cho từng mã lỗi mà `/api/auth/google/callback` có thể gửi về.
 *
 * Backend không gửi kèm câu chữ vì nó redirect chứ không trả JSON — chỉ có mã đi qua URL.
 * Tập mã cố ý HẸP và trùng với `ErrorCode` sẵn có: thêm mã mới bắt phải sửa
 * `test_error_code_mapping.py` lẫn `types.ts`, mà bên đó thì không có gì đỏ khi backend đẻ
 * ra mã lạ.
 */
const THONG_DIEP: Record<string, ApiError> = {
  UNAUTHORIZED: {
    code: 'UNAUTHORIZED',
    message: 'Đăng nhập không thành công.',
    retryable: true,
  },
  FORBIDDEN: {
    code: 'FORBIDDEN',
    message: 'Tài khoản này chưa được cấp quyền dùng hệ thống.',
    retryable: false,
  },
  AUTH_UNAVAILABLE: {
    code: 'AUTH_UNAVAILABLE',
    message: 'Google đang không phản hồi.',
    retryable: true,
  },
};

/**
 * Đọc `?authError=` rồi **xoá nó khỏi URL**.
 *
 * Xoá là bắt buộc chứ không phải cho đẹp: không xoá thì người dùng bấm F5 sau khi đăng nhập
 * lỗi sẽ thấy lại đúng thông báo đó, kể cả khi lần này họ đã vào được. Và mã lỗi nằm lại
 * trong lịch sử trình duyệt lẫn thanh địa chỉ suốt phiên.
 *
 * Mã lạ (URL bị sửa tay) trả `null` chứ không hiện gì — không dựng thông điệp từ chuỗi do
 * người ngoài đưa vào.
 */
export function readAuthError(location: Location, history: History): ApiError | null {
  const params = new URLSearchParams(location.search);
  const ma = params.get('authError');
  if (ma === null) return null;

  params.delete('authError');
  const con_lai = params.toString();
  history.replaceState({}, '', `${location.pathname}${con_lai ? `?${con_lai}` : ''}`);

  return THONG_DIEP[ma] ?? null;
}
