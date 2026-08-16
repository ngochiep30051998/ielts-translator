import type {
  AnswerResult, ApiError, AuthUser, CardDto, PageResponse, QuizExplanation, QuizItemDto,
  QuizType, Rating, ReviewResponse, SaveVocabResponse, SrsStats, StatsDto, TranslateResult,
  VocabEntryDto, VocabTagsResponse,
} from './types';
import { currentTransport } from './transport';

export interface TranslateSelectionRequest {
  type: 'TRANSLATE_SELECTION';
  text: string;
  contextSentence: string | null;
  sourceUrl: string;
  pageTitle: string;
}

/**
 * Dịch đoạn text người dùng gõ/dán thẳng vào side panel.
 *
 * Tách khỏi TRANSLATE_SELECTION chứ không tái dùng: không có trang nguồn, không có câu
 * ngữ cảnh, và service worker cần phân biệt được hai nguồn nếu sau này chúng phải khác nhau.
 */
export interface TranslateTextRequest {
  type: 'TRANSLATE_TEXT';
  text: string;
}

export interface OpenPanelRequest {
  type: 'OPEN_PANEL_WITH_RESULT';
  result: TranslateResult;
}

export interface SaveWordRequest {
  type: 'SAVE_WORD';
  result: TranslateResult;
  tags: string[];
}

/**
 * Lưu CẢ MẺ "từ đáng học" của một câu EN→VI vào sổ từ.
 *
 * Tách khỏi `SAVE_WORD` chứ không tái dùng: `SAVE_WORD` lưu ĐÚNG MỘT mục dựng từ chính kết
 * quả dịch (với chế độ CÂU thì mục đó là cả câu), còn cái này lưu N mục dựng từ mảng
 * `key_vocab` bên trong payload. Hai việc khác nhau, và kết quả trả về cũng khác hình dạng.
 *
 * Gửi cả `result` thay vì gửi sẵn danh sách từ: nơi rút danh sách là `keyVocabOf`, và để
 * đúng một chỗ làm việc đó thì UI không được phép gửi lên một danh sách nó tự lọc.
 */
export interface SaveKeyVocabRequest {
  type: 'SAVE_KEY_VOCAB';
  result: TranslateResult;
  tags: string[];
}

/**
 * Kết quả một mẻ lưu từ đáng học.
 *
 * Ba con số tách bạch chứ không phải một cờ thành/bại: mẻ lưu 5 từ có thể vừa thêm mới, vừa
 * đụng từ đã có, vừa hỏng vài từ — gộp lại thành "đã lưu" hay "có lỗi" đều là nói dối một nửa.
 */
export interface SaveKeyVocabResult {
  /** Số từ MỚI được thêm. */
  saved: number;
  /** Số từ backend báo `alreadyExists` — đã có sẵn trong sổ. */
  existed: number;
  /** Những từ không lưu được. Rỗng = trọn vẹn. */
  failures: { term: string; error: ApiError }[];
}

export interface SearchVocabRequest {
  type: 'SEARCH_VOCAB';
  query: string | null;
  tag: string | null;
  /**
   * true = CHỈ những từ chưa gắn thẻ nào (`tags` là mảng rỗng).
   *
   * KHÔNG đi cùng `tag`: hai điều kiện mâu thuẫn nhau và backend trả 400. UI đảm bảo điều
   * đó bằng cách bấm chip nào thì xoá điều kiện của chip kia.
   */
  untagged: boolean;
  page: number;
}

export interface DeleteVocabRequest {
  type: 'DELETE_VOCAB';
  id: number;
}

/**
 * Toàn bộ dữ liệu của hàng chip lọc ở tab Sổ từ: tổng không lọc, số từ chưa gắn thẻ, và
 * danh sách chủ đề kèm số từ.
 *
 * Không tham số: phạm vi luôn là sổ từ của người đang đăng nhập, backend lấy user id từ
 * `Depends(current_user_id)`. Sổ rỗng trả `{ total: 0, untagged: 0, tags: [] }` chứ không
 * phải lỗi.
 */
export interface GetVocabTagsRequest {
  type: 'GET_VOCAB_TAGS';
}

/**
 * Sửa một mục sổ từ. Ánh xạ sang PATCH /api/vocab/{id}, và ngữ nghĩa PATCH được giữ
 * nguyên tới tận đây: `null` nghĩa là KHÔNG ĐỘNG TỚI field đó.
 *
 * Với `tags`, `null` và `[]` là hai chuyện khác hẳn nhau — `null` giữ nguyên thẻ cũ, còn
 * `[]` gỡ sạch thẻ. Gộp hai thứ đó lại thì không còn cách nào gỡ một thẻ gắn nhầm.
 */
export interface UpdateVocabRequest {
  type: 'UPDATE_VOCAB';
  id: number;
  /** null = KHÔNG đổi field này (khớp ngữ nghĩa PATCH). */
  meaningVi: string | null;
  /** null = KHÔNG đổi. Mảng (kể cả rỗng) = THAY THẾ toàn bộ, không merge. */
  tags: string[] | null;
}

export interface GetLastResultRequest {
  type: 'GET_LAST_RESULT';
}

export interface HealthRequest {
  type: 'CHECK_HEALTH';
}

export interface GetDueCardsRequest {
  type: 'GET_DUE_CARDS';
  limit: number;
  newLimit: number;
}

export interface SubmitReviewRequest {
  type: 'SUBMIT_REVIEW';
  cardId: number;
  rating: Rating;
}

/** Xấp thẻ luyện thêm — mọi từ đã học, xáo ngẫu nhiên. Không có khái niệm "đến hạn". */
export interface GetPracticeCardsRequest {
  type: 'GET_PRACTICE_CARDS';
  limit: number;
}

/**
 * Một lượt luyện thêm. KHÔNG đổi lịch SM-2 — đó là toàn bộ điểm khác biệt với
 * `SUBMIT_REVIEW`. Gửi nhầm cái này cho một lượt ôn thật thì lịch đứng yên mãi mãi.
 */
export interface SubmitPracticeRequest {
  type: 'SUBMIT_PRACTICE';
  cardId: number;
  rating: Rating;
}

export interface GetSrsStatsRequest {
  type: 'GET_SRS_STATS';
  newLimit: number;
}

/**
 * Thống kê tiến độ học. Không tham số: cửa sổ thời gian là hằng số phía server.
 *
 * Tên `GET_STATS` chứ không `GET_LEARNING_STATS` để ngắn, nhưng ĐỪNG nhầm với
 * `GET_SRS_STATS` — cái kia trả số thẻ đến hạn cho badge, cái này trả biểu đồ.
 */
export interface GetStatsRequest {
  type: 'GET_STATS';
}

export interface GenerateQuizRequest {
  type: 'GENERATE_QUIZ';
  /** Đúng một trong hai field dưới được set; field còn lại là null. Backend trả 400 nếu sai. */
  vocabIds: number[] | null;
  /** Số CÂU cho loại này. Mỗi từ 1 câu/loại nên cũng đúng bằng số từ. */
  count: number | null;
  /**
   * Đặt tên `quizType` chứ không phải `type`: `type` đã là trường phân biệt của
   * union ExtensionRequest. Trên đường HTTP field này tên là `type` —
   * ApiClient.generateQuiz() là chỗ ánh xạ. Đừng đổi một trong hai mà quên chỗ kia.
   */
  quizType: QuizType;
}

export interface AnswerQuizRequest {
  type: 'ANSWER_QUIZ';
  quizItemId: number;
  /** Luôn là string. Với COLLOCATION_CHOICE là index 0-based dạng chuỗi: "0".."3". */
  answer: string;
}

/**
 * CỐ Ý không mang câu trả lời, dù panel đang giữ nó: backend tự đọc lượt làm gần nhất và
 * trả 404 khi chưa có. Response chứa đáp án, nên gửi kèm câu trả lời từ đây là mở một đường
 * vòng đọc đáp án trước khi trả lời.
 */
export interface ExplainQuizRequest {
  type: 'EXPLAIN_QUIZ';
  quizItemId: number;
}

/**
 * Mở cửa sổ đăng nhập Google.
 *
 * <p>`chrome.identity` CHỈ gọi được từ service worker, nên panel không tự mở được luồng
 * OAuth — nó gửi message này. Cùng lý do với ràng buộc #1: token không bao giờ đi qua
 * content script hay panel.
 */
export interface SignInRequest {
  type: 'SIGN_IN';
}

export interface SignOutRequest {
  type: 'SIGN_OUT';
}

/**
 * Trạng thái đăng nhập hiện tại. Chưa đăng nhập trả `data: null` — đó KHÔNG phải lỗi, nên
 * nó không được là `ok: false`. Panel phân biệt "chưa đăng nhập" với "backend chết" bằng
 * đúng chỗ này.
 */
export interface GetAuthStateRequest {
  type: 'GET_AUTH_STATE';
}

/**
 * Tải sổ từ dạng CSV.
 *
 * Đi qua service worker như mọi luồng khác chứ KHÔNG mở `window.open` thẳng tới backend:
 * một lượt điều hướng không mang được token Bearer lẫn header `X-IELTS-Web`, nên cách cũ
 * luôn nhận 401. Ràng buộc #1 nói đúng chuyện này.
 */
export interface ExportVocabCsvRequest {
  type: 'EXPORT_VOCAB_CSV';
}

export type ExtensionRequest =
  | TranslateSelectionRequest
  | TranslateTextRequest
  | OpenPanelRequest
  | SaveWordRequest
  | SaveKeyVocabRequest
  | SearchVocabRequest
  | DeleteVocabRequest
  | GetVocabTagsRequest
  | UpdateVocabRequest
  | ExportVocabCsvRequest
  | GetLastResultRequest
  | HealthRequest
  | GetDueCardsRequest
  | SubmitReviewRequest
  | GetPracticeCardsRequest
  | SubmitPracticeRequest
  | GetSrsStatsRequest
  | GetStatsRequest
  | GenerateQuizRequest
  | AnswerQuizRequest
  | ExplainQuizRequest
  | SignInRequest
  | SignOutRequest
  | GetAuthStateRequest;

export type ExtensionResponse<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export interface ResponseMap {
  TRANSLATE_SELECTION: TranslateResult;
  TRANSLATE_TEXT: TranslateResult;
  OPEN_PANEL_WITH_RESULT: null;
  SAVE_WORD: SaveVocabResponse;
  SAVE_KEY_VOCAB: SaveKeyVocabResult;
  SEARCH_VOCAB: PageResponse<VocabEntryDto>;
  DELETE_VOCAB: null;
  GET_VOCAB_TAGS: VocabTagsResponse;
  UPDATE_VOCAB: VocabEntryDto;
  /** Nội dung file CSV, chưa tải xuống — UI tự dựng blob. */
  EXPORT_VOCAB_CSV: string;
  GET_LAST_RESULT: TranslateResult | null;
  CHECK_HEALTH: { status: string; dbConnected: boolean; geminiConfigured: boolean };
  GET_DUE_CARDS: CardDto[];
  SUBMIT_REVIEW: ReviewResponse;
  GET_PRACTICE_CARDS: CardDto[];
  SUBMIT_PRACTICE: null;
  GET_SRS_STATS: SrsStats;
  GET_STATS: StatsDto;
  GENERATE_QUIZ: QuizItemDto[];
  ANSWER_QUIZ: AnswerResult;
  EXPLAIN_QUIZ: QuizExplanation;
  SIGN_IN: AuthUser;
  SIGN_OUT: null;
  GET_AUTH_STATE: AuthUser | null;
}

function localError(code: string, message: string, retryable: boolean): { ok: false; error: ApiError } {
  return { ok: false, error: { code, message, retryable } };
}

/**
 * Gửi một request tới nơi xử lý nó và nhận về kết quả đã phân biệt ok/lỗi.
 *
 * Transport ném là chuyện có thật ở cả hai surface, vì hai lý do khác nhau:
 * `chrome.runtime.sendMessage` REJECT khi không có bên nhận (service worker vừa
 * reload/crash, hoặc content script bị mồ côi sau khi reload extension); còn trên web thì
 * `operations` chạy cùng tiến trình nên chỉ ném khi có lỗi lập trình. Nuốt lỗi ở đây để
 * mọi caller chỉ phải xử lý một hình dạng kết quả, thay vì mỗi chỗ tự bọc try/catch
 * (và quên).
 *
 * Thông điệp cho ca đó do transport mang theo (`disconnectedError`) chứ không viết cứng ở
 * đây — cách khắc phục của extension và của web không giống nhau chút nào.
 */
export async function sendToBackground<R extends ExtensionRequest>(
  request: R,
): Promise<ExtensionResponse<ResponseMap[R['type']]>> {
  const transport = currentTransport();
  if (!transport) {
    // Chỉ xảy ra khi surface quên gọi `setTransport` lúc khởi động. Nói thẳng ra thay vì
    // để nó biểu hiện thành "mọi thao tác đều im lặng không làm gì".
    return localError('INTERNAL', 'Transport chưa được cài đặt cho surface này.', false);
  }

  let response: unknown;
  try {
    response = await transport.send(request);
  } catch {
    return { ok: false, error: transport.disconnectedError };
  }

  if (typeof response !== 'object' || response === null || !('ok' in response)) {
    return localError('INTERNAL', 'Không nhận được phản hồi đúng định dạng.', false);
  }
  return response as ExtensionResponse<ResponseMap[R['type']]>;
}
