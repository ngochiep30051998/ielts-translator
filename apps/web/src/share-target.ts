/**
 * Nhận text chia sẻ từ app khác (Web Share Target).
 *
 * Đây là thứ thay thế gần nhất cho "bôi đen rồi dịch" của extension, và là lý do chính đáng
 * nhất để cài web app vào màn hình chính: bôi đen text trong Chrome / Kindle / Facebook trên
 * điện thoại → Share → IELTS Translator → vào thẳng tab Dịch với text đã điền sẵn.
 *
 * **Chỉ Android.** Safari bỏ qua `share_target` trong manifest một cách im lặng; trên iOS
 * vẫn cài được vào màn hình chính và vẫn dán tay được, chỉ không có mục trong menu Share.
 *
 * Manifest khai `method: "GET"` chứ không POST: POST share target BẮT BUỘC phải có service
 * worker chặn request, nên nó hỏng ở đúng lần dùng đầu tiên (lúc SW chưa active). Mình chỉ
 * cần text, và text đi qua query string được.
 */

/** Đường dẫn khai trong `share_target.action` của manifest. Đổi ở đây phải đổi cả bên đó. */
export const SHARE_PATH = '/share';

/**
 * Đọc text được chia sẻ rồi **dọn URL**.
 *
 * Dọn là bắt buộc: text người dùng chia sẻ nằm nguyên trong thanh địa chỉ và trong lịch sử
 * trình duyệt. Với một app dịch thuật, đó có thể là đoạn riêng tư họ vừa bôi đen ở đâu đó.
 *
 * Trả `null` khi không phải lượt chia sẻ — gồm cả khi vào thẳng `/share` mà không có tham số.
 */
export function readSharedText(location: Location, history: History): string | null {
  if (location.pathname !== SHARE_PATH) return null;

  const params = new URLSearchParams(location.search);
  // `text` trước, `title` sau: Android đưa đoạn bôi đen vào `text`, còn `title` thường là
  // tiêu đề trang — dịch tiêu đề khi người ta muốn dịch đoạn văn là sai việc.
  //
  // `url` cố ý KHÔNG dùng: dịch một địa chỉ web không ra nghĩa gì.
  const noi_dung = (params.get('text') ?? params.get('title') ?? '').trim();

  // replaceState chứ không pushState: bấm Back sau khi chia sẻ phải quay về app vừa chia sẻ,
  // không phải quay lại chính màn hình này với text cũ.
  history.replaceState({}, '', '/');

  return noi_dung || null;
}
