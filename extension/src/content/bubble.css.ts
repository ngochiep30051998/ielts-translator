export const BUBBLE_CSS = `
:host { all: initial; }
.bubble {
  position: fixed;
  z-index: 2147483647;
  max-width: 320px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #1f2430;
  color: #f2f4f8;
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.bubble.error { background: #4a2020; }
.text { flex: 1; word-break: break-word; }
button {
  all: unset;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 13px;
  line-height: 1.4;
}
button:hover { background: rgba(255, 255, 255, 0.14); }
button:focus-visible { outline: 2px solid #7aa7ff; }
`;
