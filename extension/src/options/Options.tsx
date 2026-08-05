import { useEffect, useState } from 'react';
import { DEFAULT_SETTINGS, loadSettings, saveSettings, type Settings } from '../shared/settings';
import { sendToBackground } from '../shared/messages';

export function Options() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<string | null>(null);

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
    setHealthStatus('Đang kiểm tra…');
    const response = await sendToBackground({ type: 'CHECK_HEALTH' });
    if (!response.ok) {
      setHealthStatus(response.error.message);
      return;
    }
    setHealthStatus(response.data.geminiConfigured
      ? 'Backend đang chạy, Gemini đã cấu hình.'
      : 'Backend đang chạy nhưng chưa cấu hình GEMINI_API_KEY trong file .env.');
  }

  if (!loaded) return <p>Đang tải…</p>;

  return (
    <main className="options">
      <h1>IELTS Translator — Cài đặt</h1>

      <label htmlFor="backendUrl">Địa chỉ backend</label>
      <input
        id="backendUrl"
        type="url"
        value={settings.backendUrl}
        onChange={(e) => setSettings({ ...settings, backendUrl: e.target.value })}
      />

      <fieldset>
        <legend>Chế độ kích hoạt</legend>
        <label>
          <input
            type="radio"
            name="triggerMode"
            checked={settings.triggerMode === 'auto'}
            onChange={() => setSettings({ ...settings, triggerMode: 'auto' })}
          />
          Tự hiện bubble khi bôi đen
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
      </fieldset>

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

      {saveStatus && <p className="status">{saveStatus}</p>}
      {healthStatus && <p className="status">{healthStatus}</p>}
    </main>
  );
}
