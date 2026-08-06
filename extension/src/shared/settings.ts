export type TriggerMode = 'auto' | 'hotkey';

export interface Settings {
  backendUrl: string;
  triggerMode: TriggerMode;
  voiceName: string | null;
  /** Số thẻ MỚI tối đa được đưa vào hàng đợi ôn mỗi ngày. */
  newWordsPerDay: number;
}

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: 'http://127.0.0.1:8080',
  triggerMode: 'auto',
  voiceName: null,
  newWordsPerDay: 30,
};

const STORAGE_KEY = 'settings';
const MAX_NEW_WORDS_PER_DAY = 200;

/** Giá trị lạ (NaN, chuỗi, undefined) quay về mặc định thay vì lọt xuống backend. */
function normaliseNewWordsPerDay(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return DEFAULT_SETTINGS.newWordsPerDay;
  }
  return Math.min(MAX_NEW_WORDS_PER_DAY, Math.max(0, Math.round(value)));
}

function normalise(raw: Partial<Settings>): Settings {
  const merged = { ...DEFAULT_SETTINGS, ...raw };
  return {
    backendUrl: merged.backendUrl.replace(/\/+$/, ''),
    triggerMode: merged.triggerMode === 'hotkey' ? 'hotkey' : 'auto',
    voiceName: merged.voiceName ?? null,
    newWordsPerDay: normaliseNewWordsPerDay(merged.newWordsPerDay),
  };
}

export async function loadSettings(): Promise<Settings> {
  const stored = await chrome.storage.local.get([STORAGE_KEY]);
  return normalise((stored[STORAGE_KEY] ?? {}) as Partial<Settings>);
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = normalise({ ...(await loadSettings()), ...patch });
  await chrome.storage.local.set({ [STORAGE_KEY]: next });
  return next;
}
