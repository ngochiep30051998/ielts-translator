import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { sendToBackground } from '../shared/messages';
import { loadSettings } from '../shared/settings';
import { speak } from '../shared/speech';
import { buildQuestion, ratingFor, type Question } from '../shared/mcq';
import type { ApiError, Rating } from '../shared/types';

const QUEUE_LIMIT = 50;

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

  const load = useCallback(async () => {
    setLoading(true);
    const { newWordsPerDay } = await loadSettings();
    const response = await sendToBackground({
      type: 'GET_DUE_CARDS', limit: QUEUE_LIMIT, newLimit: newWordsPerDay,
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
    const response = await sendToBackground({ type: 'SUBMIT_REVIEW', cardId, rating });
    setSubmitting(false);
    setError(response.ok ? null : response.error);
  }

  async function choose(optionIndex: number) {
    if (!question || picked !== null || submitting) return;

    setPicked(optionIndex);
    const correct = optionIndex === question.correctIndex;
    await submit(ratingFor(correct, Date.now() - startedAt.current), question.card.id);
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
      </div>
    );
  }

  const card = question.card;

  return (
    // tabIndex để div nhận được phím tắt mà không cần bắt sự kiện toàn cục
    <div className="review-tab" ref={container} tabIndex={-1} onKeyDown={onKeyDown}>
      <p className="status">{index + 1}/{questions.length}</p>

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
        {question.options.map((option, i) => (
          <button
            key={option}
            type="button"
            disabled={picked !== null}
            className={optionClass(i, picked, question.correctIndex)}
            onClick={() => void choose(i)}
          >
            {i + 1}. {option}
          </button>
        ))}
      </div>

      {picked !== null && (
        <>
          <div className="review-back">
            <p className="vi">{card.term} — {card.meaningVi}</p>
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
function optionClass(index: number, picked: number | null, correctIndex: number): string {
  if (picked === null) return 'review-option';
  if (index === correctIndex) return 'review-option correct';
  if (index === picked) return 'review-option wrong';
  return 'review-option';
}
