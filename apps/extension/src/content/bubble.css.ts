/**
 * CSS của bubble, dạng chuỗi để nhét vào Shadow DOM (ràng buộc #11).
 *
 * Màu và font phải VIẾT RA Ở ĐÂY chứ không dùng token của `packages/core/src/ui/styles.css`:
 * bubble sống trong shadow root trên trang của người khác, nơi file đó không hề được nạp.
 * Giá trị lấy từ cùng một bảng màu 1a nên hai bên vẫn khớp — sửa bảng màu thì sửa cả hai.
 *
 * (Không dùng dấu nháy ngược trong file này — cả CSS nằm trong một template literal, một
 * dấu lạc chỗ là đứt chuỗi.)
 */
export const BUBBLE_CSS = `
:host { all: initial; }

.bubble {
  /* Token cục bộ của shadow root. Chế độ tối chỉ cần định nghĩa lại đúng khối này thay vì
     lặp lại một quy tắc :host([data-theme="dark"]) cho từng phần tử. */
  --text: #1a2224;
  --text-2: #3d4a4c;
  --text-3: #5a6a6d;
  --card: #ffffff;
  --line: rgba(26, 34, 36, 0.1);
  --edge: rgba(15, 122, 85, 0.22);
  --accent: #0f7a55;
  --accent-soft: #e6f4ee;
  --accent-text: #0b5c40;
  --on-accent: #ffffff;
  --danger: #b02318;
  --danger-soft: rgba(253, 240, 239, 0.95);
  --danger-edge: rgba(176, 35, 24, 0.35);
  --ok: #0f7a55;
  --shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 12px 26px -10px rgba(16, 24, 40, .24);

  --font-ui: 'Instrument Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-display: 'Space Grotesk', 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-serif: Lora, Georgia, 'Times New Roman', serif;

  position: fixed;
  z-index: 2147483647;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 360px;
  padding: 7px 8px 7px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
  box-shadow: var(--shadow);
  color: var(--text);
  font: 13.5px/1.45 var(--font-ui);
  -webkit-font-smoothing: antialiased;
}

.text {
  flex: 1;
  min-width: 0;
  padding-right: 5px;
  word-break: break-word;
}

.sep {
  width: 1px;
  height: 17px;
  margin: 0 3px;
  background: var(--line);
  flex-shrink: 0;
}

button {
  all: unset;
  box-sizing: border-box;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border-radius: 7px;
  color: var(--text-3);
  cursor: pointer;
}
button:hover { background: rgba(26, 34, 36, 0.06); color: var(--text); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: -1px; }
button[data-action="retry"] { width: auto; padding: 0 9px; font-size: 12.5px; color: var(--danger); }

svg { display: block; pointer-events: none; }

/* ---------- Trạng thái kết quả (thiết kế 1a) ----------
   Khối chữ bên trái, cụm nút bên phải, ngăn nhau bằng một đường kẻ dọc chạy HẾT chiều cao.
   Muốn kẻ hết chiều cao thì bubble phải bỏ padding của chính nó (padding chuyển vào từng
   khối con) và các con phải kéo dài bằng nhau — đó là lý do có align-items: stretch. */
.bubble.result {
  align-items: stretch;
  gap: 0;
  padding: 0;
  border-color: var(--edge);
  overflow: hidden;
}
.bubble.result .body { padding: 9px 12px; min-width: 0; }
.bubble.result .head { display: flex; align-items: baseline; gap: 7px; }
.bubble.result .term {
  font-family: var(--font-display);
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
  word-break: break-word;
}
.bubble.result .band {
  flex-shrink: 0;
  padding: 1.5px 5px;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--accent-text);
  font-family: var(--font-display);
  font-size: 9.5px;
  font-weight: 500;
  letter-spacing: .02em;
  cursor: help;
}
/* Dòng nội dung dưới dòng từ — bố cục dùng chung cho cả hai ngôn ngữ.
   display:block là bắt buộc: .text vốn là một thẻ span, mà margin-top trên phần tử inline
   không có tác dụng nào — thiếu dòng này thì nghĩa dính sát vào dòng từ ở trên. */
.bubble.result .meaning {
  display: block;
  flex: none;
  margin-top: 1px;
  padding-right: 0;
  font-size: 13px;
  line-height: 1.4;
  color: var(--text-2);
}
/* Serif (Lora) là mặt chữ thiết kế 1a dành RIÊNG cho tiếng Việt, đúng như phần nghĩa ở side
   panel. VI→EN chế độ CÂU trả về một câu tiếng Anh nên không mang class này. */
.bubble.result .meaning.vi { font-family: var(--font-serif); }
.bubble.result .tools {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  padding: 0 6px;
  border-left: 1px solid var(--line);
}
.bubble.result .tools button { width: 28px; height: 28px; }
/* "Thêm vào sổ" là hành động chính của bubble — nền đặc để nó không phải là một trong ba
   icon xám giống nhau. */
.bubble.result button[data-action="save"] { background: var(--accent); color: var(--on-accent); }
.bubble.result button[data-action="save"]:hover { background: var(--accent-text); color: var(--on-accent); }

/* trạng thái đầu: chỉ một icon, bám sát nội dung nên bỏ padding chữ */
.bubble.icon-only { padding: 4px; gap: 0; }
.bubble.icon-only button { width: 30px; height: 30px; color: var(--accent); }
/* To hơn 15px mặc định: đây là nút DUY NHẤT trên màn hình và là thứ người dùng phải
   nhận ra rồi bấm trúng, không phải một nút phụ nằm cạnh dòng chữ. */
.bubble.icon-only svg { width: 18px; height: 18px; }

/* trạng thái đang tải */
.dots { display: inline-flex; gap: 3.5px; align-items: center; padding: 3px 2px; }
.dots i {
  width: 5px; height: 5px; border-radius: 50%;
  background: #879497;
  animation: ielts-blink 1.15s infinite ease-in-out;
}
.dots i:nth-child(2) { animation-delay: .17s; }
.dots i:nth-child(3) { animation-delay: .34s; }
@keyframes ielts-blink {
  0%, 80%, 100% { opacity: .28; transform: translateY(0); }
  40%           { opacity: 1;   transform: translateY(-2.5px); }
}
.loading .text { color: var(--text-2); }

/* trạng thái lỗi */
.bubble.error {
  border-color: var(--danger-edge);
  background: var(--danger-soft);
}
.bubble.error .text { color: var(--danger); }

/* trạng thái vừa lưu */
.bubble.saved .text { color: var(--ok); }

/* Chế độ tối. Bám vào data-theme trên host chứ không hỏi prefers-color-scheme: người dùng
   chọn được Sáng/Tối/Theo hệ thống trong Options, và content/index.ts phân giải lựa chọn
   đó rồi đặt lên host. Gần như mọi quy tắc ở trên đã dùng token nên chỉ cần định nghĩa
   lại token ở đây.

   NGOẠI LỆ: đúng hai quy tắc bên dưới khối token ("button:hover" và ".dots i") phải giữ
   đồng bộ BẰNG TAY với bản sáng, vì chúng không suy được từ token — hover ở bản sáng tối
   đi, ở bản tối phải sáng lên, tức hai hướng ngược nhau chứ không phải một màu đổi giá
   trị. Đổi màu hover ở bản sáng mà quên hai dòng đó là hai chế độ lệch nhau âm thầm. */
:host([data-theme="dark"]) .bubble {
  --text: #e6eded;
  --text-2: #a8b6b7;
  --text-3: #a8b6b7;
  --card: #161f20;
  --line: rgba(255, 255, 255, 0.12);
  --edge: rgba(63, 188, 141, 0.3);
  --accent: #3fbc8d;
  --accent-soft: #10312a;
  --accent-text: #7fd9b4;
  --on-accent: #06231a;
  --danger: #ff9c92;
  --danger-soft: rgba(53, 29, 27, 0.95);
  --danger-edge: rgba(255, 156, 146, 0.3);
  --ok: #3fbc8d;
  --shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 12px 32px -8px rgba(0, 0, 0, .55);
}
:host([data-theme="dark"]) button:hover { background: rgba(255, 255, 255, 0.09); }
:host([data-theme="dark"]) .dots i { background: #7d8c8e; }
/* Nền đặc ở chế độ tối: hover sáng LÊN, không tối đi như bản sáng. */
:host([data-theme="dark"]) .bubble.result button[data-action="save"]:hover {
  background: var(--accent-text);
}
`;
