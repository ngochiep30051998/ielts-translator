import { useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type {
  AnswerResult, ApiError, QuizExplanation, QuizItemDto, QuizType,
} from '../shared/types';

/**
 * Giới hạn cứng độ dài câu trả lời, áp cho CẢ BA loại.
 *
 * Hằng song sinh phía backend là `QuizService.MAX_ANSWER_LENGTH` — cùng con số, cùng
 * ý nghĩa, backend ném TEXT_TOO_LONG khi vượt. Chặn sớm ở đây để khỏi tốn một vòng
 * request. Đổi một mình con số ở một trong hai chỗ là hỏng im lặng.
 */
const MAX_ANSWER_LENGTH = 1000;

const DEFAULT_COUNT = 10;
const MIN_COUNT = 1;
const MAX_COUNT = 50;

/**
 * Thứ tự CỐ ĐỊNH khi chia số câu cho các loại được tick, và cũng là thứ tự gửi
 * request. Cố định chứ không phải tuỳ hứng: nó làm việc chia câu tất định và test được.
 */
const TYPE_ORDER: { id: QuizType; label: string }[] = [
  { id: 'FILL_BLANK', label: 'Điền từ' },
  { id: 'COLLOCATION_CHOICE', label: 'Chọn cụm từ' },
  { id: 'FREE_WRITE', label: 'Tự viết câu' },
];

/**
 * Chia `total` câu cho `n` loại, phần dư dồn về các loại đầu.
 * total=10, n=3 → [4, 3, 3]. total=2, n=3 → [1, 1, 0].
 * Loại nhận 0 câu thì KHÔNG gửi request — một vòng gọi Gemini cho 0 câu là lãng phí thuần.
 */
function splitCount(total: number, n: number): number[] {
  const base = Math.floor(total / n);
  const remainder = total % n;
  return Array.from({ length: n }, (_, i) => base + (i < remainder ? 1 : 0));
}

/**
 * Gợi ý thêm sau thông điệp lỗi.
 *
 * `retryable` CHỈ dùng để chọn chữ, KHÔNG dùng để quyết định có hiện nút "Tạo đề"
 * hay không: `AppException.of()` phía backend chỉ đặt `retryable = true` cho đúng
 * GEMINI_UNAVAILABLE, nên PARSE_ERROR về tới đây với `retryable: false` dù bấm lại
 * rất có thể thành công (Gemini không tất định). Nút "Tạo đề" luôn bấm lại được.
 */
function hintFor(error: ApiError): string {
  return error.retryable
    ? 'Backend đang bận — thử lại sau ít giây.'
    : 'Bấm "Tạo đề" để thử lại; đề do AI sinh nên lần sau thường khác.';
}

export function QuizTab() {
  const [countText, setCountText] = useState(String(DEFAULT_COUNT));
  const [types, setTypes] = useState<QuizType[]>(TYPE_ORDER.map((t) => t.id));

  const [items, setItems] = useState<QuizItemDto[]>([]);
  const [results, setResults] = useState<(AnswerResult | null)[]>([]);
  const [index, setIndex] = useState(0);

  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  /** Đã chạy xong ít nhất một lượt tạo đề — để phân biệt "chưa bấm" với "bấm rồi mà rỗng". */
  const [generated, setGenerated] = useState(false);
  /** Loại nào sinh hụt trong lượt vừa rồi. Hỏng một phần thì vẫn cho làm phần đã có. */
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  const [draft, setDraft] = useState('');
  const [grading, setGrading] = useState(false);
  const [answerError, setAnswerError] = useState<ApiError | null>(null);

  /**
   * MỘT ô chứ không phải mảng song song với `results`: điều hướng chỉ đi tới — `next()`
   * không có đường lùi — nên không bao giờ quay lại câu cũ. `results` là mảng vì màn tổng
   * kết đếm số câu đúng; giải thích không vào tổng kết.
   */
  const [explanation, setExplanation] = useState<QuizExplanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<ApiError | null>(null);

  const count = Number.parseInt(countText, 10);
  const countValid = Number.isInteger(count) && count >= MIN_COUNT && count <= MAX_COUNT;
  const canGenerate = !generating && countValid && types.length > 0;

  /**
   * Chuỗi rỗng là câu trả lời HỢP LỆ, nghĩa là "bỏ qua câu này" — backend nhận
   * (`@NotNull` chứ không `@NotBlank`), chấm 0 và ghi `quiz_attempt` như một lượt làm
   * thật. Khoá nút Nộp khi ô trống làm người học không bỏ qua được câu nào, và câu đó
   * còn quay lại ở đề sau vì `findReusable` chỉ loại item ĐÃ có lượt làm.
   *
   * Nút chỉ khoá vì hai lý do: đang chấm, và vượt 1000 ký tự.
   */
  const tooLong = draft.length > MAX_ANSWER_LENGTH;
  const canSubmit = !grading && !tooLong;

  function toggleType(id: QuizType) {
    setTypes((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
  }

  async function generate() {
    if (!canGenerate) return;

    // Chỉ những loại được tick, theo ĐÚNG thứ tự TYPE_ORDER — không theo thứ tự người
    // dùng bấm chuột, nếu không số câu chia ra sẽ nhảy lung tung giữa hai lượt.
    const chosen = TYPE_ORDER.filter((t) => types.includes(t.id));
    const shares = splitCount(count, chosen.length);
    const jobs = chosen
      .map((t, i) => ({ type: t, share: shares[i] }))
      .filter((job) => job.share > 0);

    setGenerating(true);
    setGenerated(false);
    setError(null);
    setWarnings([]);
    setProgress({ done: 0, total: jobs.length });

    const collected: QuizItemDto[] = [];
    const failed: string[] = [];
    let lastError: ApiError | null = null;

    // TUẦN TỰ, không Promise.all: mỗi loại là một lô gọi Gemini trên cùng một API key,
    // và chạy lần lượt mới hiện được tiến độ thật cùng giữ được phần đã sinh xong.
    for (const job of jobs) {
      const response = await sendToBackground({
        type: 'GENERATE_QUIZ',
        vocabIds: null,
        count: job.share,
        quizType: job.type.id,
      });
      if (response.ok) {
        collected.push(...response.data);
      } else {
        lastError = response.error;
        failed.push(`${job.type.label}: ${response.error.message}`);
      }
      setProgress((p) => ({ ...p, done: p.done + 1 }));
    }

    setItems(collected);
    setResults(collected.map(() => null));
    setIndex(0);
    setDraft('');
    setAnswerError(null);
    setExplanation(null);
    setExplainError(null);
    // "Hỏng một phần" chỉ có nghĩa khi CÓ phần chạy được. Hỏng sạch thì nó là lỗi
    // chặn, và hiện kèm cảnh báo "một phần" vừa thừa vừa sai sự thật.
    setWarnings(collected.length > 0 ? failed : []);
    // Chỉ coi là lỗi chặn khi KHÔNG còn câu nào dùng được. Hỏng một phần vẫn cho làm bài.
    setError(collected.length === 0 ? lastError : null);
    setGenerated(true);
    setGenerating(false);
  }

  async function submit(answer: string) {
    const item = items[index];
    // Không chặn chuỗi rỗng: đó là "bỏ qua câu", một câu trả lời hợp lệ.
    if (!item || grading || answer.length > MAX_ANSWER_LENGTH) return;

    setGrading(true);
    setAnswerError(null);
    const response = await sendToBackground({
      type: 'ANSWER_QUIZ', quizItemId: item.id, answer,
    });
    setGrading(false);

    if (response.ok) {
      const data = response.data;
      setResults((prev) => prev.map((r, i) => (i === index ? data : r)));
    } else {
      setAnswerError(response.error);
    }
  }

  async function explain() {
    const item = items[index];
    if (!item || explaining) return;

    setExplaining(true);
    setExplainError(null);
    const response = await sendToBackground({ type: 'EXPLAIN_QUIZ', quizItemId: item.id });
    setExplaining(false);

    if (response.ok) {
      setExplanation(response.data);
    } else {
      setExplainError(response.error);
    }
  }

  function next() {
    setDraft('');
    setAnswerError(null);
    setExplanation(null);
    setExplainError(null);
    setIndex((i) => i + 1);
  }

  function reset() {
    setItems([]);
    setResults([]);
    setIndex(0);
    setDraft('');
    setGenerated(false);
    setWarnings([]);
    setError(null);
    setAnswerError(null);
    setExplanation(null);
    setExplainError(null);
  }

  const warningBlock = warnings.length > 0 && (
    <p className="status bad" role="status">
      Một phần đề không sinh được — {warnings.join('; ')}
    </p>
  );

  /* ---------- Màn chuẩn bị: chưa có câu nào dùng được ---------- */

  if (items.length === 0) {
    return (
      <div className="quiz-tab">
        {warningBlock}

        <div className="quiz-setup">
          <label htmlFor="quiz-count">Số câu</label>
          <input
            id="quiz-count"
            type="number"
            min={MIN_COUNT}
            max={MAX_COUNT}
            value={countText}
            disabled={generating}
            onChange={(e) => setCountText(e.target.value)}
          />

          <fieldset>
            <legend>Loại câu hỏi</legend>
            {TYPE_ORDER.map((t) => (
              <label key={t.id} className="quiz-type">
                <input
                  type="checkbox"
                  checked={types.includes(t.id)}
                  disabled={generating}
                  onChange={() => toggleType(t.id)}
                />
                {t.label}
              </label>
            ))}
          </fieldset>

          <button type="button" disabled={!canGenerate} onClick={() => void generate()}>
            Tạo đề
          </button>
        </div>

        {generating && (
          <p className="status">Đang sinh đề: {progress.done}/{progress.total}</p>
        )}

        {error && (
          <p className="status bad" role="alert">{error.message} {hintFor(error)}</p>
        )}

        {generated && !generating && !error && (
          <p className="empty">
            Chưa có từ nào đủ điều kiện — cần ôn ít nhất một lượt trước đã.
          </p>
        )}
      </div>
    );
  }

  /* ---------- Tổng kết ---------- */

  if (index >= items.length) {
    const correct = results.filter((r) => r?.correct).length;
    return (
      <div className="quiz-tab">
        {warningBlock}
        <div className="empty">
          <p>Đúng {correct}/{items.length}</p>
          <button type="button" onClick={reset}>Làm đề mới</button>
        </div>
      </div>
    );
  }

  /* ---------- Một câu hỏi ---------- */

  const item = items[index];
  const result = results[index];
  const answered = result !== null && result !== undefined;

  return (
    <div className="quiz-tab">
      {warningBlock}

      <p className="status">{index + 1}/{items.length}</p>

      <div className="quiz-card">
        {/* term là null với FILL_BLANK (nó chính là đáp án) — chỉ hiện khi backend có gửi. */}
        {item.term && <p className="quiz-term">{item.term}</p>}
        <p className="quiz-question">{item.question}</p>

        {item.type === 'FILL_BLANK' && (
          <>
            <p className="quiz-sentence">{item.sentence}</p>
            <input
              type="text"
              aria-label="Từ cần điền"
              value={draft}
              disabled={answered}
              onChange={(e) => setDraft(e.target.value)}
            />
          </>
        )}

        {item.type === 'COLLOCATION_CHOICE' && item.options && (
          <div className="quiz-options">
            {/*
              TUYỆT ĐỐI KHÔNG sort/shuffle mảng này. Backend đã xáo đúng một lần lúc lưu
              item, và câu trả lời gửi lên là index trong CHÍNH mảng đang render. Xáo lại
              ở đây làm mọi câu trắc nghiệm chấm sai mà không có lỗi nào nổ ra.
              (ReviewTab của Phase 2 tự xáo ở client vì backend gửi cả đáp án lẫn mồi
              nhử — đừng bê pattern đó sang đây.)
            */}
            {item.options.map((option, i) => (
              <button
                key={`${i}-${option}`}
                type="button"
                className="quiz-option"
                disabled={answered || grading}
                onClick={() => void submit(String(i))}
              >
                {i + 1}. {option}
              </button>
            ))}
          </div>
        )}

        {item.type === 'FREE_WRITE' && (
          <>
            <textarea
              aria-label="Câu tiếng Anh của bạn"
              rows={4}
              value={draft}
              disabled={answered}
              onChange={(e) => setDraft(e.target.value)}
            />
            {/* Không dùng maxLength: cắt cụt im lặng thì người dùng không hiểu vì sao mất chữ. */}
            <p className={tooLong ? 'quiz-counter over' : 'quiz-counter'}>
              {draft.length}/{MAX_ANSWER_LENGTH}
            </p>
          </>
        )}

        {item.type !== 'COLLOCATION_CHOICE' && !answered && (
          <button
            type="button"
            className="quiz-submit"
            disabled={!canSubmit}
            onClick={() => void submit(draft.trim())}
          >
            Nộp
          </button>
        )}

        {/*
          COLLOCATION_CHOICE không có ô nhập nên cũng không có nút "Nộp" — thiếu nút này
          thì cách duy nhất đi tiếp là đoán bừa, mà đoán bừa ghi một quiz_attempt rác và
          làm bẩn luôn tiêu chí xếp ưu tiên ứng viên cho đề sau (ưu tiên từ ít lượt làm
          nhất). Backend đã nhận chuỗi rỗng cho cả ba loại, không cần đổi gì phía server.
        */}
        {item.type === 'COLLOCATION_CHOICE' && !answered && (
          <button
            type="button"
            className="quiz-skip"
            disabled={grading}
            onClick={() => void submit('')}
          >
            Bỏ qua
          </button>
        )}

        {grading && <p className="status">Đang chấm…</p>}

        {answerError && (
          <p className="status bad" role="alert">
            {/*
              Chữ phải rẽ theo loại: nút "Nộp" chỉ tồn tại khi type !== COLLOCATION_CHOICE.
              Bảo người dùng bấm một nút không có trên màn hình là chỉ sai đường hồi phục.
            */}
            {answerError.message}{' '}
            {item.type === 'COLLOCATION_CHOICE'
              ? 'Chọn lại một đáp án để gửi lại.'
              : 'Bấm "Nộp" để gửi lại.'}
          </p>
        )}
      </div>

      {answered && (
        <div className={result.correct ? 'quiz-result ok' : 'quiz-result bad'}>
          <p className="quiz-verdict">
            {result.correct ? '✓ Đúng' : '✗ Chưa đúng'} · {result.score} điểm
          </p>
          {/* Khi sai, feedback CHỨA LUÔN đáp án đúng — QuizItemDto không mang nó. */}
          <p className="quiz-feedback">{result.feedback}</p>

          {/*
            improvedVersion null nghĩa là "loại này không có khái niệm câu viết lại",
            không phải "chưa chấm xong" — không render khối này.
          */}
          {result.improvedVersion && (
            <div className="quiz-improved">
              <h3>Câu viết lại</h3>
              <p>{result.improvedVersion}</p>
            </div>
          )}

          {!explanation && (
            <button
              type="button"
              className="quiz-explain"
              disabled={explaining}
              onClick={() => void explain()}
            >
              {explaining ? 'Đang giải thích…' : 'Giải thích'}
            </button>
          )}

          {explainError && (
            <p className="status bad" role="alert">
              {explainError.message} Bấm "Giải thích" để thử lại.
            </p>
          )}

          {explanation && (
            <div className="quiz-explanation">
              <h3>Giải thích</h3>
              <p>{explanation.explanation}</p>

              <h3>Nghĩa đáp án</h3>
              <p>{explanation.answerMeaning}</p>

              {/*
                sentenceEn và sentenceVi là MỘT CẶP — backend không bao giờ gửi một nửa.
                Kiểm cả hai vừa để TypeScript hẹp được kiểu, vừa để một nửa lọt qua (nếu
                hợp đồng vỡ) không render ra một khối trống.
              */}
              {explanation.sentenceEn && explanation.sentenceVi && (
                <>
                  <h3>Dịch câu</h3>
                  <p className="quiz-sentence-en">{explanation.sentenceEn}</p>
                  <p>{explanation.sentenceVi}</p>
                </>
              )}
            </div>
          )}

          {/*
            Khoá nút Tiếp trong lúc đang giải thích. Không khoá thì bấm Tiếp khi request
            đang bay sẽ làm response về muộn ghi giải thích của câu cũ lên câu mới — sai
            câu, và không có lỗi nào nổ ra. Người vừa bấm "Giải thích" là người đang muốn
            đọc, nên chờ một hai giây không mất gì; response lỗi cũng kết thúc `explaining`
            nên không có đường kẹt vĩnh viễn.
          */}
          <button
            type="button"
            className="quiz-next"
            disabled={explaining}
            onClick={next}
          >
            {index + 1 < items.length ? 'Tiếp' : 'Xem kết quả'}
          </button>
        </div>
      )}
    </div>
  );
}
