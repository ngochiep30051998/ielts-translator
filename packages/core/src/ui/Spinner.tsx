/**
 * Vòng quay chờ, dùng chung cho mọi nút đang bận.
 *
 * `aria-hidden` vì nó KHÔNG mang thông tin cho trình đọc màn hình: thông tin nằm ở nhãn nút
 * (đổi thành "Đang lưu…") và ở `aria-busy`. Đọc lên một hình trang trí chỉ làm nhiễu.
 *
 * Không nhận prop kích thước: nó lấy `1em` theo cỡ chữ của chỗ đặt, nên nút to nút nhỏ đều
 * cân mà không phải truyền số.
 */
export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}
