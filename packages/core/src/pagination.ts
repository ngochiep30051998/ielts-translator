/** Dãy số trang rút gọn cho thanh phân trang.
 *
 * Side panel chỉ rộng khoảng 360px, nên dãy số KHÔNG được phép dài theo số trang: sổ 200
 * trang mà vẽ 200 ô thì thanh phân trang vỡ dòng và đẩy danh sách từ xuống dưới màn hình.
 * Ở đây dãy luôn gói trong `MAX_PAGE_SLOTS` ô, phần bị cắt thay bằng dấu `…`.
 */

/** Ô trong dãy: một chỉ số trang, hoặc chỗ ngắt `…` (không bấm được). */
export type PageSlot = number | 'gap';

/** Sức chứa của dãy. Số LẺ để trang hiện tại nằm đúng giữa khi ở quãng giữa sổ từ.
 *  7 ô cộng hai nút mũi tên là 320px — vừa side panel ở bề rộng thường dùng (~400px);
 *  hẹp hơn thì `.vocab-pager` cho xuống dòng chứ dãy không tự co lại. */
export const MAX_PAGE_SLOTS = 7;

/** Số ô hai đầu dãy bị dấu `…` và trang đầu/cuối chiếm mất, khi cắt ở cả hai bên. */
const EDGE_SLOTS = 2;

/**
 * @param current chỉ số trang đang xem, TÍNH TỪ 0 — cùng hệ với `cursor.page` và với field
 *   `number` mà backend trả về. Chỉ đổi sang cách đếm từ 1 lúc hiển thị.
 * @param totalPages tổng số trang.
 */
export function pageSlots(current: number, totalPages: number): PageSlot[] {
  if (totalPages <= 0) return [];

  const last = totalPages - 1;
  const all = (from: number, to: number): number[] =>
    Array.from({ length: to - from + 1 }, (_, i) => from + i);

  if (totalPages <= MAX_PAGE_SLOTS) return all(0, last);

  // Gần đầu: chưa cần dấu … bên trái, nên bên phải được dùng trọn phần còn lại.
  const window = MAX_PAGE_SLOTS - EDGE_SLOTS;
  if (current <= window - 2) return [...all(0, window - 1), 'gap', last];

  // Gần cuối: đối xứng với nhánh trên.
  if (current >= last - (window - 2)) return [0, 'gap', ...all(last - (window - 1), last)];

  // Quãng giữa: dấu … cả hai bên, trang hiện tại kèm đúng một trang mỗi bên.
  return [0, 'gap', current - 1, current, current + 1, 'gap', last];
}
