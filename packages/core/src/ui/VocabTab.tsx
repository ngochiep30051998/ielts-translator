import { useCallback, useEffect, useRef, useState } from 'react';
import { sendToBackground } from '../messages';
import { Spinner } from './Spinner';
import { surfaceCapabilities } from '../surface';
import { pageSlots } from '../pagination';
import { MASTERED_REPETITIONS, vocabProgress } from '../vocab-progress';
import type { ApiError, VocabEntryDto, VocabTagsResponse } from '../types';

const SEARCH_DEBOUNCE_MS = 300;
const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

/** Ba màu chip chủ đề, xoay vòng theo THỨ TỰ backend trả về. Không mang nghĩa gì thêm. */
const TOPIC_TONES = ['a', 'b', 'c'] as const;

/** Từ khoá tìm kiếm, chủ đề đang lọc và số trang phải nằm trong CÙNG một state.
 *
 * Gõ một phím vừa đổi từ khoá vừa phải kéo trang về 0 — tách thành hai state thì hai lần
 * `set` đó cho effect thấy một trạng thái trung gian (từ khoá mới, trang cũ) và bắn thừa
 * một request cho trang không ai còn muốn xem. Chip chủ đề y hệt: đang ở trang 3 của cả sổ
 * rồi lọc còn 24 từ thì trang 3 không tồn tại, và người dùng nhận một danh sách rỗng cho
 * một chủ đề đang có từ.
 */
interface Cursor {
  text: string;
  /** `null` = không lọc. KHÔNG dùng chuỗi rỗng: `tag=` trên URL là lọc theo tên rỗng. */
  tag: string | null;
  /** true = chỉ những từ chưa gắn thẻ nào. KHÔNG bao giờ đi cùng `tag` — backend trả 400. */
  untagged: boolean;
  page: number;
}

/** Bản nháp của form sửa. `null` = không có dòng nào đang mở form. */
interface EditDraft {
  id: number;
  meaningVi: string;
  /** Chủ đề nhập tay, cách nhau bằng dấu phẩy. */
  tags: string;
}

/** "a, b , ,c" → ["a", "b", "c"]. Bỏ khoảng trắng thừa và mục rỗng. */
function parseTags(raw: string): string[] {
  return raw.split(',').map((t) => t.trim()).filter((t) => t.length > 0);
}

export function VocabTab() {
  const [cursor, setCursor] = useState<Cursor>({
    text: '', tag: null, untagged: false, page: 0,
  });
  const [entries, setEntries] = useState<VocabEntryDto[]>([]);
  /** Dữ liệu hàng chip. `total` ở đây là tổng KHÔNG lọc, khác hẳn `total` ngay dưới. */
  const [tagInfo, setTagInfo] = useState<VocabTagsResponse>({
    total: 0, untagged: 0, tags: [],
  });
  /** Số từ của LƯỢT TÌM KIẾM hiện tại (đã lọc) — dòng "N từ" trên đầu danh sách. */
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  /**
   * Id của từ đang bị xoá — theo TỪNG DÒNG, không phải một cờ chung.
   *
   * Một cờ chung sẽ khoá nút xoá của cả danh sách trong lúc xoá một từ, và trên màn hình
   * dài thì người dùng không hiểu vì sao mọi thứ bỗng đơ.
   */
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async ({ text, tag, untagged, page }: Cursor) => {
    setLoading(true);
    const response = await sendToBackground({
      type: 'SEARCH_VOCAB', query: text || null, tag, untagged, page,
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
    // Debounce chỉ dành cho việc gõ. Bấm nút chuyển trang hay chip chủ đề là một ý định đã
    // dứt khoát — bắt nó chờ thêm 300ms chỉ làm side panel có cảm giác ì.
    const delay = cursor.text === lastText.current ? 0 : SEARCH_DEBOUNCE_MS;
    lastText.current = cursor.text;
    const timer = window.setTimeout(() => void load(cursor), delay);
    return () => window.clearTimeout(timer);
  }, [cursor, load]);

  /**
   * Nạp dữ liệu hàng chip — MỘT lượt gọi cho cả tổng, số chưa gắn thẻ và danh sách chủ đề.
   *
   * KHÔNG kèm theo mỗi lượt tìm kiếm (gõ một phím là một lượt), nhưng phải gọi lại sau MỌI
   * lượt đổi dữ liệu. Nút "Sửa" ngay trên màn hình này đổi được `tags`: sửa chủ đề của một
   * từ xong mà không nạp lại thì chủ đề MỚI không có chip nào — người dùng vừa tạo ra một
   * chủ đề mà không lọc theo nó được cho tới khi đóng/mở lại panel. Xoá từ cũng vậy, chip cũ
   * ở lại thành một ô bấm vào ra danh sách rỗng.
   *
   * Hỏng thì im lặng bỏ hàng chip đi — nó là đường tắt, ô tìm kiếm vẫn lọc được.
   */
  const loadTags = useCallback(async () => {
    const response = await sendToBackground({ type: 'GET_VOCAB_TAGS' });
    if (response.ok) setTagInfo(response.data);
  }, []);

  useEffect(() => {
    void loadTags();
  }, [loadTags]);

  function goToPage(page: number) {
    setCursor((c) => ({ ...c, page }));
  }

  /** Lọc theo một chủ đề, hoặc `null` để về "Tất cả". Luôn tắt `untagged`: hai điều kiện
   *  đó mâu thuẫn nhau và backend trả 400 nếu nhận cả hai. */
  function filterByTag(tag: string | null) {
    setCursor((c) => ({ ...c, tag, untagged: false, page: 0 }));
  }

  function filterUntagged() {
    setCursor((c) => ({ ...c, tag: null, untagged: true, page: 0 }));
  }

  async function remove(id: number) {
    // Chặn lượt thứ hai kể cả khi nút chưa kịp disabled — người dùng bấm nhanh hơn một nhịp
    // render là chuyện thường trên điện thoại. Xoá hai lần thì lượt sau nhận NOT_FOUND, và
    // người dùng thấy một lỗi cho đúng việc họ vừa làm thành công.
    if (deletingId !== null) return;
    setDeletingId(id);
    const response = await sendToBackground({ type: 'DELETE_VOCAB', id });
    if (!response.ok) {
      setError(response.error);
      setDeletingId(null);
      return;
    }
    setDeletingId(null);
    // Xoá một từ có thể làm rỗng cả một chủ đề. Không nạp lại thì chip của nó ở lại, và bấm
    // vào ra danh sách rỗng.
    void loadTags();
    // Xoá mục cuối cùng của một trang không phải trang đầu để lại một trang rỗng mà người
    // dùng không tự thoát ra được — lùi một trang, effect ở trên lo việc nạp.
    if (entries.length === 1 && cursor.page > 0) {
      setCursor((c) => ({ ...c, page: c.page - 1 }));
      return;
    }
    await load(cursor);
  }

  /**
   * Lưu form sửa.
   *
   * Field nào KHÔNG đổi thì gửi `null` — đó là ngữ nghĩa PATCH của backend ("vắng mặt =
   * không đổi"). Gửi lại giá trị cũ cũng ra kết quả đúng trong phần lớn trường hợp, nhưng
   * nó biến một lượt sửa nghĩa thành một lượt ghi đè thẻ, và hai thiết bị sửa cùng lúc sẽ
   * xoá thay đổi của nhau.
   */
  async function saveDraft() {
    if (!draft || saving) return;
    const original = entries.find((e) => e.id === draft.id);
    if (!original) return;

    const meaningVi = draft.meaningVi.trim();
    if (!meaningVi) return;

    const nextTags = parseTags(draft.tags);
    const tagsChanged = nextTags.length !== original.tags.length
      || nextTags.some((t, i) => t !== original.tags[i]);

    setSaving(true);
    const response = await sendToBackground({
      type: 'UPDATE_VOCAB',
      id: draft.id,
      meaningVi: meaningVi === original.meaningVi ? null : meaningVi,
      tags: tagsChanged ? nextTags : null,
    });
    setSaving(false);

    if (!response.ok) {
      setError(response.error);
      return;
    }
    const updated = response.data;
    setDraft(null);
    // Hàng chip thì PHẢI nạp lại: lượt sửa vừa rồi có thể vừa tạo ra một chủ đề mới, vừa bỏ
    // trống một chủ đề cũ. Đây là chỗ duy nhất trong app đổi được `tags` của một từ đã lưu.
    void loadTags();

    // Đổi thẻ TRONG LÚC đang lọc: dòng vừa sửa có thể không còn thuộc bộ lọc hiện tại nữa.
    // Thay tại chỗ lúc đó để lại một dòng không khớp bộ lọc, và `total` đứng yên trong khi
    // hàng chip ngay phía trên đã tụt số — hai con số nói ngược nhau trên cùng màn hình.
    // Nạp lại là cách duy nhất biết dòng đó còn thuộc trang này không, vì điều kiện lọc
    // nằm ở backend.
    if (tagsChanged && (cursor.tag !== null || cursor.untagged)) {
      await load(cursor);
      return;
    }

    // Không lọc (hoặc chỉ sửa nghĩa) thì thay tại chỗ: người dùng vừa sửa xong một dòng và
    // đang nhìn đúng dòng đó — nạp lại là một nhịp nhấp nháy không đổi lấy gì.
    setEntries((list) => list.map((e) => (e.id === updated.id ? updated : e)));
  }

  /**
   * Tải CSV qua ĐÚNG đường xác thực rồi tự dựng file, thay vì `window.open` tới backend.
   *
   * Cách cũ luôn nhận 401: một lượt điều hướng không mang được token Bearer (extension) lẫn
   * header `X-IELTS-Web` (web), nên người dùng nhận về một trang JSON lỗi thay vì file.
   */
  async function openExport() {
    if (exporting) return;
    setExporting(true);
    const response = await sendToBackground({ type: 'EXPORT_VOCAB_CSV' });
    setExporting(false);

    if (!response.ok) {
      setError(response.error);
      return;
    }

    // BOM \uFEFF ở đầu: thiếu nó thì Excel trên Windows đọc UTF-8 thành Latin-1 và mọi dấu
    // tiếng Việt thành ký tự rác — sổ từ mở ra không đọc được.
    const blob = new Blob([`\uFEFF${response.data}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vocabulary.csv';
    a.click();
    // Thu hồi NGAY sau khi bấm: giữ lại là giữ nguyên nội dung sổ từ trong bộ nhớ tab cho
    // tới lúc đóng tab.
    URL.revokeObjectURL(url);
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
          onChange={(e) => setCursor((c) => ({ ...c, text: e.target.value, page: 0 }))}
        />
        <button
          type="button"
          disabled={exporting}
          aria-busy={exporting}
          onClick={() => void openExport()}
        >
          {exporting && <Spinner />}
          <span>CSV</span>
        </button>
      </div>

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

      {loading && (
        <p className="status" aria-live="polite">
          <Spinner /> Đang tải…
        </p>
      )}

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
            {entries.map((e) => {
              const progress = vocabProgress(e);
              const editing = draft?.id === e.id;
              return (
                <li key={e.id} className="vocab-item">
                  <div className="vocab-main">
                    <div className="vocab-head">
                      <strong>{e.term}</strong>
                      {e.pos && <span className="meta">{e.pos}</span>}
                    </div>

                    {editing ? (
                      <div className="vocab-edit">
                        <label htmlFor={`meaning-${e.id}`}>Nghĩa tiếng Việt</label>
                        <input
                          id={`meaning-${e.id}`}
                          type="text"
                          value={draft.meaningVi}
                          onChange={(ev) => setDraft({ ...draft, meaningVi: ev.target.value })}
                        />
                        <label htmlFor={`tags-${e.id}`}>Chủ đề (cách nhau bằng dấu phẩy)</label>
                        <input
                          id={`tags-${e.id}`}
                          type="text"
                          value={draft.tags}
                          onChange={(ev) => setDraft({ ...draft, tags: ev.target.value })}
                        />
                        <div className="vocab-edit-actions">
                          <button
                            type="button"
                            className="vocab-edit-save"
                            // Nghĩa rỗng bị backend trả 400 — chặn ở đây để khỏi tốn một
                            // vòng request cho một câu trả lời đã biết trước.
                            disabled={saving || draft.meaningVi.trim().length === 0}
                            aria-busy={saving}
                            onClick={() => void saveDraft()}
                          >
                            {saving && <Spinner />}
                            <span>Lưu</span>
                          </button>
                          <button type="button" onClick={() => setDraft(null)}>Huỷ</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="vi">{e.meaningVi}</p>
                        <div className="vocab-foot">
                          {e.tags.map((tag, i) => (
                            <span
                              key={tag}
                              className="vocab-tag"
                              data-tone={TOPIC_TONES[i % TOPIC_TONES.length]}
                            >
                              {tag}
                            </span>
                          ))}
                          {/* Thanh mang aria-hidden: chữ trạng thái ngay bên phải đã nói
                              đúng thông tin đó, đọc hai lần chỉ làm phiền. */}
                          <span className="mastery" aria-hidden="true">
                            {Array.from({ length: MASTERED_REPETITIONS }, (_, i) => (
                              <i
                                key={i}
                                data-on={i < progress.level ? '' : undefined}
                                data-lapsed={progress.lapsed ? '' : undefined}
                              />
                            ))}
                          </span>
                          <span className="vocab-status">{progress.label}</span>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="vocab-side">
                    {e.bandLevel && (
                      <span className="band" title={BAND_HINT}>{e.bandLevel}</span>
                    )}
                    {!editing && (
                      <button
                        type="button"
                        className="vocab-edit-open"
                        aria-label={`Sửa ${e.term}`}
                        onClick={() => setDraft({
                          id: e.id, meaningVi: e.meaningVi, tags: e.tags.join(', '),
                        })}
                      >
                        Sửa
                      </button>
                    )}
                    <button
                      type="button"
                      className="vocab-delete"
                      aria-label={`Xoá ${e.term}`}
                      disabled={deletingId !== null}
                      aria-busy={deletingId === e.id}
                      onClick={() => void remove(e.id)}
                    >
                      {deletingId === e.id ? <Spinner /> : '✕'}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {totalPages > 1 && (
        <nav className="vocab-pager" aria-label="Phân trang sổ từ">
          <button
            type="button"
            aria-label="Trang trước"
            disabled={loading || cursor.page === 0}
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
            disabled={loading || cursor.page >= totalPages - 1}
            onClick={() => goToPage(cursor.page + 1)}
          >
            ›
          </button>
        </nav>
      )}
    </div>
  );
}
