import type { Transport } from './ports';

/**
 * Transport đang dùng của surface này.
 *
 * Singleton cấp module chứ không phải React context, vì `sendToBackground` được gọi từ cả
 * chỗ không có React (service worker của extension). Mỗi surface gọi `setTransport` đúng
 * một lần lúc khởi động.
 */
let current: Transport | null = null;

export function setTransport(transport: Transport | null): void {
  current = transport;
}

export function currentTransport(): Transport | null {
  return current;
}
