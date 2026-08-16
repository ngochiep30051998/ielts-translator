import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { keyVocabOf } from '../key-vocab';
import { sendToBackground } from '../messages';
import type { SaveKeyVocabResult } from '../messages';
import { surfaceCapabilities } from '../surface';
import { MAX_SELECTION_LENGTH, validateSelection } from '../text';
import type { ApiError, TranslateResult } from '../types';
import { PayloadView } from './PayloadViews';
import { Spinner } from './Spinner';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

/**
 * Diễn kết quả một mẻ lưu từ đáng học thành câu cho người dùng đọc.
 *
 * Bốn ca tách bạch chứ không gộp thành "đã lưu" / "có lỗi": một mẻ 5 từ có thể vừa thêm mới,
 * vừa đụng từ đã có, vừa hỏng vài từ — và người dùng cần biết chính xác cái nào, vì việc phải
 * làm tiếp khác hẳn nhau (bỏ qua, hay bấm lại).
 */
function keyVocabStatus(outcome: SaveKeyVocabResult): NonNullable<Status> {
  if (outcome.failures.length > 0) {
    // Nêu thông điệp lỗi ĐẦU TIÊN chứ không gộp thành "có lỗi xảy ra": phần lớn mẻ hỏng là
    // hỏng vì cùng một lý do, và lý do đó cho biết có nên thử lại hay không.
    return {
      text: `Đã lưu ${outcome.saved} từ, ${outcome.failures.length} từ lỗi: `
        + outcome.failures[0].error.message,
      kind: 'bad',
    };
  }
  if (outcome.existed === 0) return { text: `Đã lưu ${outcome.saved} từ vào sổ`, kind: 'ok' };
  if (outcome.saved === 0) {
    return { text: `Cả ${outcome.existed} từ đều đã có trong sổ`, kind: 'ok' };
  }
  return { text: `Đã lưu ${outcome.saved} từ, ${outcome.existed} từ đã có sẵn`, kind: 'ok' };
}

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
  /**
   * Cờ RIÊNG cho mẻ từ đáng học, không dùng chung với `saving`.
   *
   * Chung một cờ thì bấm một nút là khoá luôn nút kia cho tới khi xong — mà mẻ từ đáng học
   * là N lượt POST tuần tự, tức là lâu hơn hẳn một lượt lưu thường.
   */
  const [savingKeyVocab, setSavingKeyVocab] = useState(false);
  const [failure, setFailure] = useState<Failure>(null);

  const check = validateSelection(draft);
  const tooLong = !check.ok && check.reason === 'TOO_LONG';

  // Số từ THẬT sau khi lọc và bỏ trùng — nhãn nút phải nói đúng số sẽ được gửi đi, không
  // phải độ dài thô của `key_vocab`. Rỗng ở mọi tổ hợp trừ EN→VI chế độ CÂU.
  const keyVocab = result ? keyVocabOf(result) : [];

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

  /** Lưu cả mẻ "từ đáng học" của một câu EN→VI. Việc lọc/bỏ trùng/gọi HTTP nằm ở core. */
  async function saveKeyVocab() {
    if (!result || savingKeyVocab) return;
    setSavingKeyVocab(true);
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_KEY_VOCAB', result, tags: [] });
    setStatus(response.ok
      ? keyVocabStatus(response.data)
      : { text: response.error.message, kind: 'bad' });
    setSavingKeyVocab(false);
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
            {/* Chỉ EN→VI chế độ CÂU mới có từ đáng học — ba tổ hợp còn lại cho mảng rỗng. */}
            {keyVocab.length > 0 && (
              <button
                type="button"
                disabled={savingKeyVocab}
                aria-busy={savingKeyVocab}
                onClick={() => void saveKeyVocab()}
              >
                {savingKeyVocab && <Spinner />}
                <span>
                  {savingKeyVocab ? 'Đang lưu…' : `Lưu ${keyVocab.length} từ đáng học`}
                </span>
              </button>
            )}
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
