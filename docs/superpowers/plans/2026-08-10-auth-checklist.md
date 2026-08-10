# Đăng nhập + đa thiết bị — checklist bàn giao

**Ngày:** 2026-08-10
**Trạng thái code:** đã viết xong toàn bộ 17 task của
`docs/superpowers/plans/2026-08-10-auth-multi-user.md`, đã ghi thẳng vào repo. **Chưa commit
git** (CLAUDE.md: không tự commit).

---

## Đã kiểm chứng được / chưa kiểm chứng được

| Việc | Kết quả |
|---|---|
| `npm test` (extension) | ✅ **217/217 pass**, 18 file |
| `npm run build` (tsc --noEmit + vite) | ✅ pass |
| Type-check Java (main + test) | ✅ **0 lỗi** — javac chạy với một bộ stub API dựng riêng |
| `mvn test` (backend, Testcontainers) | ❌ **CHƯA CHẠY** — sandbox chặn Maven Central (403) |

**Về bộ stub Java:** không có Maven thì không có Spring/JPA/JUnit để biên dịch, nên tôi viết
một bộ stub API (~95 file, `jakarta.*`, `org.springframework.*`, Jackson, JUnit, AssertJ,
Mockito, MockMvc, WireMock, Testcontainers) rồi biên dịch **toàn bộ** `src/main` +
`src/test` chống lại nó. Baseline trên code chưa sửa là 0 lỗi, nên mọi lỗi xuất hiện sau đó
đều là lỗi thật của tôi — và tôi đã sửa hết. Bộ stub đó nằm trong sandbox, **không** vào repo.

Điều này chứng minh: cú pháp đúng, tên method/field khớp nhau qua mọi file, switch exhaustive,
generic khớp. Nó **không** chứng minh: câu HQL/native chạy đúng, Spring wiring lên được, hành
vi test đúng. Đó là việc của `mvn test`.

---

## A. Trước khi chạm vào bất cứ thứ gì

- [ ] **`rm .git/index.lock`** — còn sót từ lượt trước, không xoá thì mọi lệnh git đều kẹt.
- [ ] **Sao lưu DB thật.** Đây là điều kiện bắt buộc, không phải khuyến nghị:
      ```bash
      docker compose exec -T db pg_dump -U ielts ielts | gzip > ~/ielts-backup-$(date +%F).sql.gz
      gunzip -t ~/ielts-backup-*.sql.gz && echo "bản sao lưu đọc được"
      ```
- [ ] Xoá `_to_delete/ielts.tgz` (bản tar tôi dùng để chuyển repo sang sandbox).
- [ ] `git status` xem 87 file đã về đúng chỗ, `git diff` đọc lướt V6 và `MultiUserIsolationIT`.

## B. Google Cloud Console

- [ ] Lấy **EXTENSION_ID** ở `chrome://extensions` (cố định nhờ field `key` trong manifest).
- [ ] Tạo OAuth client kiểu **Web application** (KHÔNG phải "Chrome Extension").
- [ ] Authorized redirect URI — dán **chính xác**, có dấu `/` cuối:
      `https://<EXTENSION_ID>.chromiumapp.org/`
- [ ] Màn hình đồng ý (OAuth consent screen): scope `openid`, `email`, `profile`. Để chế độ
      Testing và thêm email của nhóm vào Test users là đủ cho vài người quen.
- [ ] Ghi lại **Client ID** và **Client secret**.

## C. Điền cấu hình

- [ ] `.env` ở thư mục gốc (mẫu ở `.env.example`):
      ```
      AUTH_GOOGLE_CLIENT_ID=...
      AUTH_GOOGLE_CLIENT_SECRET=...
      AUTH_ALLOWED_EMAILS=ban@gmail.com,ban-cua-ban@gmail.com
      AUTH_BOOTSTRAP_EMAIL=ban@gmail.com
      ```
- [ ] **`AUTH_BOOTSTRAP_EMAIL` phải là email Google bạn sẽ dùng để đăng nhập lần đầu.**
      Toàn bộ sổ từ hiện có sẽ thuộc về nó. Gõ sai thì sổ từ nằm ở một tài khoản không ai
      vào được, và Flyway **không chạy lại** để sửa.
- [ ] `extension/.env`: `VITE_GOOGLE_CLIENT_ID=` (cùng client id; **không** có secret).
- [ ] `Caddyfile`: đổi `ielts.example.com` thành domain thật.
- [ ] `extension/manifest.config.ts`: đổi `https://ielts.example.com/*` trong
      `host_permissions` thành domain thật. **Bỏ qua bước này thì extension chết im lặng
      sau khi deploy** — không lỗi mạng, không lỗi CORS, fetch chỉ đơn giản không đi.

## D. Chạy test (phần tôi không chạy được)

- [ ] `cd backend && mvn test` — cần Docker chạy sẵn cho Testcontainers.
- [ ] Nếu đỏ, gửi tôi output; phần lớn khả năng nằm ở câu HQL/native mới hoặc Spring wiring.
- [ ] `cd extension && npm test && npm run build` — chạy lại trên máy bạn để chắc.

Test đáng đọc kết quả nhất, theo thứ tự: `AuthMigrationIT` (dữ liệu cũ có mất không),
`MultiUserIsolationIT` (người này có đọc được dữ liệu người kia không), `SessionFilterIT`.

## E. Diễn tập migration trên bản sao — LÀM TRƯỚC KHI CHẠM DB THẬT

```bash
createdb ielts_rehearsal
gunzip -c ~/ielts-backup-*.sql.gz | psql ielts_rehearsal
psql ielts_rehearsal -c "SELECT count(*) FROM vocab_entry;"        # ghi lại con số này

DB_NAME=ielts_rehearsal AUTH_BOOTSTRAP_EMAIL=<email-thật-của-bạn> \
  mvn -f backend/pom.xml spring-boot:run
# Ctrl-C sau khi log báo Flyway chạy xong V6

psql ielts_rehearsal -c "SELECT count(*), count(user_id) FROM vocab_entry;"
```

- [ ] Hai con số bằng nhau **và** bằng số ghi lại lúc đầu. Lệch một hàng cũng dừng lại.
- [ ] `psql ielts_rehearsal -c "SELECT email, google_sub FROM app_user;"` → đúng một hàng,
      `google_sub` là NULL (sẽ được điền ở lần đăng nhập đầu).
- [ ] `dropdb ielts_rehearsal` sau khi xong.

## F. Chạy local trước khi lên VPS

- [ ] `docker compose up -d --build` (ở máy dev, `docker-compose.override.yml` tự mở lại cổng).
- [ ] `curl http://127.0.0.1:8080/api/health` → 200 **không cần token**.
- [ ] `curl http://127.0.0.1:8080/api/vocab` → **401** kèm `{code, message, retryable}`.
- [ ] `cd extension && npm run build`, nạp lại extension, mở side panel → hiện màn đăng nhập.
- [ ] Đăng nhập → **sổ từ cũ hiện đủ**. Đây là thời khắc quyết định của cả tính năng.
- [ ] Thử một Gmail **không** có trong `AUTH_ALLOWED_EMAILS` → "chưa được cấp quyền",
      không mời thử lại.

## G. Deploy VPS

- [ ] Trỏ DNS domain về IP VPS.
- [ ] Copy repo lên VPS **KHÔNG kèm `docker-compose.override.yml`** — file đó mở lại cổng
      Postgres ra host, đúng thứ vừa đóng vì lý do bảo mật.
- [ ] `docker compose up -d --build`.
- [ ] `curl https://<domain>/api/health` → 200 qua HTTPS.
- [ ] Từ **máy khác**: `psql -h <ip-vps> -U ielts` → **phải bị từ chối kết nối**. Không bị
      từ chối là Postgres đang mở ra Internet.
- [ ] Sửa `backendUrl` trong trang Options của extension sang `https://<domain>`.

## H. Kiểm tra đa thiết bị — thứ mà cả tính năng này tồn tại vì nó

- [ ] Máy A: đăng nhập, lưu một từ mới.
- [ ] **Máy B** (Chrome profile khác): đăng nhập **cùng tài khoản** → thấy đúng từ vừa lưu.
- [ ] Máy B: đăng xuất → máy A **vẫn** đăng nhập bình thường.
- [ ] Máy A: ôn một thẻ → máy B tải lại thấy lịch đã đổi.

## I. Vận hành

- [ ] Cron sao lưu trên VPS, **trước khi** đưa người thứ hai vào dùng:
      ```
      0 3 * * * cd /srv/ielts && docker compose exec -T db pg_dump -U ielts ielts | gzip > /backup/ielts-$(date +\%F).sql.gz
      ```
- [ ] Thử khôi phục bản sao lưu một lần. Bản sao lưu chưa từng khôi phục không phải bản sao lưu.
- [ ] Thêm người: sửa `AUTH_ALLOWED_EMAILS` trong `.env` rồi `docker compose up -d app`.

---

## Những chỗ tôi làm khác plan, đều là chủ ý

1. **Không chạy vòng đỏ-xanh từng bước.** Không có `mvn test` thì không có "đỏ" để quan sát.
   Code và test viết cùng lượt; nội dung bám plan.
2. **Bong bóng chưa đăng nhập chỉ đổi thông điệp, không có nút mở panel.** `chrome.sidePanel.open`
   đòi user gesture trong ngữ cảnh extension; nút bấm từ content script nhiều khả năng không
   mở được, và một nút bấm không ăn còn tệ hơn không có nút. Thông điệp nói rõ phải mở side
   panel.
3. **Hạn mức Gemini tắt (`0`) trong test.** Bật lên thì một test dài vô tình chạm trần sẽ đỏ
   vì lý do chẳng liên quan; `GeminiQuotaGuardIT` tự bật lại đúng 2 để test cái trần.
4. **Không tick checkbox nào trong file plan.** Tick "PASS" cho những bước tôi không chạy
   được là nói dối.
