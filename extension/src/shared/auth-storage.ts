import type { AuthUser } from './types';

/**
 * Token phiên nằm ở `chrome.storage.local`, KHÔNG phải `sync`.
 *
 * `sync` sẽ đẩy token sang mọi profile Chrome đăng nhập cùng tài khoản Google — biến một
 * phiên bị lộ thành tất cả. Đồng bộ dữ liệu học là việc của backend, không phải của storage.
 */
const TOKEN_KEY = 'authToken';
const USER_KEY = 'authUser';

export interface StoredAuth {
  token: string;
  user: AuthUser;
}

export async function saveAuth(token: string, user: AuthUser): Promise<void> {
  await chrome.storage.local.set({ [TOKEN_KEY]: token, [USER_KEY]: user });
}

/** Trả null khi chưa đăng nhập — KHÔNG bao giờ ném, kể cả khi storage hỏng. */
export async function loadAuth(): Promise<StoredAuth | null> {
  try {
    const raw = await chrome.storage.local.get([TOKEN_KEY, USER_KEY]);
    const token = raw[TOKEN_KEY];
    const user = raw[USER_KEY];
    if (typeof token !== 'string' || !token || !user || typeof user !== 'object') {
      return null;
    }
    return { token, user: user as AuthUser };
  } catch {
    return null;
  }
}

export async function loadToken(): Promise<string | null> {
  return (await loadAuth())?.token ?? null;
}

export async function clearAuth(): Promise<void> {
  await chrome.storage.local.remove([TOKEN_KEY, USER_KEY]);
}
