import type {
  AnswerResult, ApiError, AuthUser, CardDto, PageResponse, QuizExplanation, QuizItemDto,
  QuizType, Rating, ReviewResponse, SaveVocabResponse, SrsStats, StatsDto, TranslateResult,
  VocabEntryDto,
} from './types';

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

export interface SearchVocabRequest {
  type: 'SEARCH_VOCAB';
  query: string | null;
  tag: string | null;
  page: number;
}

export interface DeleteVocabRequest {
  type: 'DELETE_VOCAB';
  id: number;
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

export type ExtensionRequest =
  | TranslateSelectionRequest
  | TranslateTextRequest
  | OpenPanelRequest
  | SaveWordRequest
  | SearchVocabRequest
  | DeleteVocabRequest
  | GetLastResultRequest
  | HealthRequest
  | GetDueCardsRequest
  | SubmitReviewRequest
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
  SEARCH_VOCAB: PageResponse<VocabEntryDto>;
  DELETE_VOCAB: null;
  GET_LAST_RESULT: TranslateResult | null;
  CHECK_HEALTH: { status: string; dbConnected: boolean; geminiConfigured: boolean };
  GET_DUE_CARDS: CardDto[];
  SUBMIT_REVIEW: ReviewResponse;
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
 * Gửi message tới service worker và nhận về kết quả đã phân biệt ok/lỗi.
 *
 * `chrome.runtime.sendMessage` REJECT khi không có bên nhận — xảy ra thật khi
 * service worker vừa reload/crash, hoặc content script bị mồ côi sau khi reload
 * extension. Nuốt lỗi đó ở đây để mọi caller chỉ phải xử lý một hình dạng kết
 * quả, thay vì mỗi chỗ tự bọc try/catch (và quên).
 */
export async function sendToBackground<R extends ExtensionRequest>(
  request: R,
): Promise<ExtensionResponse<ResponseMap[R['type']]>> {
  let response: unknown;
  try {
    response = await chrome.runtime.sendMessage(request);
  } catch {
    return localError(
      'BACKEND_DOWN',
      'Không liên lạc được với extension. Tải lại trang, hoặc bật lại extension trong chrome://extensions.',
      true,
    );
  }

  if (typeof response !== 'object' || response === null || !('ok' in response)) {
    return localError('INTERNAL', 'Service worker không phản hồi đúng định dạng.', false);
  }
  return response as ExtensionResponse<ResponseMap[R['type']]>;
}
