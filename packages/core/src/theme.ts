/** Chế độ màu của giao diện.
 *
 * Điểm mấu chốt của cả module: CSS **không** tự hỏi hệ điều hành nữa. JS phân giải
 * `'system'` ra `'light' | 'dark'` rồi gắn kết quả lên `<html data-theme="…">`, nên
 * `styles.css` chỉ cần MỘT khối token tối (`:root[data-theme="dark"]`) thay vì hai khối
 * song song — một cho media query, một cho lựa chọn thủ công — phải nhớ sửa cùng nhau.
 */

/** Lựa chọn của người dùng, đúng như lưu trong cài đặt. */
export type Theme = 'system' | 'light' | 'dark';

/** Chế độ thật sự đang hiển thị, sau khi đã hỏi hệ điều hành. */
export type ResolvedTheme = 'light' | 'dark';

const DARK_QUERY = '(prefers-color-scheme: dark)';

/** `matchMedia` vắng mặt trong jsdom và trong vài WebView cũ. Thiếu nó thì coi như sáng —
 *  đó cũng là bộ token mặc định của `:root`, nên giao diện vẫn đúng chứ không trắng trơn. */
function prefersDark(): boolean {
  return typeof matchMedia === 'function' && matchMedia(DARK_QUERY).matches;
}

export function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme === 'light' || theme === 'dark') return theme;
  return prefersDark() ? 'dark' : 'light';
}

/**
 * Gắn chế độ đã phân giải lên thẻ gốc và trả lại chính nó.
 *
 * `color-scheme` phải đặt cùng lúc: nó điều khiển những thứ CSS của ta không với tới được
 * — thanh cuộn, ô nhập gốc, bảng chọn ngày. Thiếu nó thì nền tối mà thanh cuộn vẫn trắng.
 */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement):
    ResolvedTheme {
  const resolved = resolveTheme(theme);
  root.dataset.theme = resolved;
  root.style.colorScheme = resolved;
  return resolved;
}

/**
 * Theo dõi hệ điều hành đổi chế độ màu. Trả về hàm huỷ đăng ký.
 *
 * Người dùng chọn "theo hệ thống" rồi để máy tự chuyển tối lúc chiều muộn — không nghe
 * sự kiện này thì side panel đang mở vẫn sáng cho tới lần mở lại sau.
 */
export function watchSystemTheme(onChange: (resolved: ResolvedTheme) => void): () => void {
  if (typeof matchMedia !== 'function') return () => {};
  const query = matchMedia(DARK_QUERY);
  const handler = (event: { matches: boolean }) => onChange(event.matches ? 'dark' : 'light');
  query.addEventListener('change', handler as (e: MediaQueryListEvent) => void);
  return () => query.removeEventListener('change', handler as (e: MediaQueryListEvent) => void);
}
