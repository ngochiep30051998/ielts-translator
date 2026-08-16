<<<<<<< Updated upstream
=======
/**
 * CSS của bubble, dạng chuỗi để nhét vào Shadow DOM (ràng buộc #11).
 *
 * Màu và font phải VIẾT RA Ở ĐÂY chứ không dùng token của `packages/core/src/ui/styles.css`:
 * bubble sống trong shadow root trên trang của người khác, nơi file đó không hề được nạp.
 * Giá trị lấy từ cùng một bảng màu 1b nên hai bên vẫn khớp — sửa bảng màu thì sửa cả hai.
 *
 * (Không dùng dấu nháy ngược trong file này — cả CSS nằm trong một template literal, một
 * dấu lạc chỗ là đứt chuỗi.)
 */
>>>>>>> Stashed changes
export const BUBBLE_CSS = `
:host { all: initial; }

.bubble {
<<<<<<< Updated upstream
=======
  /* Token cục bộ của shadow root. Chế độ tối chỉ cần định nghĩa lại đúng khối này thay vì
     lặp lại một quy tắc :host([data-theme="dark"]) cho từng phần tử. */
  --text: #12191b;
  --text-2: #39454a;
  --text-3: #879497;
  --card: #ffffff;
  --line: rgba(18, 25, 27, 0.09);
  --edge: rgba(15, 158, 108, 0.22);
  --accent: #0f9e6c;
  --accent-soft: #e3f7ef;
  --accent-text: #0a7a52;
  --on-accent: #ffffff;
  --danger: #b02318;
  --danger-soft: rgba(253, 240, 239, 0.95);
  --danger-edge: rgba(176, 35, 24, 0.35);
  --ok: #0f9e6c;
  --shadow: 0 2px 4px rgba(16, 24, 40, .06), 0 18px 34px -14px rgba(16, 24, 40, .28);

  --font-ui: 'Instrument Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-display: 'Space Grotesk', 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-serif: Lora, Georgia, 'Times New Roman', serif;

>>>>>>> Stashed changes
  position: fixed;
  z-index: 2147483647;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 340px;
  padding: 7px 8px 7px 12px;
<<<<<<< Updated upstream
  border: 1px solid rgba(20, 22, 26, 0.12);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px) saturate(1.6);
  -webkit-backdrop-filter: blur(14px) saturate(1.6);
  box-shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 10px 28px -8px rgba(16, 24, 40, .22);
  color: #14161a;
  font: 13.5px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
=======
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--card);
  box-shadow: var(--shadow);
  color: var(--text);
  font: 13.5px/1.45 var(--font-ui);
>>>>>>> Stashed changes
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
  background: rgba(20, 22, 26, 0.12);
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
  color: #5b6270;
  cursor: pointer;
}
button:hover { background: rgba(20, 22, 26, 0.06); color: #14161a; }
button:focus-visible { outline: 2px solid #4f46e5; outline-offset: -1px; }
button[data-action="save"] { color: #4338ca; }
button[data-action="retry"] { width: auto; padding: 0 9px; font-size: 12.5px; color: #b42318; }

svg { display: block; pointer-events: none; }

<<<<<<< Updated upstream
=======
/* ---------- Trạng thái kết quả (thiết kế 1b) ----------
   Khối chữ ở TRÊN, thanh hành động nền xanh đặc ở DƯỚI, card không viền chỉ có bóng nổi.
   Bubble phải bỏ padding của chính nó (padding chuyển vào từng khối con) thì thanh dưới
   mới chạy hết bề ngang được, và overflow:hidden cắt góc thanh theo bo của card.
   (Không dấu nháy ngược trong file này — cả CSS nằm trong một template literal.) */
.bubble.result {
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  padding: 0;
  border: 0;
  overflow: hidden;
}
.bubble.result .body { padding: 13px 14px 12px; min-width: 0; }
.bubble.result .head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.bubble.result .term {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -.01em;
  color: var(--text);
  word-break: break-word;
}
.bubble.result .band {
  flex-shrink: 0;
  padding: 3px 7px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent-text);
  font-family: var(--font-display);
  font-size: 10.5px;
  font-weight: 600;
  cursor: help;
}
/* Dòng nội dung dưới dòng từ — bố cục dùng chung cho cả hai ngôn ngữ.
   display:block là bắt buộc: .text vốn là một thẻ span, mà margin-top trên phần tử inline
   không có tác dụng nào — thiếu dòng này thì nghĩa dính sát vào dòng từ ở trên. */
.bubble.result .meaning {
  display: block;
  flex: none;
  margin-top: 5px;
  padding-right: 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-2);
}
/* Serif (Lora) là mặt chữ dành RIÊNG cho tiếng Việt, đúng như phần nghĩa ở side panel.
   VI→EN chế độ CÂU trả về một câu tiếng Anh nên không mang class này. */
.bubble.result .meaning.vi { font-family: var(--font-serif); }

/* Thanh hành động: nền accent ĐẶC, chữ trắng. Đây là thứ 1b thay cho cụm ba icon xám. */
.bubble.result .bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  background: var(--accent);
}
.bubble.result .bar button[data-action="save"] {
  flex: 1;
  width: auto;
  height: auto;
  justify-content: flex-start;
  display: block;
  color: var(--on-accent);
  font-family: var(--font-ui);
  font-size: 12.5px;
  font-weight: 600;
  text-align: left;
}
.bubble.result .bar button[data-action="save"]:hover {
  background: transparent;
  text-decoration: underline;
}
/* Chip "+N từ hôm nay". Hình dáng dùng chung, còn màu thì tuỳ nền nó đứng lên: thanh
   accent đặc (bubble kết quả) hay card trắng (bubble báo đã lưu). */
.daily {
  flex-shrink: 0;
  padding: 2px 7px;
  border-radius: 5px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
}
.bubble.result .daily {
  background: rgba(255, 255, 255, .24);
  color: var(--on-accent);
}
/* Trên card trắng thì màu trắng mờ là tàng hình — chip ở đây mượn cặp màu của chip band. */
.bubble.saved .daily {
  margin-left: 8px;
  background: var(--accent-soft);
  color: var(--accent-text);
}
.bubble.result .bar button[data-action="speak"],
.bubble.result .bar button[data-action="expand"] {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: rgba(255, 255, 255, .2);
  color: var(--on-accent);
}
.bubble.result .bar button[data-action="speak"]:hover,
.bubble.result .bar button[data-action="expand"]:hover {
  background: rgba(255, 255, 255, .34);
  color: var(--on-accent);
}
.bubble.result .bar svg { width: 13px; height: 13px; }

>>>>>>> Stashed changes
/* trạng thái đầu: chỉ một icon, bám sát nội dung nên bỏ padding chữ */
.bubble.icon-only { padding: 4px; gap: 0; }
.bubble.icon-only button { width: 30px; height: 30px; color: #4338ca; }
/* To hơn 15px mặc định: đây là nút DUY NHẤT trên màn hình và là thứ người dùng phải
   nhận ra rồi bấm trúng, không phải một nút phụ nằm cạnh dòng chữ. */
.bubble.icon-only svg { width: 18px; height: 18px; }

/* trạng thái đang tải */
.dots { display: inline-flex; gap: 3.5px; align-items: center; padding: 3px 2px; }
.dots i {
  width: 5px; height: 5px; border-radius: 50%;
  background: #8b93a1;
  animation: ielts-blink 1.15s infinite ease-in-out;
}
.dots i:nth-child(2) { animation-delay: .17s; }
.dots i:nth-child(3) { animation-delay: .34s; }
@keyframes ielts-blink {
  0%, 80%, 100% { opacity: .28; transform: translateY(0); }
  40%           { opacity: 1;   transform: translateY(-2.5px); }
}
.loading .text { color: #5b6270; }

/* trạng thái lỗi */
.bubble.error {
  border-color: rgba(180, 35, 24, .35);
  background: rgba(254, 243, 242, .95);
}
.bubble.error .text { color: #b42318; }

/* trạng thái vừa lưu */
.bubble.saved .text { color: #067647; }

/* Chế độ tối. Bám vào data-theme trên host chứ không hỏi prefers-color-scheme: người dùng
   chọn được Sáng/Tối/Theo hệ thống trong Options, và content/index.ts phân giải lựa chọn
   đó rồi đặt lên host. (Không dùng dấu nháy ngược trong file này — cả CSS nằm trong một
   template literal, một dấu lạc chỗ là đứt chuỗi.) */
:host([data-theme="dark"]) .bubble {
<<<<<<< Updated upstream
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(28, 31, 38, 0.92);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 12px 32px -8px rgba(0, 0, 0, .55);
  color: #e9ecf1;
}
:host([data-theme="dark"]) .sep { background: rgba(255, 255, 255, 0.14); }
:host([data-theme="dark"]) button { color: #a3abb9; }
:host([data-theme="dark"]) button:hover { background: rgba(255, 255, 255, 0.09); color: #e9ecf1; }
:host([data-theme="dark"]) button[data-action="save"] { color: #b3aefb; }
:host([data-theme="dark"]) button[data-action="retry"] { color: #ff9c92; }
:host([data-theme="dark"]) .bubble.icon-only button { color: #b3aefb; }
:host([data-theme="dark"]) .dots i { background: #79818f; }
:host([data-theme="dark"]) .loading .text { color: #a3abb9; }
:host([data-theme="dark"]) .bubble.error { border-color: rgba(255, 156, 146, .3); background: rgba(58, 31, 28, .95); }
:host([data-theme="dark"]) .bubble.error .text { color: #ff9c92; }
:host([data-theme="dark"]) .bubble.saved .text { color: #6ee7a8; }
=======
  --text: #e8efef;
  --text-2: #aab8b9;
  --text-3: #7f8e90;
  --card: #161f20;
  --line: rgba(255, 255, 255, 0.09);
  --edge: rgba(47, 189, 135, 0.3);
  --accent: #2fbd87;
  --accent-soft: #0d2f24;
  --accent-text: #7fd9b4;
  --on-accent: #05231a;
  --danger: #ff9c92;
  --danger-soft: rgba(53, 29, 27, 0.95);
  --danger-edge: rgba(255, 156, 146, 0.3);
  --ok: #2fbd87;
  --shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 12px 32px -8px rgba(0, 0, 0, .55);
}
:host([data-theme="dark"]) button:hover { background: rgba(255, 255, 255, 0.09); }
:host([data-theme="dark"]) .dots i { background: #7f8e90; }
/* Trên thanh xanh đặc, "chồng thêm màu trắng mờ" đúng cho CẢ hai chế độ (nền tối thì
   accent sáng, nền sáng thì accent đậm) nên không cần quy tắc riêng ở đây. */
>>>>>>> Stashed changes
`;
