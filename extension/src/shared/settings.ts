export type TriggerMode = 'auto' | 'hotkey';

export interface Settings {
  backendUrl: string;
  triggerMode: TriggerMode;
  voiceName: string | null;
}

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: 'http://127.0.0.1:8080',
  triggerMode: 'auto',
  voiceName: null,
};

const STORAGE_KEY = 'settings';

function normalise(raw: Partial<Settings>): Settings {
  const merged = { ...DEFAULT_SETTINGS, ...raw };
  return {
    backendUrl: merged.backendUrl.replace(/\/+$/, ''),
    triggerMode: merged.triggerMode === 'hotkey' ? 'hotkey' : 'auto',
    voiceName: merged.voiceName ?? null,
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
