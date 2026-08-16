export type Direction = 'EN_VI' | 'VI_EN';
export type Mode = 'WORD' | 'SENTENCE';

export interface EnViWordPayload {
  term: string;
  lemma: string;
  pos: string;
  ipa: string;
  meaning_vi: string;
  definition_en: string;
  cefr: string;
  band_level: string;
  register: string;
  collocations: string[];
  examples: { en: string; vi: string }[];
  synonyms: { term: string; band: string }[];
}

export interface EnViSentencePayload {
  translation_vi: string;
  key_vocab: { term: string; meaning_vi: string; band_level: string }[];
  structure_note: string;
}

export interface ViEnWordPayload {
  best_en: string;
  alternatives: { term: string; band: string; register: string; when_to_use: string }[];
  collocations: string[];
  examples: string[];
}

export interface ViEnSentencePayload {
  band65_version: string;
  why_notes: string[];
  key_phrases: string[];
  avoid: { phrase: string; reason: string }[];
}

export type TranslatePayload =
  | EnViWordPayload
  | EnViSentencePayload
  | ViEnWordPayload
  | ViEnSentencePayload;

export interface TranslateResult {
  direction: Direction;
  mode: Mode;
  cached: boolean;
  payload: TranslatePayload;
  /** Text người dùng đã bôi đen — backend không trả, client tự gắn vào. */
  sourceText: string;
  sourceUrl?: string;
  sourceSentence?: string;
}

export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface VocabEntryDto {
  id: number;
  term: string;
  lemma: string | null;
  lang: string;
  pos: string;
  ipa: string | null;
  meaningVi: string;
  definitionEn: string | null;
  cefr: string | null;
  bandLevel: string | null;
  tags: string[];
  sourceUrl: string | null;
  sourceSentence: string | null;
  collocations: unknown;
  examples: unknown;
  createdAt: string;
  /**
   * Ba field dưới đến từ `srs_card` qua LEFT JOIN, KHÔNG từ `vocab_entry`.
   *
   * CẢ BA CÙNG null khi từ chưa có thẻ ôn — đó là "chưa vào lịch ôn", KHÔNG phải "chưa
   * tải xong". UI phải phân biệt được hai chuyện đó, nếu không một từ mới lưu sẽ trông
   * y hệt một dòng đang loading.
   */
  srsState: CardState | null;
  /** "YYYY-MM-DD" theo múi giờ server. */
  srsDueDate: string | null;
  srsRepetitions: number | null;
}

/**
 * Một chủ đề trong sổ từ kèm số từ đang gắn — nguồn của hàng chip lọc ở tab Sổ từ.
 *
 * Backend sắp `count DESC, tag ASC`; thứ tự đó là hợp đồng chứ không phải tình cờ, nên
 * client KHÔNG sắp lại.
 */
export interface VocabTag {
  tag: string;
  count: number;
  /**
   * Số từ mang chủ đề này đã đạt ngưỡng thuộc — thẻ ôn có `repetitions >= 5`.
   *
   * Ngưỡng 5 đó là `MASTERED_REPETITIONS` trong `vocab-progress.ts`; backend giữ đúng cùng
   * con số. Hai bên lệch nhau thì thanh thành thạo của một chủ đề nói khác thanh của từng
   * từ trong chính chủ đề đó, ngay cạnh nhau trên một màn hình.
   *
   * Backend chỉ trả SỐ ĐẾM, phần trăm do frontend tính (`topicMastery` trong `today.ts`) —
   * trả sẵn % là khoá cứng cách làm tròn vào API.
   */
  mastered: number;
}

/**
 * Toàn bộ dữ liệu của hàng chip lọc, lấy trong ĐÚNG MỘT lượt gọi `GET /api/vocab/tags`.
 *
 * `total` KHÔNG lọc gì — nó là con số của chip "Tất cả", tức đường về. Lấy nó từ
 * `totalElements` của lượt tìm kiếm đang lọc sẽ biến chip đó thành bản sao con số của chủ
 * đề vừa bấm, và người dùng mất luôn tham chiếu "cả sổ có bao nhiêu từ".
 *
 * `untagged` đi cùng ở đây chứ không phải một request riêng: hàng chip là MỘT đơn vị hiển
 * thị, ghép nó từ hai lượt gọi là mở đường cho hai nửa lệch nhau trên màn hình.
 */
export interface VocabTagsResponse {
  total: number;
  /** Số từ có `tags` là mảng RỖNG. Chip "Chưa gắn" chỉ hiện khi số này > 0. */
  untagged: number;
  tags: VocabTag[];
}

export interface PageResponse<T> {
  content: T[];
  totalElements: number;
  totalPages: number;
  number: number;
}

export interface SaveVocabResponse {
  id: number;
  alreadyExists: boolean;
}

/** Mức người dùng tự chấm sau khi lật thẻ. Gương của enum Rating phía backend. */
export type Rating = 'AGAIN' | 'HARD' | 'GOOD' | 'EASY';

export type CardState = 'NEW' | 'REVIEW' | 'RELEARNING';

/** Gương của CardDto phía backend — thẻ đã gộp sẵn dữ liệu vocab. */
export interface CardDto {
  id: number;
  vocabEntryId: number;
  term: string;
  ipa: string | null;
  pos: string;
  meaningVi: string;
  definitionEn: string | null;
  cefr: string | null;
  bandLevel: string | null;
  collocations: unknown;
  examples: unknown;
  state: CardState;
  dueDate: string;
  /** 3 nghĩa tiếng Việt SAI, làm mồi nhử cho câu hỏi EN → VI. Rỗng khi backend chưa sinh kịp. */
  viDistractors: string[];
  /** 3 từ tiếng Anh SAI, làm mồi nhử cho câu hỏi VI → EN. Rỗng khi backend chưa sinh kịp. */
  enDistractors: string[];
}

export interface ReviewResponse {
  nextDueDate: string;
  intervalDays: number;
  easeFactor: number;
}

export interface SrsStats {
  dueCount: number;
  newCount: number;
  learnedCount: number;
}

/** Gương của enum QuizType phía backend. */
export type QuizType = 'FILL_BLANK' | 'COLLOCATION_CHOICE' | 'FREE_WRITE';

/**
 * Gương của QuizItemDto phía backend. KHÔNG chứa đáp án — backend cố ý không gửi.
 *
 * Field nào có mặt phụ thuộc `type`, nên mọi chỗ render phải phân nhánh theo `type`:
 *
 * | field       | FILL_BLANK      | COLLOCATION_CHOICE | FREE_WRITE |
 * |-------------|-----------------|--------------------|------------|
 * | term        | null            | có                 | có         |
 * | sentence    | có, chứa "___"  | null               | null       |
 * | options     | null            | đúng 4 phần tử     | null       |
 *
 * `term` null với FILL_BLANK là CỐ Ý: term chính là đáp án của loại đó.
 */
export interface QuizItemDto {
  id: number;
  type: QuizType;
  vocabEntryId: number;
  term: string | null;
  question: string;
  sentence: string | null;
  /**
   * Đã được backend xáo trộn sẵn lúc sinh đề. TUYỆT ĐỐI KHÔNG xáo lại ở panel:
   * câu trả lời gửi lên là index 0-based trong CHÍNH mảng này. Xáo lại = mọi
   * câu trắc nghiệm chấm sai mà không có lỗi nào nổ ra.
   *
   * (Khác hẳn ReviewTab của Phase 2 — ở đó panel tự xáo vì backend gửi cả đáp
   * án đúng lẫn mồi nhử. Đừng bê pattern đó sang đây.)
   *
   * Được phép xáo THỨ TỰ CÁC CÂU HỎI trong đề (mảng QuizItemDto[]).
   * KHÔNG được phép xáo mảng `options` bên trong một câu. Hai chuyện khác nhau.
   */
  options: string[] | null;
}

/**
 * Gương của AnswerResultDto phía backend.
 *
 * `improvedVersion` chỉ non-null với FREE_WRITE. Với hai loại kia luôn null —
 * nghĩa là "loại này không có khái niệm đó", không phải "chưa chấm xong".
 */
export interface AnswerResult {
  correct: boolean;
  score: number;
  feedback: string;
  improvedVersion: string | null;
}

/**
 * Gương của ExplanationDto phía backend.
 *
 * KHÔNG nằm trong QuizItemDto và cũng không nằm trong AnswerResult: nó chứa đáp án nên chỉ
 * lấy được qua EXPLAIN_QUIZ, sau khi câu đã có lượt làm.
 *
 * `sentenceEn` và `sentenceVi` là MỘT CẶP — cùng null hoặc cùng non-null, backend không bao
 * giờ gửi một nửa. Cùng null xảy ra đúng một ca: FREE_WRITE bị bỏ qua nên không có câu nào
 * để dịch.
 */
export interface QuizExplanation {
  explanation: string;
  answerMeaning: string;
  sentenceEn: string | null;
  sentenceVi: string | null;
}

/**
 * Gương của AuthUserDto phía backend. Đây là TOÀN BỘ những gì extension biết về người dùng
 * — không có id, không có token, vì panel không cần và không nên cầm.
 */
export interface AuthUser {
  email: string;
  displayName: string | null;
  pictureUrl: string | null;
}

/** Một ô ngày trong `daily`. `reviews: 0` là "ngày đó không ôn", không phải thiếu dữ liệu. */
export interface DailyPoint {
  date: string;
  reviews: number;
  /**
   * Số lượt luyện thêm trong ngày. Field RIÊNG chứ không cộng vào `reviews`: `reviews` giữ
   * nguyên nghĩa "lượt ôn theo lịch", và streak chỉ đếm nó.
   */
  practice: number;
}

export interface StreakInfo {
  current: number;
  longest: number;
  lastActiveDate: string | null;
}

export interface StatsTotals {
  reviews: number;
  /**
   * Số từ đã ôn ít nhất một lần (`repetitions >= 1`).
   *
   * ĐỪNG đọc nó là "đã thuộc": ngưỡng thuộc của cả 1b là `MASTERED_REPETITIONS`
   * (`vocab-progress.ts`), và con số đó là `masteredWords`. Field này chỉ còn dùng ở
   * `StatsTab` dưới nhãn "từ đã học" — một nhãn khác, nên không mâu thuẫn.
   */
  learnedWords: number;
  /** Số từ đã THUỘC: `repetitions >= MASTERED_REPETITIONS`. Ô "từ đã thuộc" ở Hôm nay. */
  masteredWords: number;
  /** Số từ ĐANG học: `1 <= repetitions < MASTERED_REPETITIONS`. */
  learningWords: number;
  activeDays: number;
  /**
   * Trung bình `band_level` của cả sổ từ.
   *
   * `null` = CHƯA từ nào có band, khác hẳn `0.0`. UI phải hiện "—" cho ca null; vẽ "0.0"
   * là nói với người học rằng vốn từ của họ ở band 0.
   *
   * Backend bỏ qua những hàng có `band_level` không parse được thay vì tính chúng thành 0
   * — một hàng rác kéo tụt trung bình của cả sổ mà không có gì đỏ.
   */
  avgBand: number | null;
  /**
   * Số TỪ lần đầu được đưa vào ôn trong 7 ngày gần nhất — dòng "+N từ mới tuần này".
   *
   * "Đưa vào ôn", KHÔNG phải "học thuộc": `review_log` không lưu `repetitions` nên "vượt
   * ngưỡng thuộc trong 7 ngày" là con số không tính được từ dữ liệu đang có. Đặt nó dưới
   * nhãn "+N tuần này" của ô "đã thuộc" là gán cho nó một ý nghĩa nó không có.
   */
  introducedLast7: number;
}

/** Số lượt THÔ theo 4 mức tự chấm. Tỉ lệ nhớ = `1 − again/tổng`, tính ở chỗ hiển thị. */
export interface RecallBreakdown {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

/**
 * `avgScore` là null với FILL_BLANK và COLLOCATION_CHOICE — hai loại đó chấm 100 hoặc 0 nên
 * điểm trung bình không mang thông tin gì mới. null nghĩa là "loại này không có khái niệm
 * điểm", KHÔNG phải "chưa có dữ liệu".
 */
export interface QuizTypeStats {
  type: QuizType;
  attempts: number;
  correct: number;
  avgScore: number | null;
}

/**
 * Gương của StatsDto phía backend.
 *
 * Hai bất biến mà UI dựa vào: `daily` LUÔN đúng 91 phần tử liên tục kết thúc ở hôm nay (theo
 * múi giờ của server, không phải của trình duyệt), và `quiz` LUÔN đủ 3 phần tử theo thứ tự
 * FILL_BLANK, COLLOCATION_CHOICE, FREE_WRITE.
 */
export interface StatsDto {
  streak: StreakInfo;
  totals: StatsTotals;
  daily: DailyPoint[];
  recall: RecallBreakdown;
  quiz: QuizTypeStats[];
}
