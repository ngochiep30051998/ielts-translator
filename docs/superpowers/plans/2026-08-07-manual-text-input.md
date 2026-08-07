# Nhập text thủ công để dịch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm ô nhập text vào tab "Dịch" của side panel để dịch được đoạn người dùng gõ/dán vào, không chỉ đoạn bôi đen trên trang.

**Architecture:** Ô nhập nằm trên vùng kết quả sẵn có trong `TranslateTab`; hai đường (bôi đen và nhập tay) dùng chung một vùng kết quả. State `draft`/`result` được nâng lên `App` để sống sót khi đổi tab. Side panel gửi message mới `TRANSLATE_TEXT` xuống service worker — side panel không bao giờ tự gọi HTTP. Backend không đổi một dòng nào.

**Tech Stack:** React 18 + TypeScript 5.7 (`strict` + `noUnusedLocals`), Vite 5 + `@crxjs/vite-plugin`, Vitest + React Testing Library + jsdom. Không thêm dependency nào.

**Spec:** `docs/superpowers/specs/2026-08-07-manual-text-input-design.md`

## Global Constraints

Áp dụng cho **mọi** task dưới đây:

- **Ngôn ngữ:** comment, text hiển thị, message lỗi viết bằng tiếng Việt đủ dấu. Tên biến/hàm/type giữ tiếng Anh. Lưu UTF-8.
- **Không thêm dependency mới.** Không thêm thư viện UI, state, form, validation.
- **Side panel không gọi HTTP.** Mọi request đi qua `sendToBackground` → service worker → `background/api-client.ts`.
- **Message contract:** luồng mới phải có interface request riêng, có mặt trong union `ExtensionRequest` **và** trong `ResponseMap` của `extension/src/shared/messages.ts`.
- **Hình dạng lỗi:** `{ code: string, message: string, retryable: boolean }`. UI phải phân biệt `retryable` true/false.
- **Giới hạn text:** đúng `1500` ký tự, hằng số tên `MAX_SELECTION_LENGTH`. Không được có bản sao thứ ba của con số này trong `extension/`.
- **Backend không đổi:** không sửa file Java, không migration Flyway, không sửa `resources/prompts/*.md`, không bump `version:`.
- **Type check chỉ chạy ở `npm run build`.** `npm test` xanh mà `npm run build` đỏ vẫn là hỏng. Task nào cũng phải chạy cả hai.
- Mọi lệnh `npm` chạy với cwd = `extension/`.
- **Commit:** CLAUDE.md cấm tự commit. Trước Task 1, xin phép người dùng một lần và hỏi luôn có tách nhánh mới (`feat/manual-text-input`) từ `feat/phase3-quiz` không. Được đồng ý rồi thì các bước commit trong plan này coi như đã được cho phép.

---

### Task 1: Chuyển `validateSelection` sang `shared/`

Refactor thuần, không đổi hành vi. Mục đích: side panel dùng được cùng logic chặn 1500 ký tự mà không phải import ngược từ `content/` và không phải chép hằng số.

`extractContextSentence()` **ở lại** `content/selection.ts` — nó chỉ có nghĩa với một DOM selection.

**Files:**
- Create: `extension/src/shared/text.ts`
- Create: `extension/src/shared/text.test.ts`
- Modify: `extension/src/content/selection.ts` (xoá dòng 1–13)
- Modify: `extension/src/content/selection.test.ts` (xoá dòng 1–22, sửa import)
- Modify: `extension/src/content/index.ts:1`
- Modify: `CLAUDE.md` (ràng buộc số 9)

**Interfaces:**
- Consumes: không có (task đầu tiên).
- Produces:
  - `MAX_SELECTION_LENGTH: number` — hằng `1500`, export từ `shared/text.ts`
  - `type SelectionCheck = { ok: true; text: string } | { ok: false; reason: 'EMPTY' | 'TOO_LONG' }`
  - `validateSelection(raw: string): SelectionCheck` — trim trước khi kiểm tra; trả `text` đã trim.

- [ ] **Step 1: Viết test mới cho `shared/text.ts`**

Tạo `extension/src/shared/text.test.ts` với đúng bốn ca đang có trong `content/selection.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { validateSelection, MAX_SELECTION_LENGTH } from './text';

describe('validateSelection', () => {
  it('chấp nhận text bình thường và trim khoảng trắng', () => {
    expect(validateSelection('  renewable  ')).toEqual({ ok: true, text: 'renewable' });
  });

  it('từ chối chuỗi rỗng', () => {
    expect(validateSelection('   ')).toEqual({ ok: false, reason: 'EMPTY' });
  });

  it('chấp nhận đúng ngưỡng tối đa', () => {
    const atLimit = 'a'.repeat(MAX_SELECTION_LENGTH);
    expect(validateSelection(atLimit)).toEqual({ ok: true, text: atLimit });
  });

  it('từ chối khi vượt ngưỡng', () => {
    expect(validateSelection('a'.repeat(MAX_SELECTION_LENGTH + 1)))
      .toEqual({ ok: false, reason: 'TOO_LONG' });
  });
});
```

- [ ] **Step 2: Chạy để thấy nó đỏ**

```bash
npm test -- src/shared/text.test.ts
```

Kỳ vọng: FAIL — `Failed to resolve import "./text"`.

- [ ] **Step 3: Tạo `shared/text.ts`**

```ts
/**
 * Giới hạn cứng phía client, khớp với `TranslationService.MAX_TEXT_LENGTH` ở backend.
 * Đổi số ở đây phải đổi đồng bộ bên backend.
 *
 * Chặn ở client không thay thế chặn ở backend — nó chỉ để khỏi đốt một vòng mạng
 * cho thứ backend chắc chắn từ chối.
 */
export const MAX_SELECTION_LENGTH = 1500;

export type SelectionCheck =
  | { ok: true; text: string }
  | { ok: false; reason: 'EMPTY' | 'TOO_LONG' };

export function validateSelection(raw: string): SelectionCheck {
  const text = raw.trim();
  if (text.length === 0) return { ok: false, reason: 'EMPTY' };
  if (text.length > MAX_SELECTION_LENGTH) return { ok: false, reason: 'TOO_LONG' };
  return { ok: true, text };
}
```

- [ ] **Step 4: Chạy test mới, phải xanh**

```bash
npm test -- src/shared/text.test.ts
```

Kỳ vọng: PASS, 4 ca.

- [ ] **Step 5: Bỏ bản cũ khỏi `content/selection.ts`**

Xoá **dòng 1–13** (`MAX_SELECTION_LENGTH`, `SelectionCheck`, `validateSelection`). Giữ nguyên phần còn lại. Đầu file sau khi sửa:

```ts
const MAX_CONTEXT_LENGTH = 400;

/**
 * Tìm câu chứa đoạn được chọn. Mở rộng sang trái tới dấu kết câu gần nhất và
 * sang phải tới dấu kết câu tiếp theo. Trả null nếu không tìm thấy selection.
 */
export function extractContextSentence(
```

- [ ] **Step 6: Sửa import ở `content/index.ts:1`**

Thay dòng 1 bằng hai dòng:

```ts
import { extractContextSentence } from './selection';
import { validateSelection } from '../shared/text';
```

- [ ] **Step 7: Bỏ `describe('validateSelection')` khỏi `content/selection.test.ts`**

Xoá **dòng 1–22** và thay bằng:

```ts
import { describe, it, expect } from 'vitest';
import { extractContextSentence } from './selection';
```

Phần `describe('extractContextSentence', …)` giữ nguyên hoàn toàn.

- [ ] **Step 8: Chạy toàn bộ test + build**

```bash
npm test
npm run build
```

Kỳ vọng: cả hai xanh. Nếu `tsc` báo còn chỗ nào import `validateSelection` từ `./selection`, sửa nốt chỗ đó — chỉ có `content/index.ts` là hợp lệ theo grep lúc lập plan.

- [ ] **Step 9: Sửa CLAUDE.md ràng buộc số 9**

Thay:

```
9. **Giới hạn 1500 ký tự chặn ở cả hai phía** (`TranslationService.MAX_TEXT_LENGTH` và `content/selection.ts`). Đổi số thì đổi đồng bộ.
```

bằng:

```
9. **Giới hạn 1500 ký tự chặn ở cả hai phía** (`TranslationService.MAX_TEXT_LENGTH` và `shared/text.ts`). Đổi số thì đổi đồng bộ.
```

- [ ] **Step 10: Commit**

```bash
git add extension/src/shared/text.ts extension/src/shared/text.test.ts \
        extension/src/content/selection.ts extension/src/content/selection.test.ts \
        extension/src/content/index.ts CLAUDE.md
git commit -m "refactor(ext): chuyển validateSelection sang shared/text.ts"
```

---

### Task 2: Message `TRANSLATE_TEXT` và xử lý ở service worker

**Files:**
- Modify: `extension/src/shared/messages.ts` (thêm interface sau `TranslateSelectionRequest` ở dòng 6–12, thêm vào union dòng 83–95, thêm vào `ResponseMap` dòng 99–112)
- Modify: `extension/src/background/service-worker.ts` (thêm `case` sau khối `TRANSLATE_SELECTION`, dòng 52–61)
- Modify: `extension/src/background/service-worker.test.ts`

**Interfaces:**
- Consumes: không có gì từ Task 1.
- Produces:
  - `interface TranslateTextRequest { type: 'TRANSLATE_TEXT'; text: string }` trong `shared/messages.ts`
  - Nhánh `ResponseMap['TRANSLATE_TEXT'] = TranslateResult`
  - Service worker trả `TranslateResult` và gán vào `lastResult` (cùng biến `TRANSLATE_SELECTION` dùng), nên `GET_LAST_RESULT` đọc được ngay sau đó.

- [ ] **Step 1: Viết test đỏ trong `service-worker.test.ts`**

Chèn `describe` này ngay trước `describe('định tuyến message Quiz', …)`:

```ts
  describe('định tuyến message dịch', () => {
    it('TRANSLATE_TEXT gọi translate không kèm ngữ cảnh và không kèm trang nguồn', async () => {
      api.translate.mockResolvedValue(RESULT);
      await loadServiceWorker();

      const response = await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });

      // sourceUrl/pageTitle rỗng chứ không phải null: api-client đổi chuỗi rỗng thành
      // undefined, và bản ghi vào sổ từ nhận sourceUrl null. Text gõ tay không có trang nguồn.
      expect(api.translate).toHaveBeenCalledWith({
        text: 'mitigate', contextSentence: null, sourceUrl: '', pageTitle: '',
      });
      expect(response).toMatchObject({ ok: true, data: { sourceText: 'mitigate' } });
    });

    it('TRANSLATE_TEXT cập nhật kết quả gần nhất mà GET_LAST_RESULT đọc', async () => {
      api.translate.mockResolvedValue(RESULT);
      await loadServiceWorker();

      await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });
      const response = await send({ type: 'GET_LAST_RESULT' });

      // Cùng một ô nhớ với đường bôi đen: side panel chỉ có MỘT vùng kết quả.
      expect(response).toMatchObject({ ok: true, data: { sourceText: 'mitigate' } });
    });

    it('lỗi khi dịch trả về dạng { ok: false, error }', async () => {
      api.translate.mockRejectedValue(
        { code: 'GEMINI_QUOTA', message: 'Hết quota Gemini hôm nay.', retryable: false });
      await loadServiceWorker();

      const response = await send({ type: 'TRANSLATE_TEXT', text: 'mitigate' });

      expect(response).toMatchObject({
        ok: false, error: { code: 'GEMINI_QUOTA', retryable: false },
      });
    });
  });
```

- [ ] **Step 2: Chạy để thấy nó đỏ**

```bash
npm test -- src/background/service-worker.test.ts
```

Kỳ vọng: FAIL. `api.translate` không được gọi (`handle()` chưa có nhánh nào khớp nên rơi ra ngoài `switch` và trả `undefined`).

- [ ] **Step 3: Thêm interface vào `shared/messages.ts`**

Ngay sau `TranslateSelectionRequest` (kết thúc ở dòng 12):

```ts
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
```

Thêm vào union (ngay sau `| TranslateSelectionRequest`):

```ts
  | TranslateTextRequest
```

Thêm vào `ResponseMap` (ngay sau dòng `TRANSLATE_SELECTION: TranslateResult;`):

```ts
  TRANSLATE_TEXT: TranslateResult;
```

- [ ] **Step 4: Thêm `case` vào `service-worker.ts`**

Ngay sau khối `case 'TRANSLATE_SELECTION'` (kết thúc ở dòng 61):

```ts
    case 'TRANSLATE_TEXT': {
      // Chuỗi rỗng chứ không phải null cho sourceUrl/pageTitle: api-client đã có sẵn
      // `args.sourceUrl || undefined`, nên rỗng tự biến thành "không có nguồn".
      const result = await client.translate({
        text: request.text,
        contextSentence: null,
        sourceUrl: '',
        pageTitle: '',
      });
      lastResult = result;
      return result;
    }
```

- [ ] **Step 5: Chạy test, phải xanh**

```bash
npm test -- src/background/service-worker.test.ts
```

Kỳ vọng: PASS, 3 ca mới.

- [ ] **Step 6: Chạy toàn bộ + build**

```bash
npm test
npm run build
```

Kỳ vọng: cả hai xanh. `switch` trong `handle()` không có `default`, nên nếu quên nhánh nào `tsc` sẽ báo — đó là lưới bắt lỗi chính của task này.

- [ ] **Step 7: Commit**

```bash
git add extension/src/shared/messages.ts \
        extension/src/background/service-worker.ts \
        extension/src/background/service-worker.test.ts
git commit -m "feat(ext): message TRANSLATE_TEXT cho luồng nhập tay"
```

---

### Task 3: Nâng `result` và `loaded` từ `TranslateTab` lên `App`

Chưa thêm ô nhập. Task này chỉ đổi chỗ chứa state để Task 4 có chỗ đặt `draft`.

Lý do phải làm riêng: effect `GET_LAST_RESULT` đang nằm trong `TranslateTab`. Đổi tab làm component unmount, nên effect chạy lại mỗi lần quay lại. Để nguyên chỗ cũ thì Task 4 thêm `draft` bao nhiêu cũng vô ích — nó bị ghi đè ngay.

**Files:**
- Modify: `extension/src/sidepanel/TranslateTab.tsx` (bỏ `useEffect` + hai state, nhận props)
- Modify: `extension/src/sidepanel/App.tsx`
- Modify: `extension/src/sidepanel/TranslateTab.test.tsx` (đổi cách render 9 ca hiện có)
- Create: `extension/src/sidepanel/App.test.tsx`

**Interfaces:**
- Consumes: `TRANSLATE_TEXT` chưa dùng ở task này.
- Produces:
  - `interface TranslateTabProps { result: TranslateResult | null; loaded: boolean }`
  - `TranslateTab` là component thuần hiển thị, không còn tự gọi `GET_LAST_RESULT`.
  - `App` sở hữu `result` / `loaded`; Task 4 thêm `draft` vào cùng chỗ.

- [ ] **Step 1: Viết `App.test.tsx` (đỏ)**

Tạo `extension/src/sidepanel/App.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from './App';
import type { TranslatePayload, TranslateResult } from '../shared/types';

const lastResult: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'was resiliented',
  payload: {
    term: 'resilient', lemma: 'resilient', pos: 'adj', meaning_vi: 'kiên cường',
  } as unknown as TranslatePayload,
};

/** Mock đủ cho App + mọi tab con mà test này chạm tới. */
function mockBackend(last: TranslateResult | null) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      switch (request.type) {
        case 'GET_LAST_RESULT':
          return { ok: true, data: last };
        case 'SEARCH_VOCAB':
          return { ok: true, data: { content: [], totalElements: 0, totalPages: 0, number: 0 } };
        default:
          return { ok: true, data: null };
      }
    },
  );
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('đọc kết quả gần nhất một lần và hiện ở tab Dịch', async () => {
    mockBackend(lastResult);
    render(<App />);

    expect(await screen.findByText('kiên cường')).toBeInTheDocument();
    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith({ type: 'GET_LAST_RESULT' });
  });
});
```

- [ ] **Step 2: Chạy để chốt hành vi hiện tại**

```bash
npm test -- src/sidepanel/App.test.tsx
```

Kỳ vọng: **PASS** — đây không phải test TDD-đỏ mà là test bảo vệ. Hành vi này đang đúng nhờ effect trong `TranslateTab`; task này chỉ đổi chỗ chứa state nên nó phải xanh cả trước lẫn sau. Xanh từ đầu là đúng ý; đỏ từ đầu nghĩa là mock sai, sửa mock trước khi đi tiếp.

- [ ] **Step 3: Đổi `TranslateTab.tsx` sang nhận props**

Thay toàn bộ phần đầu file (dòng 1–19) bằng:

```tsx
import { useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { PayloadView } from './PayloadViews';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

export interface TranslateTabProps {
  result: TranslateResult | null;
  loaded: boolean;
}

export function TranslateTab({ result, loaded }: TranslateTabProps) {
  const [status, setStatus] = useState<Status>(null);
```

Phần còn lại (`save()`, hai nhánh return, JSX) giữ nguyên hoàn toàn. Xoá `useEffect` khỏi import — `noUnusedLocals` sẽ bắt nếu quên.

- [ ] **Step 4: Đưa state và effect lên `App.tsx`**

Thay dòng 1 và thân `App()`:

```tsx
import { useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { ReviewTab } from './ReviewTab';
import { QuizTab } from './QuizTab';
```

Trong `App()`, ngay sau `const [tab, setTab] = useState<Tab>('translate');`:

```tsx
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Ở App chứ không ở TranslateTab: đổi tab làm TranslateTab unmount, nên effect đặt
  // trong đó sẽ chạy lại mỗi lần quay lại tab Dịch và ghi đè state người dùng đang gõ dở.
  // Ở đây nó chạy đúng một lần cho mỗi lần mở side panel.
  useEffect(() => {
    void (async () => {
      const response = await sendToBackground({ type: 'GET_LAST_RESULT' });
      if (response.ok) setResult(response.data);
      setLoaded(true);
    })();
  }, []);
```

Và dòng render tab Dịch:

```tsx
        {tab === 'translate' && <TranslateTab result={result} loaded={loaded} />}
```

- [ ] **Step 5: Sửa `TranslateTab.test.tsx` cho khớp props**

Thay helper `mockLastResult` (dòng 7–15) bằng:

```tsx
function mockSave(response: unknown) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async () => response,
  );
}

const SAVE_OK = { ok: true, data: { id: 1, alreadyExists: false } };
```

Sửa 9 call site theo bảng này:

| Cũ | Mới |
|---|---|
| `mockLastResult(null); render(<TranslateTab />);` | `mockSave(SAVE_OK); render(<TranslateTab result={null} loaded />);` |
| `mockLastResult(enViWord); render(<TranslateTab />);` | `mockSave(SAVE_OK); render(<TranslateTab result={enViWord} loaded />);` |
| `mockLastResult({…inline…}); render(<TranslateTab />);` | `mockSave(SAVE_OK); render(<TranslateTab result={{…inline…}} loaded />);` |

Ba ca cuối (`bấm Lưu từ…`, `báo Đã có trong sổ…`, `hiện thông báo lỗi khi lưu…`) đổi mock thành:

```tsx
    mockSave(SAVE_OK);                                     // ca 1
    mockSave({ ok: true, data: { id: 1, alreadyExists: true } });   // ca 2
    mockSave({ ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true } });  // ca 3
```

và render với `result={enViWord} loaded`.

- [ ] **Step 6: Chạy toàn bộ + build**

```bash
npm test
npm run build
```

Kỳ vọng: cả hai xanh, `App.test.tsx` vẫn xanh như bước 2 — nghĩa là đổi chỗ state không đổi hành vi.

- [ ] **Step 7: Commit**

```bash
git add extension/src/sidepanel/App.tsx extension/src/sidepanel/App.test.tsx \
        extension/src/sidepanel/TranslateTab.tsx extension/src/sidepanel/TranslateTab.test.tsx
git commit -m "refactor(ext): App giữ kết quả dịch, TranslateTab thành component thuần"
```

---

### Task 4: Ô nhập text và nút Dịch

**Files:**
- Modify: `extension/src/sidepanel/TranslateTab.tsx`
- Modify: `extension/src/sidepanel/App.tsx`
- Modify: `extension/src/sidepanel/TranslateTab.test.tsx`
- Modify: `extension/src/sidepanel/App.test.tsx`

**Interfaces:**
- Consumes:
  - `TranslateTextRequest` / `ResponseMap['TRANSLATE_TEXT']` (Task 2)
  - `validateSelection`, `MAX_SELECTION_LENGTH` từ `../shared/text` (Task 1)
  - `TranslateTabProps` (Task 3)
- Produces:
  - `TranslateTabProps` mở rộng thành `{ draft, onDraftChange, result, onResult, loaded }`
  - Class CSS Task 5 phải style: `.translate-input`, `.translate-input-foot`, `.counter`, `.counter.over`

- [ ] **Step 1: Viết test đỏ trong `TranslateTab.test.tsx`**

Thêm import `useState` từ `react` ở đầu file, rồi thêm harness có state (controlled component không tự cập nhật được với `vi.fn()`):

```tsx
function StatefulTab({ initialDraft = '', initialResult = null }: {
  initialDraft?: string;
  initialResult?: TranslateResult | null;
}) {
  const [draft, setDraft] = useState(initialDraft);
  const [result, setResult] = useState<TranslateResult | null>(initialResult);
  return (
    <TranslateTab
      draft={draft} onDraftChange={setDraft}
      result={result} onResult={setResult} loaded
    />
  );
}

function mockSend(handler: (request: { type: string }) => unknown) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => handler(request),
  );
}

const BOX = /Text cần dịch/i;
```

**Sửa luôn ca trạng thái rỗng đang có** (`hiện trạng thái rỗng khi chưa dịch gì`). Task này đổi câu đó, nên regex cũ `/Bôi đen một đoạn text/i` sẽ không khớp nữa:

```tsx
    expect(await screen.findByText(/nhập vào ô trên rồi bấm Dịch/i)).toBeInTheDocument();
```

Thêm `describe` mới ở cuối file:

```tsx
describe('ô nhập text trong tab Dịch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('bấm Dịch gửi TRANSLATE_TEXT với text đã trim và hiện kết quả', async () => {
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? { ok: true, data: enViWord }
      : { ok: true, data: null });
    render(<StatefulTab />);

    await userEvent.type(screen.getByLabelText(BOX), '  renewable  ');
    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    expect(chrome.runtime.sendMessage)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
    expect(await screen.findByText('tái tạo')).toBeInTheDocument();
  });

  it('ô trống thì nút Dịch tắt', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab />);

    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it('vượt 1500 ký tự: đếm chuyển đỏ, nút tắt, Ctrl+Enter cũng KHÔNG gửi message', async () => {
    mockSend(() => ({ ok: true, data: null }));
    render(<StatefulTab initialDraft={'a'.repeat(1501)} />);

    expect(screen.getByText('1501/1500')).toHaveClass('over');
    expect(screen.getByRole('button', { name: 'Dịch' })).toBeDisabled();

    // Phím tắt không đi qua nút, nên nút disabled một mình không chặn được nó.
    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled();
  });

  it('Ctrl+Enter gửi giống bấm nút', async () => {
    mockSend((r) => r.type === 'TRANSLATE_TEXT'
      ? { ok: true, data: enViWord }
      : { ok: true, data: null });
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByLabelText(BOX));
    await userEvent.keyboard('{Control>}{Enter}{/Control}');

    expect(chrome.runtime.sendMessage)
      .toHaveBeenCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
  });

  it('lỗi retry được: hiện Thử lại và gửi lại ĐÚNG text đã gửi, không phải text trong ô', async () => {
    mockSend(() => ({
      ok: false,
      error: { code: 'GEMINI_UNAVAILABLE', message: 'Gemini tạm thời lỗi', retryable: true },
    }));
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));
    expect(await screen.findByText(/Gemini tạm thời lỗi/)).toBeInTheDocument();

    // Người dùng gõ thêm vào ô TRƯỚC khi bấm Thử lại.
    await userEvent.type(screen.getByLabelText(BOX), ' energy');
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }));

    expect(chrome.runtime.sendMessage)
      .toHaveBeenLastCalledWith({ type: 'TRANSLATE_TEXT', text: 'renewable' });
  });

  it('lỗi không retry được thì không có nút Thử lại', async () => {
    mockSend(() => ({
      ok: false,
      error: { code: 'TEXT_TOO_LONG', message: 'Đoạn text quá dài', retryable: false },
    }));
    render(<StatefulTab initialDraft="renewable" />);

    await userEvent.click(screen.getByRole('button', { name: 'Dịch' }));

    expect(await screen.findByText(/Đoạn text quá dài/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thử lại' })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Thêm test giữ nháp vào `App.test.tsx`**

Thêm `import userEvent from '@testing-library/user-event';` và hai ca:

```tsx
  it('điền sẵn ô nhập bằng text của kết quả gần nhất', async () => {
    mockBackend(lastResult);
    render(<App />);

    expect(await screen.findByDisplayValue('was resiliented')).toBeInTheDocument();
  });

  it('đổi sang tab khác rồi quay lại vẫn giữ nguyên text đang gõ dở', async () => {
    mockBackend(null);
    render(<App />);

    await userEvent.type(await screen.findByLabelText(/Text cần dịch/i), 'resilient');

    await userEvent.click(screen.getByRole('tab', { name: 'Sổ từ' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Dịch' }));

    // Khoá quyết định "state ở App": đẩy state ngược xuống TranslateTab cho gọn
    // sẽ làm ca này đỏ ngay.
    expect(screen.getByLabelText(/Text cần dịch/i)).toHaveValue('resilient');
  });
```

- [ ] **Step 3: Chạy để thấy đỏ**

```bash
npm test -- src/sidepanel/TranslateTab.test.tsx src/sidepanel/App.test.tsx
```

Kỳ vọng: FAIL — `Unable to find a label with the text of: /Text cần dịch/i`.

- [ ] **Step 4: Viết `TranslateTab.tsx`**

Thay toàn bộ file bằng:

```tsx
import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { sendToBackground } from '../shared/messages';
import { MAX_SELECTION_LENGTH, validateSelection } from '../shared/text';
import type { ApiError, TranslateResult } from '../shared/types';
import { PayloadView } from './PayloadViews';

type Status = { text: string; kind: 'ok' | 'bad' } | null;

/** Lỗi dịch kèm ĐÚNG đoạn text đã gửi, để "Thử lại" không đọc lại ô nhập. */
type Failure = { error: ApiError; text: string } | null;

export interface TranslateTabProps {
  draft: string;
  onDraftChange: (value: string) => void;
  result: TranslateResult | null;
  onResult: (result: TranslateResult) => void;
  loaded: boolean;
}

export function TranslateTab({
  draft, onDraftChange, result, onResult, loaded,
}: TranslateTabProps) {
  const [status, setStatus] = useState<Status>(null);
  const [translating, setTranslating] = useState(false);
  const [failure, setFailure] = useState<Failure>(null);

  const check = validateSelection(draft);
  const tooLong = !check.ok && check.reason === 'TOO_LONG';

  async function translate(text: string) {
    setTranslating(true);
    setFailure(null);
    setStatus(null);
    const response = await sendToBackground({ type: 'TRANSLATE_TEXT', text });
    setTranslating(false);
    if (response.ok) onResult(response.data);
    else setFailure({ error: response.error, text });
  }

  // Chặn ở đây chứ không chỉ dựa vào `disabled` của nút: Ctrl+Enter không đi qua nút.
  function submit() {
    if (!check.ok || translating) return;
    void translate(check.text);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      submit();
    }
  }

  async function save() {
    if (!result) return;
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_WORD', result, tags: [] });
    setStatus(response.ok
      ? {
          text: response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ từ',
          kind: 'ok',
        }
      : { text: response.error.message, kind: 'bad' });
  }

  if (!loaded) return <p className="empty">Đang tải…</p>;

  return (
    <div className="translate-tab">
      <div className="translate-input">
        <textarea
          rows={3}
          value={draft}
          aria-label="Text cần dịch"
          placeholder="Nhập hoặc dán text để dịch…"
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="translate-input-foot">
          {/* Đếm theo độ dài ĐÃ TRIM để khớp đúng thứ validateSelection kiểm tra —
              nếu không, một đoạn 1501 ký tự có khoảng trắng cuối sẽ hiện đỏ mà vẫn dịch được. */}
          <span className={tooLong ? 'counter over' : 'counter'}>
            {draft.trim().length}/{MAX_SELECTION_LENGTH}
          </span>
          <button type="button" disabled={!check.ok || translating} onClick={submit}>
            {translating ? 'Đang dịch…' : 'Dịch'}
          </button>
        </div>
        {failure && (
          <p className="status bad">
            {failure.error.message}
            {failure.error.retryable && (
              <button type="button" onClick={() => void translate(failure.text)}>
                Thử lại
              </button>
            )}
          </p>
        )}
      </div>

      {result ? (
        <>
          <PayloadView result={result} />
          <div className="actions">
            <button type="button" onClick={() => void save()}>Lưu từ</button>
            {result.cached && <span className="cached-hint">từ cache</span>}
            {status && <p className={`status ${status.kind}`}>{status.text}</p>}
          </div>
        </>
      ) : (
        <p className="empty">Bôi đen text trên trang, hoặc nhập vào ô trên rồi bấm Dịch.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Nối `draft` ở `App.tsx`**

Thêm state và mở rộng effect:

```tsx
  const [draft, setDraft] = useState('');
```

Trong effect, sau `if (response.ok) setResult(response.data);`:

```tsx
      // Tự điền để sửa lại đoạn bôi đen hụt rồi dịch lại, không phải gõ từ đầu.
      // Chỉ chạy một lần mỗi lần mở panel — hết lần này là nháp thuộc về người dùng.
      if (response.ok && response.data) setDraft(response.data.sourceText);
```

Và dòng render:

```tsx
        {tab === 'translate' && (
          <TranslateTab
            draft={draft} onDraftChange={setDraft}
            result={result} onResult={setResult} loaded={loaded}
          />
        )}
```

- [ ] **Step 6: Chạy test, phải xanh**

```bash
npm test -- src/sidepanel/TranslateTab.test.tsx src/sidepanel/App.test.tsx
```

Kỳ vọng: PASS toàn bộ. Nếu thấy cảnh báo `act(...)` từ `App.test.tsx`, nó đến từ debounce 300ms của `VocabTab` khi đổi tab — cảnh báo, không phải fail. Nếu nó làm ca đỏ, bọc assertion cuối bằng `await waitFor(() => …)`.

- [ ] **Step 7: Chạy toàn bộ + build**

```bash
npm test
npm run build
```

Kỳ vọng: cả hai xanh. Chín ca cũ trong `TranslateTab.test.tsx` (sửa ở Task 3) vẫn phải xanh — chúng render với `result` có sẵn nên vẫn thấy `PayloadView`.

- [ ] **Step 8: Commit**

```bash
git add extension/src/sidepanel/TranslateTab.tsx extension/src/sidepanel/TranslateTab.test.tsx \
        extension/src/sidepanel/App.tsx extension/src/sidepanel/App.test.tsx
git commit -m "feat(ext): ô nhập text thủ công trong tab Dịch"
```

---

### Task 5: CSS và README

**Files:**
- Modify: `extension/src/sidepanel/styles.css` (chèn trước khối `/* Tab sổ từ */` ở dòng ~242)
- Modify: `README.md:43`

**Interfaces:**
- Consumes: các class do Task 4 sinh ra — `.translate-input`, `.translate-input-foot`, `.counter`, `.counter.over`.
- Produces: không có gì cho task sau (đây là task cuối).

- [ ] **Step 1: Thêm CSS**

Chèn ngay trước khối `/* Tab sổ từ */`:

```css
/* ============================================================
   Ô nhập text để dịch
   ============================================================ */
.translate-input { margin-bottom: 14px; }

.translate-input textarea {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 13.5px;
  line-height: 1.5;
  resize: vertical;
}
.translate-input textarea:focus {
  outline: 2px solid var(--accent);
  outline-offset: -1px;
}

.translate-input-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.translate-input-foot .counter { color: var(--text-3); font-size: 12px; }
.translate-input-foot .counter.over { color: var(--danger); }
.translate-input-foot button {
  padding: 7px 15px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 13.5px;
  font-weight: 560;
  cursor: pointer;
}
.translate-input-foot button:hover:not(:disabled) { filter: brightness(1.08); }
.translate-input-foot button:disabled { opacity: 0.45; cursor: default; }

.translate-input .status.bad { margin-top: 8px; }
.translate-input .status.bad button {
  margin-left: 6px;
  padding: 2px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
```

- [ ] **Step 2: Cập nhật README**

Thay dòng 43:

```
Bôi đen text bất kỳ trên web để dịch. Bấm `+` để lưu vào sổ, `⤢` để mở side panel.
```

bằng:

```
Bôi đen text bất kỳ trên web để dịch. Bấm `+` để lưu vào sổ, `⤢` để mở side panel.

Không có sẵn text trên trang thì mở side panel và gõ/dán thẳng vào ô trên tab **Dịch**
(`Ctrl/Cmd+Enter` để dịch). Ô này được điền sẵn đoạn vừa bôi đen, nên bôi hụt một chút
thì sửa lại rồi dịch lại, không phải gõ từ đầu.
```

- [ ] **Step 3: Kiểm tra bằng mắt trên extension thật**

```bash
cd extension && npm run build
```

Nạp lại extension ở `chrome://extensions` (Load unpacked → `extension/dist`), mở side panel và kiểm:

1. Ô nhập hiện đúng, textarea kéo giãn được theo chiều dọc.
2. Gõ 1 từ → nút `Dịch` sáng → bấm → ra kết quả tra từ.
3. Dán một đoạn dài > 1500 → bộ đếm đỏ, nút `Dịch` mờ và bấm không được.
4. Bôi đen trên trang → bấm icon → `⤢` mở panel → ô nhập điền sẵn đúng đoạn đó.
5. Tắt backend (`docker compose stop app`) → bấm `Dịch` → hiện lỗi kèm nút `Thử lại`.

Backend phải đang chạy cho bước 2 và 4: `docker compose up -d`.

- [ ] **Step 4: Chạy lần cuối**

```bash
npm test
npm run build
```

Dán output thật của cả hai lệnh vào báo cáo. Không được nói "xong" khi chưa có output.

- [ ] **Step 5: Commit**

```bash
git add extension/src/sidepanel/styles.css README.md
git commit -m "feat(ext): style ô nhập text và cập nhật README"
```

---

## Kiểm tra sau cùng

Trước khi báo xong, đối chiếu với spec:

- [ ] `npm test` xanh, có output thật
- [ ] `npm run build` xanh, có output thật
- [ ] Không có bản sao thứ ba của số `1500` trong `extension/src/` (`grep -rn "1500" extension/src/`)
- [ ] Không file Java, migration, hay `prompts/*.md` nào bị đụng (`git diff --stat main`)
- [ ] Không dependency mới trong `extension/package.json`
