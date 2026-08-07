import { useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { PayloadView } from './PayloadViews';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

export interface TranslateTabProps {
  result: TranslateResult | null;
  loaded: boolean;
}

export function TranslateTab({ result, loaded }: TranslateTabProps) {
  const [status, setStatus] = useState<Status>(null);

  async function save() {
    if (!result) return;
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_WORD', result, tags: [] });
    setStatus(response.ok
      ? {
          text: response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ từ',
          kind: 'ok',
        }
      : { text: response.error.message, kind: 'bad' });
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
        {status && <p className={`status ${status.kind}`}>{status.text}</p>}
      </div>
    </div>
  );
}
