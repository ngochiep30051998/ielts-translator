import type { ApiClient } from './api-client';
import { keyVocabOf } from './key-vocab';
import type { KeyVocabItem } from './key-vocab';
import type { ExtensionRequest, SaveKeyVocabResult } from './messages';
import type { OperationsPlatform } from './ports';
import type { TranslateResult } from './types';
import type { ApiError } from './types';

/**
 * Xử lý một `ExtensionRequest`. Đây là phần thân của `handle()` cũ trong service worker,
 * gỡ khỏi mọi thứ thuộc về Chrome.
 *
 * Extension gọi nó từ listener của `chrome.runtime.onMessage`; web gọi nó thẳng trong
 * cùng tiến trình. Hai đường đi khác nhau nhưng ĐÚNG MỘT cách xử lý — đó là toàn bộ lý do
 * file này tồn tại.
 */
export function createOperations(client: ApiClient, platform: OperationsPlatform) {
  return async function handle(request: ExtensionRequest, senderTabId?: number): Promise<unknown> {
    switch (request.type) {
      case 'TRANSLATE_SELECTION': {
        const result = await client.translate({
          text: request.text,
          contextSentence: request.contextSentence,
          sourceUrl: request.sourceUrl,
          pageTitle: request.pageTitle,
        });
        await platform.lastResult.set(result);
        return result;
      }
      case 'TRANSLATE_TEXT': {
        // Chuỗi rỗng chứ không phải null cho sourceUrl/pageTitle: api-client đã có sẵn
        // `args.sourceUrl || undefined`, nên rỗng tự biến thành "không có nguồn".
        const result = await client.translate({
          text: request.text,
          contextSentence: null,
          sourceUrl: '',
          pageTitle: '',
        });
        await platform.lastResult.set(result);
        return result;
      }
      case 'OPEN_PANEL_WITH_RESULT': {
        await platform.lastResult.set(request.result);
        if (senderTabId !== undefined) {
          await platform.openPanel?.(senderTabId);
        }
        return null;
      }
      case 'GET_LAST_RESULT':
        return platform.lastResult.get();
      case 'SAVE_WORD': {
        // Từ mới vào sổ = thêm một thẻ vào hàng đợi ôn, nên badge phải đổi ngay.
        const result = await client.saveVocab(buildVocabPayload(request.result, request.tags));
        void platform.onVocabChanged?.();
        return result;
      }
      case 'SAVE_KEY_VOCAB': {
        const items = keyVocabOf(request.result);
        const outcome: SaveKeyVocabResult = { saved: 0, existed: 0, failures: [] };

        for (const item of items) {
          // TUẦN TỰ chứ không `Promise.all`: cùng một người dùng, và hai lượt POST song song
          // cho hai từ giống nhau sau chuẩn hoá là một cuộc đua không cần thiết.
          try {
            const saved = await client.saveVocab(buildKeyVocabPayload(request.result, item, request.tags));
            if (saved.alreadyExists) outcome.existed += 1;
            else outcome.saved += 1;
          } catch (error) {
            // Đi HẾT danh sách kể cả khi có lỗi: lưu được 3 trong 5 từ vẫn hơn bỏ cả 5 vì
            // từ thứ hai hỏng. Người dùng thấy đúng từ nào hỏng, không phải "có lỗi xảy ra".
            outcome.failures.push({ term: item.term, error: toApiError(error) });
          }
        }

        // ĐÚNG MỘT LẦN cho cả mẻ, và chỉ khi có từ mới: badge đếm thẻ đến hạn, mẻ không
        // thêm từ nào thì con số không thể đổi.
        if (outcome.saved > 0) void platform.onVocabChanged?.();
        return outcome;
      }
      case 'SEARCH_VOCAB':
        return client.searchVocab({
          query: request.query, tag: request.tag,
          untagged: request.untagged, page: request.page,
        });
      case 'DELETE_VOCAB': {
        // Xoá từ là xoá luôn thẻ của nó (ON DELETE CASCADE) — badge phải bỏ số cũ đi.
        const result = await client.deleteVocab(request.id);
        void platform.onVocabChanged?.();
        return result;
      }
      case 'GET_VOCAB_TAGS':
        return client.vocabTags();
      case 'UPDATE_VOCAB':
        // KHÔNG báo đổi: sửa nghĩa hay đổi thẻ không thêm và không bớt thẻ ôn nào, nên
        // số trên badge không thể đổi vì một lượt sửa.
        return client.updateVocab({
          id: request.id, meaningVi: request.meaningVi, tags: request.tags,
        });
      case 'EXPORT_VOCAB_CSV':
        return client.exportVocabCsv();
      case 'GET_DUE_CARDS':
        return client.getDueCards({ limit: request.limit, newLimit: request.newLimit });
      case 'SUBMIT_REVIEW': {
        const result = await client.submitReview({ cardId: request.cardId, rating: request.rating });
        void platform.onVocabChanged?.();
        return result;
      }
      case 'GET_PRACTICE_CARDS':
        return client.getPracticeCards(request.limit);
      case 'SUBMIT_PRACTICE':
        // KHÔNG báo đổi: luyện thêm không đụng lịch, nên số thẻ đến hạn không thể đổi vì
        // một lượt luyện.
        return client.submitPractice({ cardId: request.cardId, rating: request.rating });
      case 'GET_SRS_STATS':
        return client.srsStats(request.newLimit);
      case 'GET_STATS':
        // KHÔNG báo đổi: đây là màn chỉ đọc, số thẻ đến hạn không thể đổi vì một lượt xem
        // biểu đồ.
        return client.learningStats();
      case 'GENERATE_QUIZ':
        return client.generateQuiz({
          vocabIds: request.vocabIds,
          count: request.count,
          type: request.quizType,   // quizType (message) -> type (HTTP body)
        });
      case 'ANSWER_QUIZ':
        // KHÔNG báo đổi ở đây: quiz không chạm lịch SRS, nên số thẻ đến hạn không thể đổi
        // vì một lượt nộp bài.
        return client.answerQuiz({ quizItemId: request.quizItemId, answer: request.answer });
      case 'EXPLAIN_QUIZ':
        // Cũng như ANSWER_QUIZ. Quiz không chạm lịch SRS nên số thẻ đến hạn không thể đổi
        // vì một lượt xin giải thích.
        return client.explainQuiz({ quizItemId: request.quizItemId });
      case 'SIGN_IN': {
        const user = await platform.auth.signIn();
        await platform.onVocabChanged?.();
        return user;
      }
      case 'SIGN_OUT':
        // Xoá phiên phía client DÙ backend lỗi. Giữ lại vì server không phản hồi sẽ kẹt
        // người dùng ở trạng thái "đã bấm đăng xuất nhưng vẫn đang đăng nhập" — và trên
        // máy mượn thì đó đúng là điều họ vừa cố tránh.
        try {
          await client.logout();
        } finally {
          await platform.auth.signOut();
          await platform.onVocabChanged?.();
        }
        return null;
      case 'GET_AUTH_STATE':
        return platform.auth.currentUser();
      case 'CHECK_HEALTH':
        return client.health();
    }
  };
}

export type Operations = ReturnType<typeof createOperations>;

/**
 * Chuyển một giá trị ném ra thành `ApiError`.
 *
 * `ApiClient` ném đúng hình dạng đó rồi, nên nhánh đầu là đường đi thường. Nhánh sau chỉ
 * bắt lỗi lập trình — và cố ý KHÔNG đưa nội dung lỗi gốc vào thông điệp, vì nó có thể
 * chứa nguyên đoạn dữ liệu người dùng vừa gửi.
 */
export function toApiError(error: unknown): ApiError {
  if (error && typeof error === 'object' && 'code' in error) {
    return error as ApiError;
  }
  return { code: 'INTERNAL', message: 'Lỗi không xác định', retryable: false };
}

/** Chuyển kết quả dịch thành body cho POST /api/vocab. */
export function buildVocabPayload(result: TranslateResult, tags: string[]) {
  const payload = result.payload as unknown as Record<string, unknown>;
  const isEnVi = result.direction === 'EN_VI';
  const isWord = result.mode === 'WORD';

  const term = isEnVi
    ? (payload.term as string) ?? result.sourceText
    : (payload.best_en as string) ?? (payload.band65_version as string) ?? '';
  const meaningVi = isEnVi
    ? (payload.meaning_vi as string) ?? (payload.translation_vi as string) ?? ''
    : result.sourceText;

  return {
    term,
    lemma: (payload.lemma as string) ?? term,
    lang: 'en',
    pos: isWord ? ((payload.pos as string) ?? '') : 'phrase',
    ipa: (payload.ipa as string) ?? null,
    meaningVi,
    definitionEn: (payload.definition_en as string) ?? null,
    cefr: (payload.cefr as string) ?? null,
    bandLevel: (payload.band_level as string) ?? null,
    tags,
    sourceUrl: result.sourceUrl ?? null,
    sourceSentence: result.sourceSentence ?? null,
    collocations: payload.collocations ?? [],
    examples: payload.examples ?? [],
  };
}

/**
 * Dựng body POST /api/vocab cho MỘT từ đáng học của một câu EN→VI.
 *
 * Cùng hình dạng với `buildVocabPayload`, khác ở chỗ nguồn dữ liệu là một phần tử
 * `key_vocab` chứ không phải cả payload — mà phần tử đó chỉ mang đúng ba thứ: `term`,
 * `meaning_vi`, `band_level`. Mọi field còn lại để `null`/rỗng chứ KHÔNG bịa.
 */
export function buildKeyVocabPayload(
  result: TranslateResult, item: KeyVocabItem, tags: string[],
) {
  return {
    term: item.term,
    // Không biết dạng nguyên thể — `key_vocab` không trả lemma. Dùng chính nó.
    lemma: item.term,
    lang: 'en',
    // Chuỗi rỗng, KHÔNG phải 'phrase' như nhánh câu: đây là TỪ, và `key_vocab` không trả
    // từ loại. Cột `vocab_entry.pos` là VARCHAR(16) NOT NULL DEFAULT '' nên `null` không
    // dùng được ở đây.
    //
    // LƯU Ý về trùng lặp: khoá chống trùng phía backend là `(user_id, term, pos)`, mà cùng
    // một từ lưu qua bubble EN→VI chế độ TỪ sẽ mang `pos` thật ('verb', 'noun'...). Nên
    // `pos: ''` KHÔNG gộp được hai đường lưu — sổ từ vẫn có thể có hai hàng cho cùng một
    // term, khác `pos`. Đó là hành vi hiện tại, không phải chuyện đã được xử lý.
    pos: '',
    ipa: null,
    meaningVi: item.meaningVi,
    definitionEn: null,
    cefr: null,
    bandLevel: item.bandLevel,
    tags,
    sourceUrl: result.sourceUrl ?? null,
    // Với một từ đáng học, chính câu đang dịch LÀ ngữ cảnh của nó. `sourceSentence` null khi
    // người dùng gõ tay vào ô Dịch — lúc đó `sourceText` chính là câu đó.
    sourceSentence: result.sourceSentence ?? result.sourceText,
    collocations: [],
    examples: [],
  };
}
