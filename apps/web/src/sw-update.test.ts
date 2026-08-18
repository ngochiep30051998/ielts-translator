import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  applyUpdate,
  createUpdateSignal,
  startUpdateChecks,
  watchForUpdate,
} from './sw-update';

/**
 * Phát hiện bản mới của web app.
 *
 * PWA cài vào màn hình chính thường KHÔNG BAO GIỜ được đóng — người dùng chỉ chuyển đi
 * chuyển lại. Không có luồng này thì họ chạy bundle của lần mở đầu tiên cho tới khi tự tay
 * đóng hẳn app, tức là mãi mãi: sửa lỗi xong deploy mà người dùng vẫn gặp đúng lỗi đó.
 *
 * Test dựng đối tượng giả thay vì dùng `navigator.serviceWorker` — jsdom không có service
 * worker, và kể cả có thì cũng không dựng được cảnh "worker mới vừa cài xong" theo ý muốn.
 */

class WorkerGia {
  state = 'installing';
  posted: unknown[] = [];
  private nguoiNghe = new Set<() => void>();
  addEventListener(_loai: 'statechange', cb: () => void) {
    this.nguoiNghe.add(cb);
  }
  postMessage(data: unknown) {
    this.posted.push(data);
  }
  /** Đẩy worker sang trạng thái mới và bắn `statechange`, y như trình duyệt làm. */
  chuyenSang(state: string) {
    this.state = state;
    this.nguoiNghe.forEach((cb) => cb());
  }
}

class DangKyGia {
  waiting: WorkerGia | null = null;
  installing: WorkerGia | null = null;
  soLanUpdate = 0;
  private nguoiNghe = new Set<() => void>();
  addEventListener(_loai: 'updatefound', cb: () => void) {
    this.nguoiNghe.add(cb);
  }
  async update() {
    this.soLanUpdate += 1;
  }
  /** Trình duyệt tìm thấy sw.js khác byte → tạo worker mới → bắn `updatefound`. */
  timThayBanMoi(worker: WorkerGia) {
    this.installing = worker;
    this.nguoiNghe.forEach((cb) => cb());
  }
}

class ContainerGia {
  controller: unknown = {};
  private nguoiNghe = new Set<() => void>();
  addEventListener(_loai: 'controllerchange', cb: () => void) {
    this.nguoiNghe.add(cb);
  }
  doiController() {
    this.nguoiNghe.forEach((cb) => cb());
  }
}

const asReg = (r: DangKyGia) => r as unknown as ServiceWorkerRegistration;
const asContainer = (c: ContainerGia) => c as unknown as ServiceWorkerContainer;
const asWorker = (w: WorkerGia) => w as unknown as ServiceWorker;

describe('watchForUpdate', () => {
  it('báo ngay nếu đã có bản đang CHỜ sẵn lúc trang mở', () => {
    // Người dùng đóng app khi bản mới vừa tải xong; lần mở sau nó nằm sẵn ở `waiting` và
    // sẽ không có sự kiện `updatefound` nào nữa. Không xét ca này là banner mất hẳn.
    const reg = new DangKyGia();
    reg.waiting = new WorkerGia();
    const bao = vi.fn();

    watchForUpdate(asReg(reg), asContainer(new ContainerGia()), bao);

    expect(bao).toHaveBeenCalledWith(asWorker(reg.waiting));
  });

  it('báo khi worker mới cài xong', () => {
    const reg = new DangKyGia();
    const bao = vi.fn();
    watchForUpdate(asReg(reg), asContainer(new ContainerGia()), bao);

    const moi = new WorkerGia();
    reg.timThayBanMoi(moi);
    moi.chuyenSang('installed');

    expect(bao).toHaveBeenCalledWith(asWorker(moi));
  });

  it('KHÔNG báo ở lần cài ĐẦU TIÊN — chưa có gì cũ để mà thay', () => {
    // Không có controller nghĩa là trang này chưa từng do service worker nào điều khiển.
    // Báo "đã có bản mới" cho người vừa mở app lần đầu là nói dối và làm họ reload vô ích.
    const container = new ContainerGia();
    container.controller = null;
    const reg = new DangKyGia();
    const bao = vi.fn();
    watchForUpdate(asReg(reg), asContainer(container), bao);

    const moi = new WorkerGia();
    reg.timThayBanMoi(moi);
    moi.chuyenSang('installed');

    expect(bao).not.toHaveBeenCalled();
  });

  it('KHÔNG báo khi bản mới cài HỎNG (redundant)', () => {
    const reg = new DangKyGia();
    const bao = vi.fn();
    watchForUpdate(asReg(reg), asContainer(new ContainerGia()), bao);

    const moi = new WorkerGia();
    reg.timThayBanMoi(moi);
    moi.chuyenSang('redundant');

    expect(bao).not.toHaveBeenCalled();
  });
});

describe('applyUpdate', () => {
  it('bảo worker đang chờ nhường chỗ, rồi tải lại khi nó đã cầm lái', () => {
    const worker = new WorkerGia();
    const container = new ContainerGia();
    const taiLai = vi.fn();

    applyUpdate(asWorker(worker), asContainer(container), taiLai);

    expect(worker.posted).toEqual([{ type: 'SKIP_WAITING' }]);
    expect(taiLai).not.toHaveBeenCalled();

    container.doiController();

    expect(taiLai).toHaveBeenCalledTimes(1);
  });

  it('chỉ tải lại MỘT lần dù controller đổi nhiều lần', () => {
    // Tải lại hai lần là màn hình nháy trắng hai nhịp, và ở kết nối chậm là hai lượt tải
    // lại chồng nhau.
    const container = new ContainerGia();
    const taiLai = vi.fn();
    applyUpdate(asWorker(new WorkerGia()), asContainer(container), taiLai);

    container.doiController();
    container.doiController();

    expect(taiLai).toHaveBeenCalledTimes(1);
  });
});

describe('startUpdateChecks', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function docGia(visibilityState = 'visible') {
    const nguoiNghe = new Set<() => void>();
    return {
      visibilityState,
      addEventListener: (_l: string, cb: () => void) => void nguoiNghe.add(cb),
      removeEventListener: (_l: string, cb: () => void) => void nguoiNghe.delete(cb),
      hienLai: () => nguoiNghe.forEach((cb) => cb()),
      soNguoiNghe: () => nguoiNghe.size,
    };
  }

  it('hỏi lại theo chu kỳ — PWA mở hàng ngày không có lượt điều hướng nào để tự hỏi', () => {
    const reg = new DangKyGia();
    startUpdateChecks(asReg(reg), { intervalMs: 1000, doc: docGia() as never });

    vi.advanceTimersByTime(3000);

    expect(reg.soLanUpdate).toBe(3);
  });

  it('hỏi lại khi người dùng quay lại tab', () => {
    const reg = new DangKyGia();
    const doc = docGia();
    startUpdateChecks(asReg(reg), { intervalMs: 60_000, minGapMs: 0, doc: doc as never });

    doc.hienLai();

    expect(reg.soLanUpdate).toBe(1);
  });

  it('KHÔNG hỏi dồn dập khi chuyển tab liên tục', () => {
    const reg = new DangKyGia();
    const doc = docGia();
    startUpdateChecks(asReg(reg), { intervalMs: 60_000, minGapMs: 5000, doc: doc as never });
    vi.advanceTimersByTime(6000);

    doc.hienLai();
    doc.hienLai();
    doc.hienLai();

    expect(reg.soLanUpdate).toBe(1);
  });

  it('vừa mở trang thì chưa hỏi lại — lượt đăng ký vừa nãy đã là một lần hỏi rồi', () => {
    const reg = new DangKyGia();
    const doc = docGia();
    startUpdateChecks(asReg(reg), { intervalMs: 60_000, minGapMs: 5000, doc: doc as never });

    doc.hienLai();

    expect(reg.soLanUpdate).toBe(0);
  });

  it('tab đang ẩn thì không hỏi', () => {
    const reg = new DangKyGia();
    const doc = docGia('hidden');
    startUpdateChecks(asReg(reg), { intervalMs: 60_000, minGapMs: 0, doc: doc as never });

    doc.hienLai();

    expect(reg.soLanUpdate).toBe(0);
  });

  it('dừng lại là gỡ sạch cả hẹn giờ lẫn người nghe', () => {
    const reg = new DangKyGia();
    const doc = docGia();
    const dung = startUpdateChecks(asReg(reg), { intervalMs: 1000, doc: doc as never });

    dung();
    vi.advanceTimersByTime(5000);

    expect(reg.soLanUpdate).toBe(0);
    expect(doc.soNguoiNghe()).toBe(0);
  });
});

describe('createUpdateSignal', () => {
  it('người đăng ký TRƯỚC được gọi khi có bản mới', () => {
    const signal = createUpdateSignal();
    const cb = vi.fn();
    signal.subscribe(cb);

    const reg = new DangKyGia();
    reg.waiting = new WorkerGia();
    signal.watch(asReg(reg), asContainer(new ContainerGia()));

    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('người đăng ký SAU được gọi ngay — React mount muộn hơn service worker', () => {
    // Banner là component React, nó mount sau khi `registerServiceWorker` đã chạy. Không
    // phát lại trạng thái đã có thì banner không bao giờ hiện ở đúng ca này.
    const signal = createUpdateSignal();
    const reg = new DangKyGia();
    reg.waiting = new WorkerGia();
    signal.watch(asReg(reg), asContainer(new ContainerGia()));

    const cb = vi.fn();
    signal.subscribe(cb);

    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('huỷ đăng ký thì thôi nhận', () => {
    const signal = createUpdateSignal();
    const cb = vi.fn();
    signal.subscribe(cb)();

    const reg = new DangKyGia();
    reg.waiting = new WorkerGia();
    signal.watch(asReg(reg), asContainer(new ContainerGia()));

    expect(cb).not.toHaveBeenCalled();
  });

  it('chưa có bản mới thì `apply` không tải lại trang', () => {
    const signal = createUpdateSignal();
    const taiLai = vi.fn();

    signal.apply(taiLai);

    expect(taiLai).not.toHaveBeenCalled();
  });

  it('`apply` áp dụng đúng worker đang chờ', () => {
    const signal = createUpdateSignal();
    const reg = new DangKyGia();
    reg.waiting = new WorkerGia();
    const container = new ContainerGia();
    signal.watch(asReg(reg), asContainer(container));

    const taiLai = vi.fn();
    signal.apply(taiLai);

    expect(reg.waiting.posted).toEqual([{ type: 'SKIP_WAITING' }]);
    container.doiController();
    expect(taiLai).toHaveBeenCalledTimes(1);
  });
});
