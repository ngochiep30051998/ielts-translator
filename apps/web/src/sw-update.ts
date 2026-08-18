/**
 * Phát hiện bản mới của web app và áp dụng nó.
 *
 * **Vì sao cần:** PWA cài vào màn hình chính gần như không bao giờ được đóng — người dùng
 * chỉ chuyển đi rồi chuyển lại. Trang đang mở giữ nguyên bundle JS của lần tải đầu tiên,
 * nên deploy một bản sửa lỗi xong họ vẫn gặp đúng lỗi đó cho tới khi tự tay tắt hẳn app.
 *
 * **Cách làm:** service worker mới KHÔNG tự giành quyền (không còn `skipWaiting()` lúc
 * install), nó nằm ở trạng thái `waiting` cho tới khi người dùng bấm "Tải lại". Đó là lý do
 * luồng này báo trước rồi mới hành động thay vì tự reload: người dùng có thể đang gõ dở một
 * đoạn cần dịch hoặc đang làm dở một câu quiz, và reload là mất sạch.
 */

/** 30 phút. Đủ để bắt được bản mới trong ngày, không đủ để thành phiền phức. */
const CHU_KY_MAC_DINH_MS = 30 * 60_000;
/** Khoảng cách tối thiểu giữa hai lần hỏi. Chuyển tab qua lại không được thành spam mạng. */
const KHOANG_CACH_TOI_THIEU_MS = 5 * 60_000;

/**
 * Theo dõi một đăng ký service worker, gọi `onReady` khi có bản mới sẵn sàng.
 *
 * `container` chỉ dùng để đọc `controller`: không có controller nghĩa là trang này chưa từng
 * do service worker nào điều khiển, tức đây là lần cài ĐẦU TIÊN chứ không phải bản mới.
 */
export function watchForUpdate(
  reg: ServiceWorkerRegistration,
  container: ServiceWorkerContainer,
  onReady: (worker: ServiceWorker) => void,
): void {
  // Bản mới tải xong từ phiên trước và đang nằm chờ. Sẽ KHÔNG có `updatefound` nào nữa cho
  // nó, nên không xét ở đây là mất hẳn ca này.
  if (reg.waiting) {
    onReady(reg.waiting);
    return;
  }

  reg.addEventListener('updatefound', () => {
    const moi = reg.installing;
    if (!moi) return;
    moi.addEventListener('statechange', () => {
      // `installed` là trạng thái "tải xong, đang chờ tới lượt". `redundant` là cài hỏng —
      // báo có bản mới rồi reload vào đúng bản cũ là làm người dùng mất công vô ích.
      if (moi.state !== 'installed') return;
      if (!container.controller) return;
      onReady(moi);
    });
  });
}

/**
 * Hỏi lại xem có bản mới không: theo chu kỳ, và mỗi lần người dùng quay lại tab.
 *
 * Trình duyệt chỉ tự hỏi khi có lượt điều hướng, mà một PWA dạng tab thì chẳng bao giờ điều
 * hướng. Trả về hàm dừng.
 */
export function startUpdateChecks(
  reg: ServiceWorkerRegistration,
  {
    intervalMs = CHU_KY_MAC_DINH_MS,
    minGapMs = KHOANG_CACH_TOI_THIEU_MS,
    doc = document,
    now = () => Date.now(),
  }: {
    intervalMs?: number;
    minGapMs?: number;
    doc?: Document;
    now?: () => number;
  } = {},
): () => void {
  let lanCuoi = now();

  function hoi() {
    lanCuoi = now();
    // Mất mạng là ca thường gặp nhất ở đây, và nó không phải lỗi: lần hỏi sau sẽ tới.
    void reg.update().catch(() => {});
  }

  const dinhKy = setInterval(hoi, intervalMs);

  function khiHienLai() {
    if (doc.visibilityState !== 'visible') return;
    if (now() - lanCuoi < minGapMs) return;
    hoi();
  }

  doc.addEventListener('visibilitychange', khiHienLai);

  return () => {
    clearInterval(dinhKy);
    doc.removeEventListener('visibilitychange', khiHienLai);
  };
}

/**
 * Áp dụng bản mới: bảo worker đang chờ nhường chỗ, rồi tải lại khi nó đã cầm lái.
 *
 * Phải đợi `controllerchange` chứ không reload ngay sau `postMessage`: reload sớm hơn một
 * nhịp thì trang mới vẫn do worker CŨ phục vụ, và người dùng bấm "Tải lại" xong vẫn thấy
 * banner hiện lại.
 */
export function applyUpdate(
  worker: ServiceWorker,
  container: ServiceWorkerContainer,
  reload: () => void = () => window.location.reload(),
): void {
  let daTai = false;
  container.addEventListener('controllerchange', () => {
    if (daTai) return;
    daTai = true;
    reload();
  });
  worker.postMessage({ type: 'SKIP_WAITING' });
}

/** Cầu nối giữa service worker (chạy sớm, ngoài React) và banner (component React). */
export interface UpdateSignal {
  /** Đăng ký nhận tin. Nếu bản mới ĐÃ sẵn sàng thì gọi lại ngay. Trả về hàm huỷ. */
  subscribe(cb: () => void): () => void;
  /** Bắt đầu theo dõi một đăng ký service worker. */
  watch(reg: ServiceWorkerRegistration, container: ServiceWorkerContainer): void;
  /** Áp dụng bản đang chờ. Không có gì chờ thì không làm gì. */
  apply(reload?: () => void): void;
}

export function createUpdateSignal(): UpdateSignal {
  let dangCho: ServiceWorker | null = null;
  let container: ServiceWorkerContainer | null = null;
  const nguoiNghe = new Set<() => void>();

  return {
    subscribe(cb) {
      nguoiNghe.add(cb);
      // Service worker được đăng ký trước khi React mount, nên banner luôn đến muộn hơn tin.
      // Không phát lại trạng thái đã có thì nó không bao giờ hiện.
      if (dangCho) cb();
      return () => {
        nguoiNghe.delete(cb);
      };
    },

    watch(reg, cont) {
      container = cont;
      watchForUpdate(reg, cont, (worker) => {
        dangCho = worker;
        nguoiNghe.forEach((cb) => cb());
      });
    },

    apply(reload) {
      if (!dangCho || !container) return;
      applyUpdate(dangCho, container, reload);
    },
  };
}

/** Bản dùng chung của cả app. `register-sw` nuôi nó, `UpdateBanner` nghe nó. */
export const updateSignal = createUpdateSignal();
