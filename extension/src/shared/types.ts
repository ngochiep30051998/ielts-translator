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
