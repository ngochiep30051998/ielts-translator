export const BUBBLE_CSS = `
:host { all: initial; }

.bubble {
  position: fixed;
  z-index: 2147483647;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 340px;
  padding: 7px 8px 7px 12px;
  border: 1px solid rgba(20, 22, 26, 0.12);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px) saturate(1.6);
  -webkit-backdrop-filter: blur(14px) saturate(1.6);
  box-shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 10px 28px -8px rgba(16, 24, 40, .22);
  color: #14161a;
  font: 13.5px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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

@media (prefers-color-scheme: dark) {
  .bubble {
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(28, 31, 38, 0.92);
    box-shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 12px 32px -8px rgba(0, 0, 0, .55);
    color: #e9ecf1;
  }
  .sep { background: rgba(255, 255, 255, 0.14); }
  button { color: #a3abb9; }
  button:hover { background: rgba(255, 255, 255, 0.09); color: #e9ecf1; }
  button[data-action="save"] { color: #b3aefb; }
  button[data-action="retry"] { color: #ff9c92; }
  .bubble.icon-only button { color: #b3aefb; }
  .dots i { background: #79818f; }
  .loading .text { color: #a3abb9; }
  .bubble.error { border-color: rgba(255, 156, 146, .3); background: rgba(58, 31, 28, .95); }
  .bubble.error .text { color: #ff9c92; }
  .bubble.saved .text { color: #6ee7a8; }
}
`;
