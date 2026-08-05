import { useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { PayloadView } from './PayloadViews';

export function TranslateTab() {
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const response = await sendToBackground({ type: 'GET_LAST_RESULT' });
      if (response.ok) setResult(response.data);
      setLoaded(true);
    })();
  }, []);

  async function save() {
    if (!result) return;
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_WORD', result, tags: [] });
    setStatus(response.ok
      ? (response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ từ')
      : response.error.message);
  }

  if (!loaded) return <p className="empty">Đang tải…</p>;

  if (!result) {
    return <p className="empty">Bôi đen một đoạn text trên trang web để bắt đầu.</p>;
  }

  return (
    <div className="translate-tab">
      <PayloadView result={result} />
      <div className="actions">
        <button type="button" onClick={() => void save()}>Lưu từ</button>
        {result.cached && <span className="cached-hint">từ cache</span>}
      </div>
      {status && <p className="status">{status}</p>}
    </div>
  );
}
