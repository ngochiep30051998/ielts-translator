# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Ngôn ngữ

Comment code, message lỗi, text hiển thị và trả lời người dùng viết bằng **tiếng Việt đủ dấu** (đúng như code hiện tại). Tên class/biến/hàm/package giữ tiếng Anh. Lưu UTF-8.

## Lệnh thường dùng

```bash
# Backend (cwd = backend/)
mvn test                              # cần Docker chạy sẵn cho Testcontainers
mvn test -Dtest=LanguageDetectorTest  # một test class
mvn -q compile                        # kiểm tra nhanh khi không đổi test

# Extension (cwd = extension/)
npm test                              # vitest run
npm test -- src/content/selection.test.ts   # một file test
npm run build                         # tsc --noEmit && vite build — TYPE CHECK CHỈ Ở ĐÂY
npm run icons                         # sinh lại public/icons/* từ scripts/make-icons.mjs

# Chạy hệ thống (cwd = thư mục gốc)
docker compose up -d --build          # toàn bộ backend + Postgres
docker compose up -d db               # chỉ Postgres, app chạy từ IDE (run config "Backend local")
curl http://127.0.0.1:8080/api/health # phải trả geminiConfigured: true
```

`npm run build` là nơi **duy nhất** chạy type check. Test xanh mà build đỏ vẫn là hỏng — luôn chạy cả hai trước khi báo xong.

Surefire được cấu hình include cả `**/*Test.java` và `**/*IT.java`. Đặt sai tên file test = test bị bỏ qua **im lặng**.

**Không bao giờ chạy `docker compose down -v`** — xoá volume `ielts_pgdata`, tức xoá sạch sổ từ vựng của người dùng. Cần reset DB thì hỏi trước và nhắc export CSV (`GET /api/vocab/export.csv`).

## Kiến trúc

Hai nửa chạy hoàn toàn trên máy cá nhân: Chrome extension MV3 (`extension/`) gọi Spring Boot ở `127.0.0.1:8080` (`backend/`), backend gọi Gemini.

**Đường dữ liệu một lượt dịch:**

```
content/selection.ts (validate + trích context)
  → content/index.ts (bubble trong Shadow DOM)
  → shared/messages.ts (union type ExtensionRequest)
  → background/service-worker.ts
  → background/api-client.ts (fetch)
  → TranslateController → TranslationService
       → LanguageDetector (EN_VI | VI_EN) + Mode.of (WORD nếu ≤3 token, else SENTENCE)
       → PromptLoader chọn prompts/{en-vi|vi-en}-{word|sentence}.md
       → LookupCache (hit → trả luôn) hoặc GeminiClient.generateJson + lưu cache
```

Bốn tổ hợp direction × mode sinh ra **bốn hình dạng payload JSON khác nhau** (`TranslationSchemas` phía backend, `shared/types.ts` phía extension). Mọi UI hiển thị kết quả phải phân nhánh theo `direction` + `mode`.

**Backend** — package theo feature: `common` (lỗi, CORS, `common/gemini`), `health`, `translation` (+ `translation/cache`), `vocabulary`. Java 21, Spring Boot 3.4.1, Web MVC (không WebFlux), JPA/Hibernate + Postgres 16 + Flyway, hypersistence-utils để map JSONB. **Không Lombok**: constructor injection thủ công, `record` cho DTO, field `final`.

**Extension** — bốn surface (`content/`, `background/`, `sidepanel/`, `options/`) + `shared/`. React 18 + TS 5.7 (`strict` **và** `noUnusedLocals`), Vite 5 + `@crxjs/vite-plugin`, manifest sinh từ `manifest.config.ts` (không có `manifest.json` viết tay). **Không có thư viện UI/state nào** — CSS viết tay (`sidepanel/styles.css`, CSS-in-TS ở `content/bubble.css.ts`). Test: Vitest + RTL + jsdom; `vitest.setup.ts` stub sẵn `chrome.storage.local`/`runtime`/`sidePanel` — cần API chrome mới thì bổ sung vào stub đó, đừng stub rải rác.

## Ràng buộc — vi phạm là hỏng thật, không phải vấn đề phong cách

1. **Content script / side panel / Options KHÔNG BAO GIỜ gọi HTTP.** Mọi request đi qua service worker (`background/api-client.ts`). `host_permissions` chỉ cấp cho extension context; content script chạy trong origin của trang lạ.

2. **Hợp đồng message ở `shared/messages.ts`.** Luồng mới = thêm interface request + thêm vào union `ExtensionRequest` + thêm vào `ResponseMap`, rồi mới xử lý ở service worker. Không gửi message ad-hoc bằng object rời.

3. **`shared/types.ts` là bản gương của DTO backend.** Backend đổi field → sửa ở đây trước, TypeScript sẽ chỉ ra mọi chỗ vỡ. Đừng bịa field backend không có.

4. **Lỗi đi một đường duy nhất, hình dạng `{ code, message, retryable }`.** Backend: ném `AppException.of(ErrorCode.X, "thông điệp tiếng Việt")`, `GlobalExceptionHandler.statusFor()` map sang HTTP status (switch exhaustive — thêm `ErrorCode` mới mà quên nhánh là fail compile; đừng thêm `default` để né). Mã hợp lệ: `GEMINI_QUOTA`, `GEMINI_UNAVAILABLE`, `PARSE_ERROR`, `TEXT_TOO_LONG`, `NOT_FOUND`, `INTERNAL`. UI phải phân biệt lỗi retry được và lỗi vĩnh viễn.

5. **Sửa nội dung prompt PHẢI tăng `version:` ở đầu file `resources/prompts/*.md`.** Version nằm trong cache key — đó là cách duy nhất làm cache cũ hết hiệu lực. Cache key = text + context + direction + mode + model + prompt version, nối theo dạng `độDài:nộiDung|`; đừng đổi cách nối mà chưa đọc javadoc `TranslationService.appendField`.

6. **`application.yml` không hardcode giá trị nào** — mọi mục viết `${BIEN:mặc-định}`, default trong file chính là cấu hình chạy local. Thêm config mới → thêm vào `.env.example` **và** bảng "Biến môi trường" trong `README.md`. JDBC URL ghép phẳng từ `DB_HOST`/`DB_PORT`/`DB_NAME`; không tái tạo biến `DB_URL`.

7. **CORS chỉ mở cho `EXTENSION_ID`** (`CorsConfig`). ID cố định nhờ field `key` trong `manifest.config.ts` + `key.pem` — đừng xoá, đừng tái sinh, đừng in `key.pem` ra chat. ID đổi → `.env` sai → backend chặn CORS → cả extension chết.

8. **Migration Flyway là append-only.** Không sửa file `V*.sql` đã chạy; thêm version mới, và cập nhật entity JPA trong cùng thay đổi (`ddl-auto: validate` sẽ fail khi lệch).

9. **Giới hạn 1500 ký tự chặn ở cả hai phía** (`TranslationService.MAX_TEXT_LENGTH` và `content/selection.ts`). Đổi số thì đổi đồng bộ.

10. **`host_permissions` ghim `http://127.0.0.1:8080/*`.** Đổi `APP_PORT` phải sửa cả manifest **và** `backendUrl` mặc định trong `shared/settings.ts` / trang Options — sửa một chỗ là hỏng im lặng.

11. **Bubble render trong Shadow DOM** (`content/bubble.ts`) — cách duy nhất tránh CSS trang chủ đè lên. Đừng chèn thẳng vào DOM trang hay thêm `<link>` toàn cục.

12. **Không thêm dependency mới** nếu chưa nêu lý do và được đồng ý. Dự án cố ý gọn: backend không Lombok/MapStruct, extension chỉ React + Vite + Vitest.

## Quy ước test

- **Backend**: `*Test.java` = unit, không cần Docker (`LanguageDetectorTest`, `PromptLoaderTest`, `CsvExporterTest`). `*IT.java` = integration, kế thừa `AbstractPostgresIT` (Testcontainers Postgres dùng chung một container), WireMock giả lập Gemini (`GEMINI_BASE_URL`).
- **Extension**: test đặt cạnh file được test (`Options.test.tsx` cạnh `Options.tsx`). Query theo vai trò/nhãn người dùng thấy (RTL), đừng bám class CSS hay cấu trúc DOM.
- Dùng skill `superpowers:test-driven-development` khi viết code, `superpowers:systematic-debugging` khi sửa bug, `superpowers:verification-before-completion` trước khi báo xong. Không nói "đã xong / đã fix / test pass" khi chưa dán được output lệnh thật.

## Bẫy cấu hình đã biết

- **`.env` ở thư mục gốc được nạp bởi `application.yml`, không phải file profile-specific.** Profile chỉ bật khi dùng đúng run config; bấm mũi tên xanh cạnh `main` trong IntelliJ sinh config tạm không có profile nào. `spring.config.import` khai hai ứng viên (`../.env` và `./.env`) vì working directory khác nhau tuỳ cách chạy.
- **`POSTGRES_*` chỉ có tác dụng lần khởi tạo data directory đầu tiên.** Đổi `DB_NAME`/`DB_USER`/`DB_PASSWORD` khi volume đã tồn tại → container giữ giá trị cũ, app nối bằng giá trị mới và fail xác thực.
- **`DB_PORT`/`APP_PORT` chỉ đổi cổng publish trên host.** Trong mạng compose db luôn 5432, app luôn 8080.
- `testcontainers.version` bị override lên 1.21.4 trong `pom.xml` (bản mặc định của Boot 3.4.1 mis-negotiate API version với Docker Desktop mới) — đừng gỡ.

## Ranh giới làm việc

- **Không tự commit/push/tạo PR** trừ khi người dùng yêu cầu. Nhánh hiện tại là `main` — cảnh báo trước khi commit.
- Ranh giới `backend/` ↔ `extension/` tách sạch: thay đổi chạm cả hai phía thì **chốt hợp đồng API trước** (tên field, kiểu, status code, mã lỗi) rồi mới sửa song song.
- Repo có 5 agent chuyên trách (`.claude/agents/`: `pm`, `techlead`, `senior-backend`, `senior-frontend`, cộng `senior-ba` global) và skill `team` điều phối. Việc nhỏ, một phía, đã rõ phải làm gì → tự làm, đừng gọi team.
