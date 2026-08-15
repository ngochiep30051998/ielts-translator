import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { sendToBackground } from '../messages';
import { surfaceCapabilities } from '../surface';
import { MAX_SELECTION_LENGTH, validateSelection } from '../text';
import type { ApiError, TranslateResult } from '../types';
import { PayloadView } from './PayloadViews';
import { Spinner } from './Spinner';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

/** Lỗi dịch kèm ĐÚNG đoạn text đã gửi, để "Thử lại" không đọc lại ô nhập. */
type Failure = { error: ApiError; text: string } | null;

export interface TranslateTabProps {
  draft: string;
  onDraftChange: (value: string) => void;
  result: TranslateResult | null;
  onResult: (result: TranslateResult) => void;
  loaded: boolean;
}

export function TranslateTab({
  draft, onDraftChange, result, onResult, loaded,
}: TranslateTabProps) {
  const [status, setStatus] = useState<Status>(null);
  const [translating, setTranslating] = useState(false);
  /** Chặn bấm Lưu hai lần. Không có nó thì hai lượt SAVE_WORD cùng bay đi. */
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<Failure>(null);

  const check = validateSelection(draft);
  const tooLong = !check.ok && check.reason === 'TOO_LONG';

  async function translate(text: string) {
    // Guard nằm ở đây, không phải ở từng call site: cả nút "Dịch" (qua submit()) lẫn nút
    // "Thử lại" (gọi translate() thẳng) đều phải đi qua đúng một chỗ chặn re-entrant.
    if (translating) return;
    setTranslating(true);
    setFailure(null);
    setStatus(null);
    const response = await sendToBackground({ type: 'TRANSLATE_TEXT', text });
    setTranslating(false);
    if (response.ok) onResult(response.data);
    else setFailure({ error: response.error, text });
  }

  // Guard `translating` nằm trong translate(), không ở đây: nó thuộc về hàm giữ
  // invariant, không thuộc về một call site.
  function submit() {
    if (!check.ok) return;
    void translate(check.text);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      submit();
    }
  }

  async function save() {
    // `saving` chặn lượt thứ hai kể cả khi nút chưa kịp disabled — người dùng bấm nhanh hơn
    // một nhịp render là chuyện thường trên điện thoại.
    if (!result || saving) return;
    setSaving(true);
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_WORD', result, tags: [] });
    setStatus(response.ok
      ? {
          text: response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ từ',
          kind: 'ok',
        }
      : { text: response.error.message, kind: 'bad' });
    setSaving(false);
  }

  if (!loaded) return <p className="empty"><Spinner /> Đang tải…</p>;

  return (
    <div className="translate-tab">
      <div className="translate-input">
        <textarea
          rows={3}
          value={draft}
          aria-label="Text cần dịch"
          placeholder="Nhập hoặc dán text để dịch…"
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="translate-input-foot">
          {/* Đếm theo độ dài ĐÃ TRIM để khớp đúng thứ validateSelection kiểm tra —
              nếu không, một đoạn 1501 ký tự có khoảng trắng cuối sẽ hiện đỏ mà vẫn dịch được. */}
          <span className={tooLong ? 'counter over' : 'counter'}>
            {draft.trim().length}/{MAX_SELECTION_LENGTH}
          </span>
          <button
            type="button"
            disabled={!check.ok || translating}
            aria-busy={translating}
            onClick={submit}
          >
            {translating && <Spinner />}
            <span>{translating ? 'Đang dịch…' : 'Dịch'}</span>
          </button>
        </div>
        {failure && (
          <p className="status bad">
            {failure.error.message}
            {failure.error.retryable && (
              <button type="button" onClick={() => void translate(failure.text)}>
                Thử lại
              </button>
            )}
          </p>
        )}
      </div>

      {result ? (
        <>
          <PayloadView result={result} />
          <div className="actions">
            <button type="button" disabled={saving} aria-busy={saving} onClick={() => void save()}>
              {saving && <Spinner />}
              <span>{saving ? 'Đang lưu…' : 'Lưu từ'}</span>
            </button>
            {result.cached && <span className="cached-hint">từ cache</span>}
            {status && <p className={`status ${status.kind}`}>{status.text}</p>}
          </div>
        </>
      ) : (
        <p className="empty">
            {surfaceCapabilities().selectionCapture
              ? 'Bôi đen text trên trang, hoặc nhập vào ô trên rồi bấm Dịch.'
              : 'Nhập hoặc dán text vào ô trên rồi bấm Dịch.'}
          </p>
      )}
    </div>
  );
}
