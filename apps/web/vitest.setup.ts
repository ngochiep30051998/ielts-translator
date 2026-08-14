import '@testing-library/jest-dom/vitest';

/**
 * Vá `localStorage` cho môi trường test.
 *
 * Node 25 có Web Storage **dựng sẵn trong runtime**, và nó CHE MẤT bản của jsdom:
 * `globalThis.localStorage === window.localStorage`, `constructor.name` là `undefined`, và
 * `clear()` không tồn tại. (`sessionStorage` thì không dính — nó vẫn là `Storage` thật của
 * jsdom, nên đừng đụng vào.) Kèm theo là dòng cảnh báo
 * `--localstorage-file was provided without a valid path` mỗi lần chạy test.
 *
 * Chỉ là chuyện của test: trong trình duyệt thật `window.localStorage` là hàng thật. Nhưng
 * không vá thì mọi test chạm cài đặt đỏ với `clear is not a function` — một thông điệp
 * chẳng liên quan gì tới thứ đang được kiểm.
 *
 * Vá CÓ ĐIỀU KIỆN: máy nào có `localStorage` tử tế (Node cũ hơn, hoặc jsdom thắng) thì dùng
 * hàng thật. Thay vô điều kiện là tự bịt mắt trước hành vi thật của nền tảng.
 */
function bonaFide(kho: unknown): boolean {
  return (
    typeof kho === 'object' &&
    kho !== null &&
    typeof (kho as Storage).clear === 'function' &&
    typeof (kho as Storage).key === 'function'
  );
}

if (!bonaFide(globalThis.localStorage)) {
  const map = new Map<string, string>();
  const shim: Storage = {
    get length() {
      return map.size;
    },
    key: (i: number) => [...map.keys()][i] ?? null,
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, String(v)),
    removeItem: (k: string) => void map.delete(k),
    clear: () => map.clear(),
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: shim,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(window, 'localStorage', {
    value: shim,
    configurable: true,
    writable: true,
  });
}
