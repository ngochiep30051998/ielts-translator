import { useCallback, useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import { loadSettings } from '../shared/settings';
import type { ApiError, VocabEntryDto } from '../shared/types';

const SEARCH_DEBOUNCE_MS = 300;

export function VocabTab() {
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState<VocabEntryDto[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    const response = await sendToBackground({
      type: 'SEARCH_VOCAB', query: q || null, tag: null, page: 0,
    });
    if (response.ok) {
      setEntries(response.data.content);
      setTotal(response.data.totalElements);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query, load]);

  async function remove(id: number) {
    const response = await sendToBackground({ type: 'DELETE_VOCAB', id });
    if (!response.ok) {
      setError(response.error);
      return;
    }
    await load(query);
  }

  async function openExport() {
    const { backendUrl } = await loadSettings();
    window.open(`${backendUrl}/api/vocab/export.csv`, '_blank');
  }

  if (error) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && (
          <button type="button" onClick={() => void load(query)}>Thử lại</button>
        )}
      </div>
    );
  }

  return (
    <div className="vocab-tab">
      <div className="vocab-toolbar">
        <input
          type="search"
          placeholder="Tìm từ hoặc nghĩa…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="button" onClick={() => void openExport()}>CSV</button>
      </div>

      {loading && <p className="status">Đang tải…</p>}

      {!loading && entries.length === 0 && (
        <p className="empty">Sổ từ đang trống. Lưu từ đầu tiên từ bubble dịch.</p>
      )}

      {entries.length > 0 && (
        <>
          <p className="status">{total} từ</p>
          <ul className="vocab-list">
            {entries.map((e) => (
              <li key={e.id} className="vocab-item">
                <div>
                  <strong>{e.term}</strong>
                  {e.pos && <span className="meta"> · {e.pos}</span>}
                  {e.bandLevel && (
                    <span className="band" title="Band do AI ước lượng, chỉ mang tính tham khảo">
                      {e.bandLevel}
                    </span>
                  )}
                  <span className="vi">{e.meaningVi}</span>
                </div>
                <button type="button" aria-label={`Xoá ${e.term}`} onClick={() => void remove(e.id)}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
