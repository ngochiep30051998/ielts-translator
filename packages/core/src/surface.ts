/**
 * Những gì surface đang chạy LÀM ĐƯỢC mà surface kia không.
 *
 * Khác `ports.ts`: ở đó là những thứ core cần người khác làm hộ. Ở đây là những thứ core
 * chỉ cần *biết* để nói đúng — chủ yếu là chữ nghĩa hướng dẫn.
 *
 * Vì sao cần: 5 tab dùng chung cho cả hai surface, nhưng câu "Bôi đen text trên trang" thì
 * vô nghĩa trên web — ở đó không có trang nào của người khác để bôi đen, và cũng không có
 * bubble nào. Chỉ dẫn sai còn tệ hơn không có chỉ dẫn: nó bảo người dùng làm một việc bất
 * khả thi rồi để họ tự nghi ngờ mình.
 *
 * Chỉ khai những khả năng ĐANG được dùng để phân nhánh. Danh sách này không phải chỗ mô tả
 * mọi khác biệt giữa hai surface.
 */
export interface SurfaceCapabilities {
  /**
   * Bôi đen text trên trang web bất kỳ rồi dịch ngay tại chỗ.
   *
   * Chỉ extension có — nó cắm được content script vào trang của người khác. Web không thể,
   * và đó là giới hạn của nền tảng chứ không phải tính năng còn thiếu.
   */
  selectionCapture: boolean;
}

/** Mặc định là surface hạn chế hơn: nói thiếu tính năng còn hơn hứa một thứ không có. */
const MAC_DINH: SurfaceCapabilities = { selectionCapture: false };

let current: SurfaceCapabilities = MAC_DINH;

/** Gọi MỘT lần lúc khởi động, cùng chỗ với `setTransport`. */
export function setSurfaceCapabilities(next: SurfaceCapabilities): void {
  current = next;
}

export function surfaceCapabilities(): SurfaceCapabilities {
  return current;
}

/** Chỉ dùng trong test: trả về mặc định để test này không rò sang test kia. */
export function resetSurfaceCapabilities(): void {
  current = MAC_DINH;
}
