/**
 * Icon của bottom nav — mỗi tab MỘT hình riêng.
 *
 * Trước đây cả năm mục dùng chung một ô vuông bo góc, nên từ xa nav chỉ là năm khối giống
 * hệt nhau và mắt buộc phải đọc chữ 10px mới biết mình đang ở đâu. Icon riêng cho phép nhận
 * ra mục bằng hình dáng — thứ đọc được nhanh hơn chữ nhiều lần ở cỡ đó.
 *
 * Năm hình cố ý khác nhau về SILHOUETTE chứ không chỉ khác chi tiết bên trong: mũi tên
 * ngang (Dịch) — khung vuông có tai (Hôm nay) — sách mở (Sổ từ) — vòng tròn (Ôn tập) —
 * ba dòng có chấm (Quiz). Ở 20px chi tiết bên trong biến mất, chỉ còn dáng ngoài.
 *
 * Vẽ bằng SVG inline, KHÔNG thêm thư viện icon: năm hình không đáng một dependency, và
 * `currentColor` cho phép icon tự đổi màu theo `color` của nút — trạng thái active đã đổi
 * `color` sang `--accent` rồi, icon ăn theo mà không cần thêm một quy tắc CSS nào.
 */

export type TabIconName = 'translate' | 'home' | 'vocab' | 'review' | 'quiz';

/** Nét vẽ dùng chung — giữ năm hình cùng một "bộ chữ" thay vì năm phong cách rời rạc. */
const STROKE = {
  className: 'tab-icon',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  // Icon KHÔNG mang thông tin: nhãn chữ nằm ngay dưới nó và đó mới là tên tab mà trình đọc
  // màn hình đọc lên. Đọc thêm một hình trang trí chỉ làm tên tab dài ra vô ích.
  'aria-hidden': true,
} as const;

/**
 * `data-icon` là móc để test chứng minh năm tab thật sự có năm hình khác nhau.
 * Không có nó thì "mỗi tab một icon" là thứ chỉ mắt người kiểm được.
 */
export function TabIcon({ name }: { name: TabIconName }) {
  switch (name) {
    // Dịch — hai mũi tên ngược chiều: đổi một đoạn text sang ngôn ngữ kia.
    case 'translate':
      return (
        <svg {...STROKE} data-icon="translate">
          <path d="M3.5 8.5h13" />
          <path d="m13 5 3.5 3.5L13 12" />
          <path d="M20.5 15.5h-13" />
          <path d="M11 12 7.5 15.5 11 19" />
        </svg>
      );
    // Hôm nay — tờ lịch có dấu tích: hôm nay đã học hay chưa.
    case 'home':
      return (
        <svg {...STROKE} data-icon="home">
          <rect x="3.5" y="5" width="17" height="15" rx="3.5" />
          <path d="M8 3v4M16 3v4M3.5 10h17" />
          <path d="m8.75 14.75 2.25 2.25 4.25-4.5" />
        </svg>
      );
    // Sổ từ — sách mở. Dáng hai trang có rãnh giữa, không lẫn với khung vuông của tờ lịch.
    case 'vocab':
      return (
        <svg {...STROKE} data-icon="vocab">
          <path d="M12 7.5C10.2 6.1 7.9 5.5 5.2 5.7A1.2 1.2 0 0 0 4 6.9v9.9c0 .7.6 1.2 1.3 1.2 2.5-.1 4.7.4 6.7 1.8 2-1.4 4.2-1.9 6.7-1.8a1.2 1.2 0 0 0 1.3-1.2V6.9a1.2 1.2 0 0 0-1.2-1.2c-2.7-.2-5 .4-6.8 1.8Z" />
          <path d="M12 7.5v12.3" />
        </svg>
      );
    // Ôn tập — mũi tên xoay một vòng: lặp lại thứ đã học.
    case 'review':
      return (
        <svg {...STROKE} data-icon="review">
          <path d="M20.5 12a8.5 8.5 0 1 1-2.49-6.01" />
          <path d="M20.5 4v5h-5" />
        </svg>
      );
    // Quiz — ba dòng đáp án, dòng đầu được chọn. Đúng hình dạng của câu trắc nghiệm.
    case 'quiz':
      return (
        <svg {...STROKE} data-icon="quiz">
          <circle cx="5.75" cy="6.75" r="2.25" fill="currentColor" stroke="none" />
          <circle cx="5.75" cy="12" r="2.25" />
          <circle cx="5.75" cy="17.25" r="2.25" />
          <path d="M11 6.75h9.25M11 12h9.25M11 17.25h9.25" />
        </svg>
      );
  }
}
