import { useCallback, useEffect, useRef, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import { pageSlots } from '../shared/pagination';
import { loadSettings } from '../shared/settings';
import type { ApiError, VocabEntryDto } from '../shared/types';

const SEARCH_DEBOUNCE_MS = 300;
const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

/** Từ khoá tìm kiếm và số trang phải nằm trong CÙNG một state.
 *
 * Gõ một phím vừa đổi từ khoá vừa phải kéo trang về 0 — tách thành hai state thì hai lần
 * `set` đó cho effect thấy một trạng thái trung gian (từ khoá mới, trang cũ) và bắn thừa
 * một request cho trang không ai còn muốn xem.
 */
interface Cursor {
  text: string;
  page: number;
}

export function VocabTab() {
  const [cursor, setCursor] = useState<Cursor>({ text: '', page: 0 });
  const [entries, setEntries] = useState<VocabEntryDto[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async ({ text, page }: Cursor) => {
    setLoading(true);
    const response = await sendToBackground({
      type: 'SEARCH_VOCAB', query: text || null, tag: null, page,
    });
    if (response.ok) {
      setEntries(response.data.content);
      setTotal(response.data.totalElements);
      setTotalPages(response.data.totalPages);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  const lastText = useRef(cursor.text);
  useEffect(() => {
    // Debounce chỉ dành cho việc gõ. Bấm nút chuyển trang là một ý định đã dứt khoát —
    // bắt nó chờ thêm 300ms chỉ làm side panel có cảm giác ì.
    const delay = cursor.text === lastText.current ? 0 : SEARCH_DEBOUNCE_MS;
    lastText.current = cursor.text;
    const timer = window.setTimeout(() => void load(cursor), delay);
    return () => window.clearTimeout(timer);
  }, [cursor, load]);

  function goToPage(page: number) {
    setCursor((c) => ({ ...c, page }));
  }

  async function remove(id: number) {
    const response = await sendToBackground({ type: 'DELETE_VOCAB', id });
    if (!response.ok) {
      setError(response.error);
      return;
    }
    // Xoá mục cuối cùng của một trang không phải trang đầu để lại một trang rỗng mà người
    // dùng không tự thoát ra được — lùi một trang, effect ở trên lo việc nạp.
    if (entries.length === 1 && cursor.page > 0) {
      setCursor((c) => ({ ...c, page: c.page - 1 }));
      return;
    }
    await load(cursor);
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
          <button type="button" onClick={() => void load(cursor)}>Thử lại</button>
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
          value={cursor.text}
          onChange={(e) => setCursor({ text: e.target.value, page: 0 })}
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
                  {e.pos && <span className="meta">{e.pos}</span>}
                  <span className="vi">{e.meaningVi}</span>
                </div>
                {e.bandLevel && (
                  <span className="band" title={BAND_HINT}>{e.bandLevel}</span>
                )}
                <button type="button" aria-label={`Xoá ${e.term}`} onClick={() => void remove(e.id)}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {totalPages > 1 && (
        <nav className="vocab-pager" aria-label="Phân trang sổ từ">
          <button
            type="button"
            aria-label="Trang trước"
            disabled={cursor.page === 0}
            onClick={() => goToPage(cursor.page - 1)}
          >
            ‹
          </button>
          {pageSlots(cursor.page, totalPages).map((slot, i) =>
            slot === 'gap' ? (
              // Dấu … không phải nút và cũng không đáng đọc lên — trình đọc màn hình đã có
              // aria-current trên trang đang xem để định vị.
              <span key={`gap-${i}`} className="vocab-pager-gap" aria-hidden="true">…</span>
            ) : (
              <button
                key={slot}
                type="button"
                aria-label={`Trang ${slot + 1}`}
                aria-current={slot === cursor.page ? 'page' : undefined}
                onClick={() => goToPage(slot)}
              >
                {slot + 1}
              </button>
            ))}
          <button
            type="button"
            aria-label="Trang sau"
            disabled={cursor.page >= totalPages - 1}
            onClick={() => goToPage(cursor.page + 1)}
          >
            ›
          </button>
        </nav>
      )}
    </div>
  );
}
