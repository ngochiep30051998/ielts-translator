import { useEffect, useState } from 'react';
import { DEFAULT_SETTINGS, loadSettings, saveSettings, type Settings } from '../shared/settings';
import { sendToBackground } from '../shared/messages';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

export function Options() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<Status>(null);

  useEffect(() => {
    void (async () => {
      setSettings(await loadSettings());
      setLoaded(true);
    })();
  }, []);

  async function save() {
    setSettings(await saveSettings(settings));
    setSaveStatus('Đã lưu cài đặt');
  }

  async function checkHealth() {
    setHealthStatus({ text: 'Đang kiểm tra…', kind: 'ok' });
    const response = await sendToBackground({ type: 'CHECK_HEALTH' });
    if (!response.ok) {
      setHealthStatus({ text: response.error.message, kind: 'bad' });
      return;
    }
    setHealthStatus(response.data.geminiConfigured
      ? { text: 'Backend đang chạy, Gemini đã cấu hình.', kind: 'ok' }
      : { text: 'Backend đang chạy nhưng chưa cấu hình GEMINI_API_KEY trong file .env.', kind: 'bad' });
  }

  if (!loaded) return <p className="empty">Đang tải…</p>;

  return (
    <main className="options">
      <h1>Cài đặt IELTS Translator</h1>

      <label htmlFor="backendUrl">Địa chỉ backend</label>
      <input
        id="backendUrl"
        type="url"
        value={settings.backendUrl}
        onChange={(e) => setSettings({ ...settings, backendUrl: e.target.value })}
      />

      <fieldset>
        <legend>Chế độ kích hoạt</legend>
        <div className="segmented">
          <label>
            <input
              type="radio"
              name="triggerMode"
              checked={settings.triggerMode === 'auto'}
              onChange={() => setSettings({ ...settings, triggerMode: 'auto' })}
            />
            Hiện icon khi bôi đen
          </label>
          <label>
            <input
              type="radio"
              name="triggerMode"
              checked={settings.triggerMode === 'hotkey'}
              onChange={() => setSettings({ ...settings, triggerMode: 'hotkey' })}
            />
            Chỉ khi bấm Alt+T
          </label>
        </div>
      </fieldset>

      <label htmlFor="newWordsPerDay">Từ mới mỗi ngày (0 = không giới hạn)</label>
      <input
        id="newWordsPerDay"
        type="number"
        min={0}
        max={200}
        value={settings.newWordsPerDay}
        onChange={(e) =>
          setSettings({ ...settings, newWordsPerDay: Number(e.target.value) })
        }
      />

      <label htmlFor="voiceName">Giọng đọc (để trống dùng giọng en mặc định)</label>
      <input
        id="voiceName"
        type="text"
        value={settings.voiceName ?? ''}
        onChange={(e) => setSettings({ ...settings, voiceName: e.target.value || null })}
      />

      <div className="options-actions">
        <button type="button" onClick={() => void save()}>Lưu</button>
        <button type="button" onClick={() => void checkHealth()}>Kiểm tra kết nối</button>
      </div>

      {saveStatus && <p className="status ok">{saveStatus}</p>}
      {healthStatus && <p className={`status ${healthStatus.kind}`}>{healthStatus.text}</p>}
    </main>
  );
}
