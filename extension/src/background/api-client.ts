import type {
  ApiError, PageResponse, SaveVocabResponse, TranslateResult, VocabEntryDto,
} from '../shared/types';

const HEALTH_CACHE_MS = 30_000;

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

  async health(): Promise<HealthStatus> {
    const now = Date.now();
    if (this.healthCache && now - this.healthCache.at < HEALTH_CACHE_MS) {
      return this.healthCache.value;
    }
    const value = await this.request<HealthStatus>('/api/health', { method: 'GET' });
    this.healthCache = { value, at: now };   // chỉ cache khi thành công
    return value;
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const baseUrl = await this.baseUrlProvider();

    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
      });
    } catch {
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
