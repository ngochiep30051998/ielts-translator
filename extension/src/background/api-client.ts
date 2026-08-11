import type {
  AnswerResult, ApiError, AuthUser, CardDto, PageResponse, QuizExplanation, QuizItemDto,
  QuizType, Rating, ReviewResponse, SaveVocabResponse, SrsStats, StatsDto, TranslateResult,
  VocabEntryDto,
} from '../shared/types';
import { clearAuth, loadToken } from '../shared/auth-storage';

const HEALTH_CACHE_MS = 30_000;

/**
 * timeoutMs KHÔNG phải ngân sách UX — nó là lưới chặn cuối. Việc duy nhất của nó là
 * LỚN HƠN trường hợp xấu nhất của backend, để người dùng nhận lỗi CÓ CẤU TRÚC
 * ({code, message, retryable}) thay vì một lỗi chung chung.
 *
 * Xấu nhất phía backend = MAX_ATTEMPTS × T + retryBackoffMillis
 *                       = 2 × T + 1s   (GeminiClient.MAX_ATTEMPTS = 2)
 *
 *   TRANSLATE      T=15s -> xấu nhất 31s -> 40s
 *   QUIZ_GENERATE  T=30s -> xấu nhất 61s -> 70s
 *   QUIZ_GRADE     T=20s -> xấu nhất 41s -> 50s
 *
 * Đổi GEMINI_*_TIMEOUT_SECONDS hoặc MAX_ATTEMPTS phía backend PHẢI đổi kèm ở đây.
 * Đặt thấp hơn xấu-nhất = client giết một request mà backend đang xử lý ĐÚNG.
 */
const DEFAULT_TIMEOUT_MS = 40_000;
const QUIZ_GENERATE_TIMEOUT_MS = 70_000;
const QUIZ_ANSWER_TIMEOUT_MS = 50_000;

export interface TranslateArgs {
  text: string;
  contextSentence: string | null;
  sourceUrl: string;
  pageTitle: string;
}

export interface HealthStatus {
  status: string;
  dbConnected: boolean;
  geminiConfigured: boolean;
}

function apiError(code: string, message: string, retryable: boolean): ApiError {
  return { code, message, retryable };
}

export class ApiClient {
  private healthCache: { value: HealthStatus; at: number } | null = null;

  constructor(private readonly baseUrlProvider: () => Promise<string>) {}

  async translate(args: TranslateArgs): Promise<TranslateResult> {
    const body = await this.request<Omit<TranslateResult, 'sourceText' | 'sourceSentence' | 'sourceUrl'>>(
      '/api/translate', { method: 'POST', body: JSON.stringify(args) },
    );
    return {
      ...body,
      sourceText: args.text,
      sourceSentence: args.contextSentence ?? undefined,
      sourceUrl: args.sourceUrl || undefined,
    };
  }

  async saveVocab(payload: unknown): Promise<SaveVocabResponse> {
    return this.request('/api/vocab', { method: 'POST', body: JSON.stringify(payload) });
  }

  async searchVocab(args: { query: string | null; tag: string | null; page: number }):
      Promise<PageResponse<VocabEntryDto>> {
    const params = new URLSearchParams();
    if (args.query) params.set('q', args.query);
    if (args.tag) params.set('tag', args.tag);
    params.set('page', String(args.page));
    return this.request(`/api/vocab?${params.toString()}`, { method: 'GET' });
  }

  async deleteVocab(id: number): Promise<null> {
    await this.request<null>(`/api/vocab/${id}`, { method: 'DELETE' });
    return null;
  }

  /** Hàng đợi ôn hôm nay: thẻ đến hạn trước, rồi tới thẻ mới trong hạn mức `newLimit`. */
  async getDueCards(args: { limit: number; newLimit: number }): Promise<CardDto[]> {
    const params = new URLSearchParams({
      limit: String(args.limit),
      newLimit: String(args.newLimit),
    });
    return this.request(`/api/srs/due?${params.toString()}`, { method: 'GET' });
  }

  async submitReview(args: { cardId: number; rating: Rating }): Promise<ReviewResponse> {
    return this.request('/api/srs/review', { method: 'POST', body: JSON.stringify(args) });
  }

  /** Xấp thẻ luyện thêm. Không có `newLimit` — chế độ này không có khái niệm "đến hạn". */
  async getPracticeCards(limit: number): Promise<CardDto[]> {
    return this.request(`/api/srs/practice?limit=${limit}`, { method: 'GET' });
  }

  /** Ghi một lượt luyện thêm. Backend trả 204 nên không có gì để đọc. */
  async submitPractice(args: { cardId: number; rating: Rating }): Promise<null> {
    await this.request<null>('/api/srs/practice', {
      method: 'POST',
      body: JSON.stringify(args),
    });
    return null;
  }

  async srsStats(newLimit: number): Promise<SrsStats> {
    return this.request(`/api/srs/stats?newLimit=${newLimit}`, { method: 'GET' });
  }

  /**
   * Thống kê tiến độ học. Tên `learningStats` chứ không `stats` để không lẫn với
   * `srsStats` ở ngay trên — cái kia trả số thẻ đến hạn cho badge.
   */
  async learningStats(): Promise<StatsDto> {
    return this.request('/api/stats', { method: 'GET' });
  }

  /**
   * Sinh đề cho ĐÚNG MỘT loại. Panel muốn nhiều loại thì gọi nhiều lần TUẦN TỰ —
   * mỗi loại là một lượt gọi Gemini, gộp lại đẩy xấu nhất lên ~122s và biến một
   * loại hỏng thành mất trắng cả đề.
   *
   * Không có ứng viên nào → backend trả `[]` với HTTP 200. Đó KHÔNG phải lỗi.
   */
  async generateQuiz(args: {
    vocabIds: number[] | null; count: number | null; type: QuizType;
  }): Promise<QuizItemDto[]> {
    return this.request('/api/quiz/generate',
      { method: 'POST', body: JSON.stringify(args) }, QUIZ_GENERATE_TIMEOUT_MS);
  }

  async answerQuiz(args: { quizItemId: number; answer: string }): Promise<AnswerResult> {
    return this.request('/api/quiz/answer',
      { method: 'POST', body: JSON.stringify(args) }, QUIZ_ANSWER_TIMEOUT_MS);
  }

  /**
   * Giải thích một câu ĐÃ trả lời. Cũng là một lượt gọi Gemini nên dùng chung mức chờ với
   * chấm bài — 40 giây mặc định là ngắn khi backend đang đợi Gemini.
   */
  async explainQuiz(args: { quizItemId: number }): Promise<QuizExplanation> {
    return this.request('/api/quiz/explain',
      { method: 'POST', body: JSON.stringify(args) }, QUIZ_ANSWER_TIMEOUT_MS);
  }

  /**
   * Đổi authorization code lấy phiên. KHÔNG gắn Authorization — lúc này chưa có token nào,
   * và đây là đường DUY NHẤT để có.
   */
  async googleLogin(args: { code: string; redirectUri: string }):
      Promise<{ token: string; expiresAt: string; user: AuthUser }> {
    return this.request('/api/auth/google',
      { method: 'POST', body: JSON.stringify(args) }, DEFAULT_TIMEOUT_MS, false);
  }

  /** Kiểm token còn sống, thay vì đợi một request nghiệp vụ nào đó nhận 401. */
  async authMe(): Promise<AuthUser> {
    return this.request('/api/auth/me', { method: 'GET' });
  }

  async logout(): Promise<null> {
    await this.request<null>('/api/auth/logout', { method: 'POST' });
    return null;
  }

  async health(): Promise<HealthStatus> {
    const now = Date.now();
    if (this.healthCache && now - this.healthCache.at < HEALTH_CACHE_MS) {
      return this.healthCache.value;
    }
    // KHÔNG gắn token: /api/health là thứ dùng để chẩn đoán KHI đăng nhập đang hỏng.
    // Bắt nó phải có token là tự khoá mình ngoài cửa đúng lúc cần nó nhất.
    const value = await this.request<HealthStatus>('/api/health', { method: 'GET' },
      DEFAULT_TIMEOUT_MS, false);
    this.healthCache = { value, at: now };   // chỉ cache khi thành công
    return value;
  }

  /**
   * @param authenticated false CHỈ cho /api/auth/google — mọi đường khác đều phải mang
   *                      token. Mặc định true để thêm endpoint mới mà quên là không thể.
   */
  private async request<T>(path: string, init: RequestInit,
                           timeoutMs: number = DEFAULT_TIMEOUT_MS,
                           authenticated = true): Promise<T> {
    const baseUrl = await this.baseUrlProvider();

    const authHeaders: Record<string, string> = {};
    if (authenticated) {
      const token = await loadToken();
      if (!token) {
        // Ném tại chỗ thay vì gọi rồi nhận 401: cùng kết quả, nhưng không tốn một vòng
        // mạng và một dòng log rác mỗi lần alarm badge chạy lúc chưa đăng nhập.
        throw apiError('UNAUTHORIZED', 'Cần đăng nhập để dùng chức năng này', false);
      }
      authHeaders.Authorization = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        ...init,
        signal: AbortSignal.timeout(timeoutMs),
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
          ...(init.headers ?? {}),
        },
      });
    } catch (error) {
      // Nhận diện quá hạn bằng TÊN lỗi, không bằng `instanceof DOMException`: dưới jsdom
      // (môi trường test) DOMException global là của jsdom trong khi lỗi abort có thể
      // đến từ fetch của Node — instanceof sẽ false và mọi timeout bị báo nhầm thành
      // "không kết nối được".
      //
      // Thông điệp nhắc "đề có thể đã sinh xong": client bỏ cuộc KHÔNG dừng được xử lý
      // phía server, item vẫn commit, và lần bấm sau tái dùng chúng với 0 call Gemini.
      // Đó là tính năng, không phải bug — nhưng phải nói ra, nếu không người dùng thấy
      // đề "xuất hiện bí ẩn".
      if ((error as { name?: string } | null)?.name === 'TimeoutError') {
        throw apiError('BACKEND_DOWN',
          'Backend xử lý quá lâu và đã quá hạn chờ. Đề có thể đã sinh xong ở backend — bấm "Tạo đề" lại, thường sẽ có ngay.',
          true);
      }
      throw apiError('BACKEND_DOWN',
        'Không kết nối được backend. Kiểm tra docker compose đã chạy chưa.', true);
    }

    if (response.status === 204) {
      return null as T;
    }

    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      throw apiError('INTERNAL', `Backend trả phản hồi không đọc được (HTTP ${response.status})`, false);
    }

    if (response.status === 401 && authenticated) {
      // Phiên chết ở server (hết hạn hoặc bị thu hồi từ thiết bị khác). Xoá token ngay để
      // request kế tiếp không lặp lại vòng này, rồi để UI đưa người dùng về màn đăng nhập.
      // KHÔNG tự mở lại luồng OAuth: launchWebAuthFlow bật cửa sổ, và cửa sổ tự bật khi
      // người dùng không bấm gì là hành vi đáng ngờ.
      await clearAuth();
    }

    if (!response.ok) {
      const error = parsed as Partial<ApiError>;
      throw apiError(
        error.code ?? 'INTERNAL',
        error.message ?? `Backend trả lỗi HTTP ${response.status}`,
        error.retryable ?? false,
      );
    }
    return parsed as T;
  }
}
