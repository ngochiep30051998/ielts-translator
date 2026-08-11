import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { sendToBackground } from '../shared/messages';
import { loadSettings } from '../shared/settings';
import { speak } from '../shared/speech';
import { buildQuestion, ratingFor, type Question } from '../shared/mcq';
import type { ApiError, Rating } from '../shared/types';

const QUEUE_LIMIT = 50;

type Mode = 'scheduled' | 'practice';

/** Số thẻ xen vào trước khi thẻ vừa quên hiện lại. Tương đương "learning step" của Anki,
 *  nhưng đo bằng số thẻ chứ không bằng phút — panel không có lịch trong ngày. */
const RELEARN_GAP = 3;
const PRACTICE_LIMIT = 30;

export function ReviewTab() {
  // Dựng câu hỏi MỘT LẦN lúc nạp hàng đợi, không phải useMemo: useMemo là gợi ý hiệu năng,
  // React được phép vứt cache. Vứt cache ở đây nghĩa là trộn lại đáp án giữa lúc người dùng
  // đang nhìn câu hỏi, correctIndex trỏ chỗ khác, bấm đúng bị chấm sai rồi ghi vào review_log.
  const [questions, setQuestions] = useState<Question[]>([]);
  // Giữ lại số thẻ backend trả về để phân biệt "hết bài" với "có thẻ nhưng chưa dựng được câu".
  const [queueSize, setQueueSize] = useState(0);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  // Mức vừa chấm, để nút Thử lại gửi lại ĐÚNG mức đó chứ không đoán bừa.
  const [lastRating, setLastRating] = useState<Rating | null>(null);
  // Mốc bắt đầu tính giờ, đặt lại mỗi khi câu hỏi đổi.
  const startedAt = useRef(Date.now());
  const container = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>('scheduled');
  // Thẻ đã gửi một lượt SCHEDULED trong buổi này. Dùng ref chứ không state: giá trị này
  // không ảnh hưởng render, và đọc nó trong handler phải luôn thấy giá trị mới nhất.
  const scheduledSent = useRef<Set<number>>(new Set());

  const load = useCallback(async (nextMode: Mode = 'scheduled') => {
    setLoading(true);
    scheduledSent.current = new Set();
    const response = nextMode === 'practice'
      ? await sendToBackground({ type: 'GET_PRACTICE_CARDS', limit: PRACTICE_LIMIT })
      : await sendToBackground({
          type: 'GET_DUE_CARDS',
          limit: QUEUE_LIMIT,
          newLimit: (await loadSettings()).newWordsPerDay,
        });
    if (response.ok) {
      const cards = response.data;
      setQueueSize(cards.length);
      // pool là `cards` — mảng VỪA nhận — chứ không phải state cũ, vốn còn là giá trị của
      // lần render trước; dùng state ở đây là bù mồi nhử bằng xấp thẻ cũ.
      //
      // Thẻ nào không dựng được câu hỏi thì bị loại hẳn khỏi danh sách và bỏ qua —
      // chưa ôn thì không được đổi lịch, nên cũng không gửi SUBMIT_REVIEW.
      setQuestions(
        cards
          .map((card) => buildQuestion(card, cards, Math.random))
          .filter((q): q is Question => q !== null),
      );
      setIndex(0);
      setPicked(null);
      setError(null);
    } else {
      setError(response.error);
    }
    setMode(nextMode);
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const question = questions[index];

  useEffect(() => { startedAt.current = Date.now(); }, [index]);

  // Phím tắt chỉ chạy khi div đang giữ focus. Bấm chuột vào một lựa chọn đẩy focus sang
  // nút đó, mà nút bị khoá ngay sau đấy nên focus rơi về body — phải kéo focus về đây,
  // nếu không phím Enter để sang thẻ sau sẽ không ăn.
  useEffect(() => { container.current?.focus(); }, [index, picked]);

  async function submit(rating: Rating, cardId: number) {
    setLastRating(rating);
    setSubmitting(true);

    // Mỗi thẻ đóng góp NHIỀU NHẤT MỘT lượt SCHEDULED trong một buổi. Mọi lần hiện lại đều là
    // PRACTICE.
    //
    // Lượt đầu đã kéo lịch về gần — đúng, đó là một lần quên. Nếu lượt thứ hai cũng gửi
    // SUBMIT_REVIEW, nó tính tiếp từ trạng thái vừa lapse và đẩy interval lên lại, tức là trả
    // lời đúng ở lần thứ hai xoá mất dấu vết đã quên.
    const laLuotOnDauTien = mode === 'scheduled' && !scheduledSent.current.has(cardId);

    const response = laLuotOnDauTien
      ? await sendToBackground({ type: 'SUBMIT_REVIEW', cardId, rating })
      : await sendToBackground({ type: 'SUBMIT_PRACTICE', cardId, rating });

    if (laLuotOnDauTien) scheduledSent.current.add(cardId);

    setSubmitting(false);
    setError(response.ok ? null : response.error);
  }

  async function choose(optionIndex: number) {
    if (!question || picked !== null || submitting) return;

    setPicked(optionIndex);
    const correct = optionIndex === question.correctIndex;
    await submit(ratingFor(correct, Date.now() - startedAt.current), question.card.id);

    // Trả lời sai thì chèn lại thẻ để hiện lại trong CÙNG buổi, thay vì phải đợi lịch SM-2
    // ngày mai. Chèn xen RELEARN_GAP thẻ khác ở giữa để không lặp lại ngay tức thì.
    if (!correct) {
      setQuestions((qs) => {
        const at = Math.min(index + 1 + RELEARN_GAP, qs.length);
        const next = [...qs];
        next.splice(at, 0, question);
        return next;
      });
    }
  }

  function next() {
    setPicked(null);
    setError(null);
    setIndex((i) => i + 1);
  }

  async function speakTerm() {
    if (!question) return;
    const { voiceName } = await loadSettings();
    speak(question.card.term, voiceName);
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!question) return;
    if (picked === null) {
      const n = Number(event.key);
      if (Number.isInteger(n) && n >= 1 && n <= question.options.length) {
        void choose(n - 1);
      }
      return;
    }
    if (event.key === 'Enter') next();
  }

  if (loading) return <p className="status">Đang tải…</p>;

  if (error && !question) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && <button type="button" onClick={() => void load()}>Thử lại</button>}
      </div>
    );
  }

  if (!question) {
    const blocked = queueSize > 0 && questions.length === 0;
    return (
      <div className="empty">
        <p>
          {blocked
            ? 'Chưa tạo được câu hỏi — mồi nhử đang được sinh, thử lại sau ít phút.'
            : 'Hôm nay không còn thẻ nào đến hạn.'}
        </p>
        <button type="button" onClick={() => void load()}>Tải lại</button>
        <button type="button" onClick={() => void load('practice')}>Luyện thêm</button>
      </div>
    );
  }

  const card = question.card;

  return (
    // tabIndex để div nhận được phím tắt mà không cần bắt sự kiện toàn cục
    <div className="review-tab" ref={container} tabIndex={-1} onKeyDown={onKeyDown}>
      {mode === 'practice' && (
        <div className="practice-banner">
          <span>Luyện thêm — không ảnh hưởng lịch ôn</span>
          <button type="button" onClick={() => void load('scheduled')}>Quay lại</button>
        </div>
      )}

      {/* Thanh tiến độ mang aria-hidden: số đếm ngay bên cạnh đã nói đúng thông tin đó,
          đọc hai lần chỉ làm phiền người dùng trình đọc màn hình. */}
      <div className="progress-row">
        <div className="progress-track" aria-hidden="true">
          <div
            className="progress-fill"
            style={{ width: `${((index + 1) / questions.length) * 100}%` }}
          />
        </div>
        <p className="status">{index + 1}/{questions.length}</p>
      </div>

      {error && lastRating && (
        <p className="status bad" role="alert">
          {error.message}{' '}
          {error.retryable && (
            <button
              type="button"
              disabled={submitting}
              onClick={() => void submit(lastRating, card.id)}
            >
              Thử lại
            </button>
          )}
        </p>
      )}

      <div className="review-card">
        <div className="review-front">
          {question.direction === 'EN_VI' ? (
            <>
              <strong>{card.term}</strong>
              {card.ipa && <span className="meta">{card.ipa}</span>}
              <button
                type="button"
                aria-label={`Phát âm ${card.term}`}
                onClick={() => void speakTerm()}
              >
                🔊
              </button>
            </>
          ) : (
            <strong>{card.meaningVi}</strong>
          )}
        </div>
      </div>

      <div className="review-options">
        {question.options.map((option, i) => {
          const state = optionState(i, picked, question.correctIndex);
          return (
            <button
              key={option}
              type="button"
              disabled={picked !== null}
              className={state ? `review-option ${state}` : 'review-option'}
              onClick={() => void choose(i)}
            >
              {/* Số thứ tự CHÍNH LÀ phím tắt của ô này — vẽ như một phím để người dùng
                  thấy có đường tắt, thay vì giấu nó trong câu trả lời. */}
              <span className="option-key">{i + 1}</span>
              <span className="option-text">{option}</span>
              {state && (
                <>
                  {/* Dấu để mắt bắt được trạng thái mà không cần phân biệt đỏ với xanh lá,
                      kèm chữ cho trình đọc màn hình vì màu không nói được gì với nó. */}
                  <span className="option-mark" aria-hidden="true">
                    {state === 'correct' ? '✓' : '✗'}
                  </span>
                  <span className="sr-only">
                    {state === 'correct' ? 'Đáp án đúng' : 'Bạn chọn ô này, sai'}
                  </span>
                </>
              )}
            </button>
          );
        })}
      </div>

      {picked === null && (
        <p className="review-hint">
          Bấm <kbd>1</kbd>–<kbd>{question.options.length}</kbd> để chọn nhanh
        </p>
      )}

      {picked !== null && (
        <>
          <div className="review-back">
            {/* Hai dòng chứ không nối bằng gạch ngang: đây là hai trường dữ liệu khác
                nhau, xếp chồng thì mắt tách được ngay mà không phải đọc qua dấu nối. */}
            <p className="review-back-term">{card.term}</p>
            <p className="vi">{card.meaningVi}</p>
            {card.pos && <span className="meta">{card.pos}</span>}
            {card.cefr && <span className="meta">{card.cefr}</span>}
            {card.bandLevel && (
              <span className="band" title="Band do AI ước lượng, chỉ mang tính tham khảo">
                {card.bandLevel}
              </span>
            )}
            {card.definitionEn && <p className="review-definition">{card.definitionEn}</p>}
          </div>
          {/* Lỗi chưa xử lý xong thì KHÔNG cho đi tiếp — bỏ qua lúc này là mất luôn lượt chấm. */}
          {!error && (
            <button type="button" className="review-next" onClick={next}>Tiếp</button>
          )}
        </>
      )}
    </div>
  );
}

/** Chỉ tô màu sau khi đã chọn: đáp án đúng luôn xanh, ô chọn sai thì đỏ. */
function optionState(
  index: number,
  picked: number | null,
  correctIndex: number,
): 'correct' | 'wrong' | null {
  if (picked === null) return null;
  if (index === correctIndex) return 'correct';
  if (index === picked) return 'wrong';
  return null;
}
