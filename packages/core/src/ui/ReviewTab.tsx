import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { sendToBackground } from '../messages';
import { loadSettings } from '../settings';
import { speak } from '../speech';
import { buildQuestion, ratingFor, type Question } from '../mcq';
import type { ApiError, Rating } from '../types';
import { Spinner } from './Spinner';

const QUEUE_LIMIT = 50;

type Mode = 'scheduled' | 'practice';

/** Số thẻ xen vào trước khi thẻ vừa quên hiện lại. Tương đương "learning step" của Anki,
 *  nhưng đo bằng số thẻ chứ không bằng phút — panel không có lịch trong ngày. */
const RELEARN_GAP = 3;
const PRACTICE_LIMIT = 30;

const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

/**
 * Điểm cơ bản của một câu đúng, và bậc thưởng theo combo.
 *
 * Đây là CON SỐ ĐỘNG VIÊN của một buổi, không phải điểm số học thuật: nó sống trong
 * component, mất khi đóng panel, và KHÔNG bao giờ được gửi xuống backend. Lưu nó xuống là
 * thêm một cột phải migrate cho một dòng chữ mà chính thiết kế muốn nó phù du.
 */
const POINT_BASE = 1;
/** Cứ mỗi `COMBO_STEP` câu đúng liên tiếp thì thưởng thêm 1 điểm. */
const COMBO_STEP = 3;
/** Trần thưởng — không có trần thì một buổi 50 thẻ kết thúc bằng những con số vô nghĩa. */
const MAX_BONUS = 4;

/** Mốc "nhanh"/"chắc tay" của nhận xét tốc độ, khớp thang mức SM-2 ở `mcq.ts`. */
const FAST_UNDER_MS = 5_000;
const STEADY_UNDER_MS = 15_000;

function pointsFor(combo: number): number {
  return POINT_BASE + Math.min(Math.floor(combo / COMBO_STEP), MAX_BONUS);
}

/** "2,1 giây" — dấu phẩy thập phân, đúng cách viết số tiếng Việt. */
function formatSeconds(elapsedMs: number): string {
  return `${(elapsedMs / 1000).toFixed(1).replace('.', ',')} giây`;
}

function speedLabel(correct: boolean, elapsedMs: number): string {
  if (!correct) return `Chưa đúng — ${formatSeconds(elapsedMs)}`;
  if (elapsedMs < FAST_UNDER_MS) return `Nhanh gọn — ${formatSeconds(elapsedMs)}`;
  if (elapsedMs < STEADY_UNDER_MS) return `Chắc tay — ${formatSeconds(elapsedMs)}`;
  return `Đúng rồi — ${formatSeconds(elapsedMs)}`;
}

/** Kết quả của lượt chấm vừa xong. `null` = chưa chấm câu nào trên thẻ đang hiện. */
interface Scored {
  correct: boolean;
  elapsedMs: number;
  /** Điểm của riêng câu này. 0 khi sai. */
  gain: number;
  /** Combo SAU câu này — 0 nếu vừa trả lời sai. */
  combo: number;
}

/** Nhãn hướng hỏi, in nhỏ ở đỉnh mặt thẻ. */
const DIRECTION_LABEL: Record<Question['direction'], string> = {
  EN_VI: 'Anh → Việt',
  VI_EN: 'Việt → Anh',
};

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
  /**
   * Số ngày tới lần ôn sau, lấy từ phản hồi SUBMIT_REVIEW của CHÍNH thẻ đang hiện.
   *
   * `null` = không có con số nào để nói: lượt luyện thêm (SUBMIT_PRACTICE trả 204, và luyện
   * thêm cố ý không đụng lịch), hoặc chưa chấm xong. Bịa ra một số ở hai ca đó là nói với
   * người dùng rằng lịch vừa bị dời trong khi nó đứng yên.
   */
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  /**
   * Combo và điểm — trạng thái của MỘT buổi, không lưu ở đâu cả.
   *
   * `combo` sống qua nhiều thẻ nên nằm riêng; `scored` chỉ mô tả thẻ đang hiện và bị xoá
   * mỗi lần sang thẻ mới, y như `nextInterval`.
   */
  const [combo, setCombo] = useState(0);
  const [scored, setScored] = useState<Scored | null>(null);
  // Mốc bắt đầu tính giờ, đặt lại mỗi khi câu hỏi đổi.
  const startedAt = useRef(Date.now());
  const container = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>('scheduled');
  // Thẻ đã gửi một lượt SCHEDULED trong buổi này. Dùng ref chứ không state: giá trị này
  // không ảnh hưởng render, và đọc nó trong handler phải luôn thấy giá trị mới nhất.
  const scheduledSent = useRef<Set<number>>(new Set());

  const load = useCallback(async (nextMode: Mode = 'scheduled') => {
    setLoading(true);
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
      setNextInterval(null);
      // Nạp xấp mới = buổi mới. Giữ combo của buổi trước là nói dối: chuỗi đúng liên tiếp
      // đó thuộc về một xấp thẻ khác.
      setCombo(0);
      setScored(null);
      // `questions`, `mode` và `scheduledSent` phải đổi CÙNG NHAU, chỉ khi nạp THÀNH CÔNG.
      // Nạp lỗi (vd bấm "Quay lại" mà GET_DUE_CARDS rớt mạng) phải giữ nguyên cả ba — đổi
      // `mode` một mình trong khi xấp thẻ vẫn là xấp cũ làm `submit()` tính sai thẻ đang ôn
      // là thẻ lịch, bắn nhầm SUBMIT_REVIEW cho thẻ luyện.
      setMode(nextMode);
      scheduledSent.current = new Set();
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

    // Mỗi thẻ đóng góp NHIỀU NHẤT MỘT lượt SCHEDULED trong một buổi. Mọi lần hiện lại đều là
    // PRACTICE.
    //
    // Lượt đầu đã kéo lịch về gần — đúng, đó là một lần quên. Nếu lượt thứ hai cũng gửi
    // SUBMIT_REVIEW, nó tính tiếp từ trạng thái vừa lapse và đẩy interval lên lại, tức là trả
    // lời đúng ở lần thứ hai xoá mất dấu vết đã quên.
    const laLuotOnDauTien = mode === 'scheduled' && !scheduledSent.current.has(cardId);

    // Hai nhánh viết tách nhau chứ không gộp bằng toán tử ba ngôi: chỉ SUBMIT_REVIEW mới có
    // `intervalDays` trong phản hồi, và gộp lại thì kiểu trả về là hợp của hai hình dạng,
    // không đọc được field nào cả.
    if (laLuotOnDauTien) {
      const response = await sendToBackground({ type: 'SUBMIT_REVIEW', cardId, rating });
      // Chỉ đánh dấu khi lượt SCHEDULED THẬT SỰ tới nơi. Đánh dấu vô điều kiện làm nút "Thử
      // lại" gửi SUBMIT_PRACTICE thay vì gửi lại SUBMIT_REVIEW — lịch SM-2 của thẻ đó im
      // lặng không bao giờ được cập nhật trong buổi ấy.
      if (response.ok) {
        scheduledSent.current.add(cardId);
        setNextInterval(response.data.intervalDays);
      }
      setSubmitting(false);
      setError(response.ok ? null : response.error);
      return;
    }

    const response = await sendToBackground({ type: 'SUBMIT_PRACTICE', cardId, rating });
    setSubmitting(false);
    setError(response.ok ? null : response.error);
  }

  async function choose(optionIndex: number) {
    if (!question || picked !== null || submitting) return;

    setPicked(optionIndex);
    const correct = optionIndex === question.correctIndex;
    const elapsedMs = Date.now() - startedAt.current;

    // Combo tính TRƯỚC khi gửi: nó là phản hồi tức thì cho cú bấm vừa rồi, không phụ thuộc
    // vào việc backend có nhận được lượt chấm hay không.
    const nextCombo = correct ? combo + 1 : 0;
    setCombo(nextCombo);
    setScored({ correct, elapsedMs, combo: nextCombo, gain: correct ? pointsFor(nextCombo) : 0 });

    await submit(ratingFor(correct, elapsedMs), question.card.id);

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
    // Giữ lại con số của thẻ vừa xong là gán lịch của nó cho thẻ đang hiện — sai dữ liệu,
    // không phải một chi tiết hiển thị. Dải điểm cũng vậy: nó nói về câu vừa rồi.
    setNextInterval(null);
    setScored(null);
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

  if (loading) return <p className="status" aria-live="polite"><Spinner /> Đang tải…</p>;

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
    const isPractice = mode === 'practice';
    return (
      <div className="empty">
        <p>
          {blocked
            ? 'Chưa tạo được câu hỏi — mồi nhử đang được sinh, thử lại sau ít phút.'
            : isPractice
              // Chế độ luyện không có "hạn" — chữ "đến hạn" ở đây là ngôn ngữ của chế độ
              // theo lịch, dùng nhầm sẽ khiến người dùng tưởng mình đang ôn theo lịch.
              ? 'Không còn từ nào để luyện thêm lúc này.'
              : 'Hôm nay không còn thẻ nào đến hạn.'}
        </p>
        {/* Nạp lại ĐÚNG chế độ hiện tại — `load(mode)` chứ không phải `load()` mặc định
            'scheduled', nếu không nút này âm thầm đưa người dùng ra khỏi chế độ luyện. */}
        <button type="button" onClick={() => void load(mode)}>Tải lại</button>
        {isPractice ? (
          <button type="button" onClick={() => void load('scheduled')}>Quay lại</button>
        ) : (
          <button type="button" onClick={() => void load('practice')}>Luyện thêm</button>
        )}
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
        {/* Chip chỉ hiện khi đang có chuỗi. "Combo 0" là một huy hiệu nói rằng bạn đang
            không có gì — nhiễu chứ không động viên. */}
        {combo > 0 && <span className="combo-chip">Combo {combo}</span>}
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
        {/* Nhãn hướng: cùng một thẻ hỏi hai chiều khác nhau tuỳ lượt bốc, và không có dòng
            này thì người dùng phải tự đoán mình đang được hỏi gì. */}
        <p className="review-direction">{DIRECTION_LABEL[question.direction]}</p>
        <div className="review-front">
          {question.direction === 'EN_VI' ? (
            <>
              <strong>{card.term}</strong>
              <span className="review-ipa-row">
                {card.ipa && <span className="meta">{card.ipa}</span>}
                <button
                  type="button"
                  aria-label={`Phát âm ${card.term}`}
                  onClick={() => void speakTerm()}
                >
                  🔊
                </button>
              </span>
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
            {/* Từ và các nhãn phân loại nằm CÙNG một dòng chân chữ; nghĩa tiếng Việt xuống
                dòng riêng. Ba nhóm dữ liệu, hai tầng — mắt tách được mà không cần dấu nối. */}
            <div className="review-back-head">
              <span className="review-back-term">{card.term}</span>
              <span className="meta">
                {card.pos}
                {card.pos && card.cefr && ' · '}
                {card.cefr}
                {(card.pos || card.cefr) && card.bandLevel && ' · '}
                {card.bandLevel && (
                  <span className="band-inline" title={BAND_HINT}>band {card.bandLevel}</span>
                )}
              </span>
            </div>
            <p className="vi">{card.meaningVi}</p>
            {card.definitionEn && <p className="review-definition">{card.definitionEn}</p>}
          </div>

          {/* Dải điểm: nhận xét tốc độ, chuyện xảy ra với lịch và combo, rồi điểm câu này.
              Cả ba đều là chuyện của CÂU VỪA RỒI nên chúng biến mất khi sang thẻ sau. */}
          {scored && (
            <div className="review-score">
              <div className="review-score-text">
                <p className="review-speed">{speedLabel(scored.correct, scored.elapsedMs)}</p>
                <p className="review-score-note">
                  {nextInterval !== null && (
                    <>
                      <span>Lần ôn sau:</span>{' '}
                      <span className="review-interval">{nextInterval} ngày</span>
                      {' · '}
                    </>
                  )}
                  {/* Không có `nextInterval` (lượt luyện thêm, hoặc lượt chấm vừa lỗi) thì
                      KHÔNG bịa ra một con số ngày — lịch của thẻ đó đang đứng yên. */}
                  {scored.correct
                    ? `combo lên ${scored.combo}`
                    : 'thẻ này sẽ quay lại · combo về 0'}
                </p>
              </div>
              <span className="review-gain">+{scored.gain}</span>
            </div>
          )}

          {/* Lỗi chưa xử lý xong thì KHÔNG cho đi tiếp — bỏ qua lúc này là mất luôn lượt chấm. */}
          {!error && (
            <button type="button" className="review-next" onClick={next}>
              Tiếp
              {/* Gợi ý phím tắt, KHÔNG phải một phần tên nút — aria-hidden để tên có thể
                  truy cập của nút vẫn đúng là "Tiếp". */}
              <span className="review-next-key" aria-hidden="true">Enter</span>
            </button>
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
