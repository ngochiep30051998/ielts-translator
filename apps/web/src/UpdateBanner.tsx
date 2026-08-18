import { useEffect, useState } from 'react';

import { updateSignal } from './sw-update';

/**
 * Dải báo "đã có bản mới" ở đáy màn hình web.
 *
 * KHÔNG tự tải lại trang. Bản nháp đang gõ ở tab Dịch và câu quiz đang làm dở chỉ nằm trong
 * bộ nhớ, nên một lượt reload tự động là xoá đúng thứ người dùng đang làm — và họ sẽ không
 * hiểu vì sao. Người dùng bấm thì mới tải lại.
 *
 * Chỉ có ở web: extension không có chuyện này, Chrome tự cập nhật rồi khởi động lại nó.
 */
export function UpdateBanner({
  subscribe = updateSignal.subscribe,
  apply = updateSignal.apply,
}: {
  /** Tách ra prop để test tự quyết định lúc nào "có bản mới", không phải dựng cả service worker. */
  subscribe?: (cb: () => void) => () => void;
  apply?: () => void;
} = {}) {
  const [hien, setHien] = useState(false);

  useEffect(() => subscribe(() => setHien(true)), [subscribe]);

  if (!hien) return null;

  return (
    // `role="status"` chứ không phải một `div` câm: banner tự hiện ra chứ không do người
    // dùng bấm gì, nên trình đọc màn hình phải được báo — nhưng lịch sự (`polite`), đừng
    // cắt ngang câu đang đọc dở.
    <div className="update-banner" role="status">
      <span className="update-banner-text">Đã có bản mới của app.</span>
      <button type="button" className="update-banner-later" onClick={() => setHien(false)}>
        Để sau
      </button>
      <button type="button" className="update-banner-apply" onClick={() => apply()}>
        Tải lại
      </button>
    </div>
  );
}
