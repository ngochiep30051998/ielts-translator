/*
 * Service worker viết tay.
 *
 * KHÔNG dùng Workbox: nó là một dependency mới, và ràng buộc #12 đòi nêu lý do trước. Thứ
 * cần ở đây gọn hơn nhiều so với thứ Workbox giải quyết.
 *
 * KHÔNG có precache list sinh lúc build, cũng vì lý do đó: sinh danh sách asset có hash cần
 * một plugin Vite. Thay vào đó cache dần theo lượt dùng — lần mở đầu tiên cần mạng, từ lần
 * thứ hai trở đi mở được offline. Đánh đổi này chấp nhận được cho phạm vi "offline CHỈ ĐỌC".
 *
 * File nằm ở `public/` nên Vite chép nguyên xi, không transpile. Viết JS thuần, không import.
 */

// Bump khi đổi chiến lược cache. `activate` xoá mọi cache mang version khác.
const VERSION = 'v1';
const CACHE_SHELL = `ielts-shell-${VERSION}`;
const CACHE_API = `ielts-api-${VERSION}`;

/** Endpoint đọc-thuần, an toàn để phục vụ từ cache trong lúc gọi lại nền. */
const API_DOC_DUOC = [/^\/api\/vocab(\?|$)/, /^\/api\/stats(\?|$)/];

self.addEventListener('install', (event) => {
  // Chỉ nạp sẵn vỏ tối thiểu. Asset có hash sẽ vào cache khi được yêu cầu lần đầu.
  event.waitUntil(
    caches.open(CACHE_SHELL).then((cache) => cache.addAll(['/', '/manifest.webmanifest'])),
  );
  // Không đợi tab cũ đóng: người dùng vừa cài xong app thì mong nó chạy ngay.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((ten) =>
        Promise.all(
          ten
            .filter((t) => t.startsWith('ielts-') && !t.endsWith(VERSION))
            .map((t) => caches.delete(t)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/**
 * Xoá cache API khi đăng xuất.
 *
 * BẮT BUỘC, không phải dọn dẹp cho gọn: cache dùng chung theo ORIGIN, không theo người dùng.
 * Bỏ bước này thì trên máy dùng chung, người đăng nhập sau mở app sẽ thấy sổ từ của người
 * trước hiện ra từ cache trước khi request thật kịp trả về.
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'XOA_CACHE_API') {
    event.waitUntil(caches.delete(CACHE_API));
  }
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  // Chỉ can thiệp vào chính origin của mình. Request sang nơi khác đi thẳng.
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) {
    if (API_DOC_DUOC.some((re) => re.test(url.pathname + url.search))) {
      event.respondWith(cuCungLucLamMoi(request));
    }
    // Mọi /api/* còn lại KHÔNG đụng tới: dịch, ôn, quiz đều đổi trạng thái hoặc tốn quota
    // Gemini. Phục vụ chúng từ cache là nói dối người dùng.
    return;
  }

  // Điều hướng trang: ưu tiên mạng để luôn lấy được bản mới, mất mạng thì trả vỏ đã cache.
  if (request.mode === 'navigate') {
    event.respondWith(mangTruocVoSau(request));
    return;
  }

  // Asset có hash trong tên -> nội dung không bao giờ đổi -> cache trước, khỏi hỏi lại.
  event.respondWith(cacheTruoc(request));
});

async function cacheTruoc(request) {
  const daCo = await caches.match(request);
  if (daCo) return daCo;

  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_SHELL);
    cache.put(request, response.clone());
  }
  return response;
}

async function mangTruocVoSau(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_SHELL);
      // Cache dưới khoá '/' chứ không phải URL gốc: mọi đường dẫn của SPA đều trả cùng một
      // `index.html`, nên lưu riêng từng đường dẫn là nhân bản cùng một file.
      cache.put('/', response.clone());
    }
    return response;
  } catch (loi) {
    const vo = await caches.match('/');
    if (vo) return vo;
    throw loi;
  }
}

/**
 * Trả bản cache ngay (nếu có) rồi gọi mạng nền để cập nhật cho lần sau.
 *
 * Người dùng thấy sổ từ ngay lập tức, kể cả khi mạng chậm hoặc mất hẳn. Dữ liệu có thể cũ
 * một nhịp — chấp nhận được vì đây là màn CHỈ ĐỌC, và lượt ghi (lưu từ, chấm thẻ) không đi
 * qua đường này.
 */
async function cuCungLucLamMoi(request) {
  const cache = await caches.open(CACHE_API);
  const daCo = await cache.match(request);

  const dangGoi = fetch(request)
    .then((response) => {
      // CHỈ cache 200. Cache một 401 là khoá người dùng ở màn đăng nhập cho tới khi cache
      // hết hạn, kể cả sau khi họ đã đăng nhập lại thành công.
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);

  if (daCo) {
    // Không `await` lượt gọi nền: trả cache ngay là toàn bộ điểm của chiến lược này.
    return daCo;
  }

  const tuoi = await dangGoi;
  if (tuoi) return tuoi;
  return new Response(
    JSON.stringify({
      code: 'BACKEND_DOWN',
      message: 'Không có mạng và chưa có dữ liệu đã tải về.',
      retryable: true,
    }),
    { status: 503, headers: { 'Content-Type': 'application/json' } },
  );
}
