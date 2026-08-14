import type { LastResultStore, TranslateResult } from '@ielts/core';

const KEY = 'lastResult';

/**
 * `sessionStorage` chứ không phải biến trong bộ nhớ.
 *
 * Extension giữ kết quả dịch gần nhất trong service worker, tách rời khỏi side panel — panel
 * đóng mở bao nhiêu lần cũng không mất. Web thì không có ai đứng ngoài trang: F5 là mất
 * sạch, mà F5 lại là thao tác người ta làm liên tục trên điện thoại.
 *
 * `sessionStorage` chứ không `localStorage`: kết quả dịch gắn với một lượt dùng, và trên máy
 * dùng chung thì nó không nên sống qua lần đóng tab. Cùng lý do với việc `App` xoá sạch
 * state khi đăng xuất.
 */
export const sessionLastResult: LastResultStore = {
  async get() {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      return raw ? (JSON.parse(raw) as TranslateResult) : null;
    } catch {
      return null;
    }
  },

  async set(result) {
    try {
      if (result === null) {
        window.sessionStorage.removeItem(KEY);
      } else {
        window.sessionStorage.setItem(KEY, JSON.stringify(result));
      }
    } catch {
      // Hết hạn mức lưu trữ, hoặc storage bị chặn. Mất tiện lợi, không mất chức năng.
    }
  },
};
