import { useCallback, useEffect, useRef, useState } from 'react';
import { sendToBackground } from '../messages';
import { surfaceCapabilities } from '../surface';
import { pageSlots } from '../pagination';
<<<<<<< Updated upstream
import { loadSettings } from '../settings';
import type { ApiError, VocabEntryDto } from '../types';
=======
import { MASTERED_REPETITIONS, vocabProgress } from '../vocab-progress';
import { topicMastery } from '../today';
import type { ApiError, VocabEntryDto, VocabTagsResponse } from '../types';
>>>>>>> Stashed changes

const SEARCH_DEBOUNCE_MS = 300;
const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

<<<<<<< Updated upstream
/** Từ khoá tìm kiếm và số trang phải nằm trong CÙNG một state.
=======
/** Ba màu chip chủ đề, xoay vòng theo THỨ TỰ backend trả về. Không mang nghĩa gì thêm. */
const TOPIC_TONES = ['a', 'b', 'c'] as const;

/** Số ô chủ đề nhiều màu ở đầu tab — đúng ba, như khung 1b vẽ. */
const TOPIC_CARDS = 3;

/** Từ khoá tìm kiếm, chủ đề đang lọc và số trang phải nằm trong CÙNG một state.
>>>>>>> Stashed changes
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

  // Ba chủ đề đầu bảng — backend đã sắp `count DESC, tag ASC`, client KHÔNG sắp lại.
  const topicCards = tagInfo.tags.slice(0, TOPIC_CARDS).map(topicMastery);
  /** Chủ đề đang lọc, để vẽ tiêu đề nhóm. `undefined` = đang xem cả sổ. */
  const activeTopic = cursor.tag === null
    ? undefined
    : tagInfo.tags.filter((t) => t.tag === cursor.tag).map(topicMastery)[0];

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

<<<<<<< Updated upstream
      {loading && <p className="status">Đang tải…</p>}
=======
      {/* Ba ô chủ đề nhiều màu: đường tắt tới những chủ đề đang có nhiều từ nhất, kèm mức
          thành thạo để thấy ngay chỗ nào còn yếu. Hàng chip ngay dưới vẫn là chỗ lọc ĐẦY
          ĐỦ — ba ô này chỉ là ba mục đầu bảng, không thay thế nó. */}
      {topicCards.length > 0 && (
        <div className="topic-cards">
          {topicCards.map((topic, i) => (
            <button
              key={topic.tag}
              type="button"
              className="topic-card"
              data-tone={TOPIC_TONES[i % TOPIC_TONES.length]}
              aria-pressed={cursor.tag === topic.tag}
              aria-label={`Chủ đề ${topic.tag}, ${topic.count} từ, thành thạo ${topic.percent}%`}
              onClick={() => filterByTag(topic.tag)}
            >
              <span className="topic-card-count">{topic.count}</span>
              <span className="topic-card-name">{topic.tag}</span>
              {/* Thanh mang aria-hidden: nhãn của nút đã nói đúng con số này bằng lời. */}
              <span className="topic-card-track" aria-hidden="true">
                <i style={{ width: `${topic.percent}%` }} />
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Điều kiện là `tags.length`, KHÔNG phải `total > 0` — và đó là cố ý. Sổ từ chưa gắn
          thẻ nào thì hàng chip chỉ còn "Tất cả N" với "Chưa gắn N" bằng đúng nhau, tức hai
          nút lọc ra cùng một danh sách. Tổng số từ vẫn đọc được ở dòng "N từ" ngay bên dưới,
          nên ẩn cả hàng không giấu mất thông tin nào. Đừng đổi thành `total > 0`. */}
      {tagInfo.tags.length > 0 && (
        <div className="vocab-tags" role="group" aria-label="Lọc theo chủ đề">
          {/* "Tất cả" luôn đứng đầu: nó là đường về, và người dùng phải thấy nó ở chỗ cố
              định chứ không phải đi tìm giữa hàng chip đang đổi theo sổ từ.

              Con số lấy từ `tagInfo.total` — tổng KHÔNG lọc. Lấy `total` của lượt tìm kiếm
              đang lọc sẽ biến chip này thành bản sao con số của chủ đề vừa bấm, và người
              dùng mất luôn tham chiếu "cả sổ có bao nhiêu từ". */}
          <button
            type="button"
            className="vocab-tag"
            data-tone="all"
            aria-pressed={cursor.tag === null && !cursor.untagged}
            aria-label={`Lọc theo Tất cả, ${tagInfo.total} từ`}
            onClick={() => filterByTag(null)}
          >
            Tất cả <span className="vocab-tag-count">{tagInfo.total}</span>
          </button>
          {tagInfo.tags.map((t, i) => (
            <button
              key={t.tag}
              type="button"
              className="vocab-tag"
              data-tone={TOPIC_TONES[i % TOPIC_TONES.length]}
              aria-pressed={cursor.tag === t.tag}
              aria-label={`Lọc theo ${t.tag}, ${t.count} từ`}
              onClick={() => filterByTag(t.tag)}
            >
              {t.tag} <span className="vocab-tag-count">{t.count}</span>
            </button>
          ))}
          {/* "Chưa gắn" đứng CUỐI hàng — nó là chỗ dọn dẹp, không phải một chủ đề. Chỉ hiện
              khi còn từ chưa gắn thẻ: một chip đếm 0 là ô bấm vào ra danh sách rỗng. */}
          {tagInfo.untagged > 0 && (
            <button
              type="button"
              className="vocab-tag"
              data-tone="none"
              aria-pressed={cursor.untagged}
              aria-label={`Lọc theo Chưa gắn, ${tagInfo.untagged} từ`}
              onClick={() => filterUntagged()}
            >
              Chưa gắn <span className="vocab-tag-count">{tagInfo.untagged}</span>
            </button>
          )}
        </div>
      )}

      {/* Tiêu đề nhóm — chỉ khi đang lọc theo một chủ đề. Không lọc thì danh sách là cả
          sổ, và gán cho nó một cái tên nhóm là nói sai về thứ đang hiện. */}
      {activeTopic && (
        <div className="vocab-group">
          <span className="vocab-group-name">{activeTopic.tag}</span>
          <span className="vocab-group-mastery">thành thạo {activeTopic.percent}%</span>
        </div>
      )}

      {loading && (
        <p className="status" aria-live="polite">
          <Spinner /> Đang tải…
        </p>
      )}
>>>>>>> Stashed changes

      {!loading && entries.length === 0 && (
        <p className="empty">
            {surfaceCapabilities().selectionCapture
              ? 'Sổ từ đang trống. Lưu từ đầu tiên từ bubble dịch.'
              : 'Sổ từ đang trống. Dịch một từ ở tab Dịch rồi bấm Lưu.'}
          </p>
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
