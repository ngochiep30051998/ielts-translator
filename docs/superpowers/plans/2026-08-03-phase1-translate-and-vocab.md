# IELTS Translator — Phase 1: Dịch hai chiều + Sổ từ vựng

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bôi đen text bất kỳ trên web → bubble hiện nghĩa; mở side panel xem phân tích đầy đủ; lưu từ vào sổ từ vựng PostgreSQL và tra cứu lại được.

**Architecture:** Chrome extension MV3 (content script bắt selection, service worker giữ toàn bộ HTTP, side panel React hiển thị) gọi Spring Boot chạy trên `127.0.0.1:8080` qua docker compose. Backend detect ngôn ngữ + chế độ, chọn prompt, gọi Gemini với structured output, cache kết quả vào PostgreSQL.

**Tech Stack:** Java 21 · Spring Boot 3.4 · Maven · PostgreSQL 16 · Flyway · Testcontainers · WireMock · Docker Compose · React 18 · TypeScript · Vite 5 · CRXJS · Vitest · React Testing Library

**Spec:** `docs/superpowers/specs/2026-08-03-ielts-translator-extension-design.md`

## Global Constraints

- Content script **không bao giờ** gọi HTTP. Mọi request đi qua service worker.
- Side panel và options page cũng không gọi HTTP trực tiếp — gửi message tới service worker.
- Gọi Gemini **luôn** dùng structured output (`responseSchema`). Không bao giờ parse text tự do.
- Prompt nằm ở `backend/src/main/resources/prompts/*.md`, không hardcode trong Java.
- Cache key gồm: `text + direction + mode + model + prompt_version`.
- Mọi lỗi API trả đúng hình dạng `{ code, message, retryable }`.
- Mã lỗi hợp lệ: `GEMINI_QUOTA`, `GEMINI_UNAVAILABLE`, `PARSE_ERROR`, `TEXT_TOO_LONG`, `NOT_FOUND`, `INTERNAL`.
- Backend chỉ được tiếp cận từ localhost của máy host. Cụ thể: `application.yml`
  mặc định `server.address=127.0.0.1` cho lần chạy ngoài container; trong container
  thì `SERVER_ADDRESS=0.0.0.0` (bắt buộc, nếu không container không nhận request nào),
  và tính localhost-only do `ports: "127.0.0.1:8080:8080"` của compose đảm nhiệm.
  Không bao giờ publish cổng dạng `"8080:8080"` — dạng đó phơi backend ra mạng LAN.
- CORS chỉ cho origin `chrome-extension://<extension-id>`.
- Selection > 1500 ký tự bị chặn tại content script, không gửi lên backend.
- Timeout Phase 1: dịch 15s.
- Test dùng Testcontainers PostgreSQL, **không dùng H2** (hành vi JSONB khác).
- Java package gốc: `com.hiepnn.ieltstranslator`.
- Phase 1 **không** tạo bảng `srs_card` — để Phase 2.
- Options Phase 1 chỉ có 3 mục: backend URL, chế độ kích hoạt, giọng đọc. Mục
  "Từ mới mỗi ngày" ở mục 13 của spec thuộc SRS nên dời sang Phase 2 — không dựng
  sẵn một ô cài đặt mà không có gì đọc nó.

## File Structure

```
ielts-translator/
├── docker-compose.yml              # 2 service: db, app
├── .env.example                    # GEMINI_API_KEY=...
├── backend/
│   ├── Dockerfile                  # multi-stage maven → jre
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/hiepnn/ieltstranslator/
│       │   ├── IeltsTranslatorApplication.java
│       │   ├── common/             # lỗi, CORS, cấu hình dùng chung
│       │   │   ├── ErrorCode.java  ApiError.java  AppException.java
│       │   │   ├── GlobalExceptionHandler.java
│       │   │   ├── CorsConfig.java
│       │   │   └── gemini/         # GeminiProperties, GeminiClient
│       │   ├── translation/        # detect, prompt, gọi Gemini, cache
│       │   │   ├── Direction.java  Mode.java  LanguageDetector.java
│       │   │   ├── PromptLoader.java  TranslationSchemas.java
│       │   │   ├── TranslationService.java  TranslateController.java
│       │   │   ├── dto/  cache/
│       │   ├── vocabulary/         # sổ từ: CRUD, tìm kiếm, CSV
│       │   └── health/HealthController.java
│       ├── main/resources/
│       │   ├── application.yml
│       │   ├── db/migration/       # V1 lookup_cache, V2 vocab_entry
│       │   └── prompts/            # 4 file .md
│       └── test/java/...
└── extension/
    ├── package.json  vite.config.ts  tsconfig.json  manifest.config.ts
    └── src/
        ├── shared/                 # types.ts messages.ts settings.ts
        ├── background/             # api-client.ts service-worker.ts
        ├── content/                # selection.ts bubble.tsx index.ts
        ├── sidepanel/              # App/TranslateTab/VocabTab
        └── options/
```

Ranh giới: `common` không biết gì về domain. `translation` không biết `vocabulary` tồn tại. `vocabulary` không gọi Gemini.

---

### Task 1: Backend scaffold, Docker Compose, health endpoint

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `backend/Dockerfile`, `backend/pom.xml`
- Create: `backend/src/main/resources/application.yml`
- Create: `backend/src/main/resources/db/migration/V1__lookup_cache.sql`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/IeltsTranslatorApplication.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/health/HealthController.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/common/{ErrorCode,ApiError,AppException,GlobalExceptionHandler,CorsConfig}.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/health/HealthControllerIT.java`

**Interfaces:**
- Consumes: nothing
- Produces: `ErrorCode` enum (`GEMINI_QUOTA, GEMINI_UNAVAILABLE, PARSE_ERROR, TEXT_TOO_LONG, NOT_FOUND, INTERNAL`); `ApiError(String code, String message, boolean retryable)`; `AppException(ErrorCode code, String message, boolean retryable)` với static factory `AppException.of(ErrorCode, String)`; `GET /api/health → {status, geminiConfigured, dbConnected}`

- [ ] **Step 1: Tạo `backend/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.4.1</version>
    <relativePath/>
  </parent>
  <groupId>com.hiepnn</groupId>
  <artifactId>ielts-translator</artifactId>
  <version>0.1.0</version>
  <properties>
    <java.version>21</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-core</artifactId>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-database-postgresql</artifactId>
    </dependency>
    <dependency>
      <groupId>org.postgresql</groupId>
      <artifactId>postgresql</artifactId>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>io.hypersistence</groupId>
      <artifactId>hypersistence-utils-hibernate-63</artifactId>
      <version>3.9.0</version>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-testcontainers</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>postgresql</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.wiremock</groupId>
      <artifactId>wiremock-standalone</artifactId>
      <version>3.10.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: Tạo `backend/src/main/resources/application.yml`**

```yaml
server:
  address: ${SERVER_ADDRESS:127.0.0.1}
  port: 8080

spring:
  application:
    name: ielts-translator
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/ielts}
    username: ${DB_USER:ielts}
    password: ${DB_PASSWORD:ielts}
  jpa:
    hibernate:
      ddl-auto: validate
    open-in-view: false
  flyway:
    enabled: true

gemini:
  api-key: ${GEMINI_API_KEY:}
  model: ${GEMINI_MODEL:gemini-2.5-flash}
  base-url: ${GEMINI_BASE_URL:https://generativelanguage.googleapis.com}
  timeout-seconds: 15

extension:
  id: ${EXTENSION_ID:}
```

Ghi chú: `server.address: 127.0.0.1` là bên trong container — docker compose sẽ map `127.0.0.1:8080` từ host. Trong container phải bind `0.0.0.0` mới nhận được, nên `docker-compose.yml` ở Step 4 override bằng `SERVER_ADDRESS=0.0.0.0`; việc giới hạn chỉ-localhost do phần `ports` của compose đảm nhiệm.

- [ ] **Step 3: Tạo migration `backend/src/main/resources/db/migration/V1__lookup_cache.sql`**

```sql
CREATE TABLE lookup_cache (
    id             BIGSERIAL    PRIMARY KEY,
    source_hash    VARCHAR(64)  NOT NULL UNIQUE,
    source_text    TEXT         NOT NULL,
    direction      VARCHAR(16)  NOT NULL,
    mode           VARCHAR(16)  NOT NULL,
    model          VARCHAR(64)  NOT NULL,
    prompt_version INTEGER      NOT NULL,
    response       JSONB        NOT NULL,
    hit_count      INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_lookup_cache_created_at ON lookup_cache (created_at DESC);
```

- [ ] **Step 4: Tạo `docker-compose.yml` và `.env.example`**

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ielts
      POSTGRES_USER: ielts
      POSTGRES_PASSWORD: ielts
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - ielts_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ielts -d ielts"]
      interval: 5s
      timeout: 3s
      retries: 10

  app:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      SERVER_ADDRESS: 0.0.0.0
      DB_URL: jdbc:postgresql://db:5432/ielts
      DB_USER: ielts
      DB_PASSWORD: ielts
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      GEMINI_MODEL: ${GEMINI_MODEL:-gemini-2.5-flash}
      EXTENSION_ID: ${EXTENSION_ID}
    ports:
      - "127.0.0.1:8080:8080"

volumes:
  ielts_pgdata:
```

`.env.example`:
```
GEMINI_API_KEY=thay-bang-key-cua-ban
GEMINI_MODEL=gemini-2.5-flash
EXTENSION_ID=dien-sau-khi-lam-task-7
```

`EXTENSION_ID` để trống ở giai đoạn này là chấp nhận được — `CorsConfig` sẽ bỏ qua cấu hình CORS khi giá trị rỗng. Task 7 sinh ID cố định rồi điền vào đây.

- [ ] **Step 5: Tạo `backend/Dockerfile`**

```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
RUN mvn -B clean package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/ielts-translator-0.1.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

- [ ] **Step 6: Viết test thất bại `HealthControllerIT.java`**

```java
package com.hiepnn.ieltstranslator.health;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class HealthControllerIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("gemini.api-key", () -> "test-key");
    }

    @Autowired
    MockMvc mockMvc;

    @Test
    void healthReportsDbAndGeminiConfigured() throws Exception {
        mockMvc.perform(get("/api/health"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.status").value("UP"))
               .andExpect(jsonPath("$.dbConnected").value(true))
               .andExpect(jsonPath("$.geminiConfigured").value(true));
    }
}
```

- [ ] **Step 7: Chạy test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest=HealthControllerIT`
Expected: FAIL — không có bean/class `HealthController`, compile error.

- [ ] **Step 8: Viết `common/ErrorCode.java`, `ApiError.java`, `AppException.java`**

```java
package com.hiepnn.ieltstranslator.common;

public enum ErrorCode {
    GEMINI_QUOTA,
    GEMINI_UNAVAILABLE,
    PARSE_ERROR,
    TEXT_TOO_LONG,
    NOT_FOUND,
    INTERNAL
}
```

```java
package com.hiepnn.ieltstranslator.common;

public record ApiError(String code, String message, boolean retryable) {}
```

```java
package com.hiepnn.ieltstranslator.common;

public class AppException extends RuntimeException {
    private final ErrorCode code;
    private final boolean retryable;

    public AppException(ErrorCode code, String message, boolean retryable) {
        super(message);
        this.code = code;
        this.retryable = retryable;
    }

    public static AppException of(ErrorCode code, String message) {
        boolean retryable = code == ErrorCode.GEMINI_UNAVAILABLE;
        return new AppException(code, message, retryable);
    }

    public ErrorCode code() { return code; }
    public boolean retryable() { return retryable; }
}
```

- [ ] **Step 9: Viết `common/GlobalExceptionHandler.java`**

```java
package com.hiepnn.ieltstranslator.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(AppException.class)
    public ResponseEntity<ApiError> handleApp(AppException ex) {
        log.warn("AppException {}: {}", ex.code(), ex.getMessage());
        return ResponseEntity.status(statusFor(ex.code()))
                .body(new ApiError(ex.code().name(), ex.getMessage(), ex.retryable()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleOther(Exception ex) {
        log.error("Unhandled exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ApiError(ErrorCode.INTERNAL.name(), "Lỗi không xác định", false));
    }

    private HttpStatus statusFor(ErrorCode code) {
        return switch (code) {
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case TEXT_TOO_LONG -> HttpStatus.BAD_REQUEST;
            case GEMINI_QUOTA -> HttpStatus.TOO_MANY_REQUESTS;
            case GEMINI_UNAVAILABLE -> HttpStatus.SERVICE_UNAVAILABLE;
            case PARSE_ERROR, INTERNAL -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
    }
}
```

- [ ] **Step 10: Viết `common/CorsConfig.java`**

```java
package com.hiepnn.ieltstranslator.common;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig implements WebMvcConfigurer {

    private final String extensionId;

    public CorsConfig(@Value("${extension.id:}") String extensionId) {
        this.extensionId = extensionId;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        if (extensionId.isBlank()) {
            return;
        }
        registry.addMapping("/api/**")
                .allowedOrigins("chrome-extension://" + extensionId)
                .allowedMethods("GET", "POST", "DELETE")
                .allowedHeaders("*");
    }
}
```

- [ ] **Step 11: Viết `IeltsTranslatorApplication.java` và `health/HealthController.java`**

```java
package com.hiepnn.ieltstranslator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class IeltsTranslatorApplication {
    public static void main(String[] args) {
        SpringApplication.run(IeltsTranslatorApplication.class, args);
    }
}
```

```java
package com.hiepnn.ieltstranslator.health;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/health")
public class HealthController {

    private final JdbcTemplate jdbcTemplate;
    private final String geminiApiKey;

    public HealthController(JdbcTemplate jdbcTemplate,
                            @Value("${gemini.api-key:}") String geminiApiKey) {
        this.jdbcTemplate = jdbcTemplate;
        this.geminiApiKey = geminiApiKey;
    }

    @GetMapping
    public Map<String, Object> health() {
        boolean dbConnected;
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            dbConnected = true;
        } catch (Exception e) {
            dbConnected = false;
        }
        return Map.of(
                "status", dbConnected ? "UP" : "DOWN",
                "dbConnected", dbConnected,
                "geminiConfigured", !geminiApiKey.isBlank()
        );
    }
}
```

- [ ] **Step 12: Chạy test để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest=HealthControllerIT`
Expected: PASS

- [ ] **Step 13: Xác nhận docker compose chạy được**

Run:
```bash
cp .env.example .env
docker compose up -d --build
sleep 20
curl -s http://127.0.0.1:8080/api/health
```
Expected: JSON có `"status":"UP"`, `"dbConnected":true`.

Sau đó `docker compose down`.

- [ ] **Step 14: Commit**

```bash
git add docker-compose.yml .env.example backend/
git commit -m "feat: backend scaffold, docker compose, health endpoint"
```

---

### Task 2: LanguageDetector và Mode

Logic thuần, không phụ thuộc Spring hay DB. Detect sai làm hỏng toàn bộ trải nghiệm nên test kỹ bằng bảng.

**Files:**
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/{Direction,Mode,LanguageDetector}.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/LanguageDetectorTest.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/ModeTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `enum Direction { EN_VI, VI_EN }`; `enum Mode { WORD, SENTENCE }` với `static Mode of(String text)`; `LanguageDetector` (Spring `@Component`) với `Direction detect(String text)`

- [ ] **Step 1: Viết test thất bại `LanguageDetectorTest.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class LanguageDetectorTest {

    private final LanguageDetector detector = new LanguageDetector();

    @ParameterizedTest(name = "[{index}] \"{0}\" -> {1}")
    @CsvSource(delimiter = '|', value = {
        // tiếng Việt có dấu -> nhận ra ngay bằng ký tự
        "Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo | VI_EN",
        "tái tạo                                               | VI_EN",
        "Tôi thích renewable energy                            | VI_EN",
        // tiếng Việt không dấu -> nhận ra bằng stopword
        "toi khong biet cai nay la cua ai                      | VI_EN",
        "chung ta can phai lam viec nay cho tot               | VI_EN",
        // tiếng Anh
        "renewable                                             | EN_VI",
        "The government should allocate more funding           | EN_VI",
        "this is a test of the system                          | EN_VI",
        // viết hoa toàn bộ -> cần UNICODE_CASE mới nhận ra
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM                    | VI_EN",
        "ĐIỀU NÀY RẤT QUAN TRỌNG                               | VI_EN",
        "Á                                                     | VI_EN",
        // không quyết được -> mặc định EN_VI
        "12345                                                 | EN_VI",
        "'  '                                                  | EN_VI"
    })
    void detectsDirection(String text, Direction expected) {
        assertThat(detector.detect(text)).isEqualTo(expected);
    }

    @Test
    void emptyTextDefaultsToEnVi() {
        assertThat(detector.detect("")).isEqualTo(Direction.EN_VI);
    }

    @Test
    void nullTextDefaultsToEnVi() {
        assertThat(detector.detect(null)).isEqualTo(Direction.EN_VI);
    }
}
```

- [ ] **Step 2: Viết test thất bại `ModeTest.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class ModeTest {

    @ParameterizedTest(name = "[{index}] \"{0}\" -> {1}")
    @CsvSource(delimiter = '|', value = {
        "renewable                             | WORD",
        "climate change                        | WORD",
        "renewable energy sources              | WORD",
        "  renewable   energy   sources        | WORD",
        "the government should allocate funding | SENTENCE",
        "năng lượng tái tạo là xu hướng        | SENTENCE"
    })
    void classifiesMode(String text, Mode expected) {
        assertThat(Mode.of(text)).isEqualTo(expected);
    }
}
```

- [ ] **Step 3: Chạy cả hai test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest='LanguageDetectorTest,ModeTest'`
Expected: FAIL — compile error, chưa có class `Direction`, `Mode`, `LanguageDetector`.

- [ ] **Step 4: Viết `Direction.java` và `Mode.java`**

```java
package com.hiepnn.ieltstranslator.translation;

public enum Direction {
    EN_VI,
    VI_EN
}
```

```java
package com.hiepnn.ieltstranslator.translation;

public enum Mode {
    WORD,
    SENTENCE;

    /** Từ 3 token trở xuống coi là tra từ; nhiều hơn là tra câu. */
    public static Mode of(String text) {
        if (text == null || text.isBlank()) {
            return WORD;
        }
        int tokens = text.trim().split("\\s+").length;
        return tokens <= 3 ? WORD : SENTENCE;
    }
}
```

- [ ] **Step 5: Viết `LanguageDetector.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.Set;
import java.util.regex.Pattern;

@Component
public class LanguageDetector {

    /**
     * Ký tự chỉ xuất hiện trong tiếng Việt — thấy một cái là chắc chắn tiếng Việt.
     * UNICODE_CASE là bắt buộc: CASE_INSENSITIVE một mình chỉ fold case US-ASCII,
     * không fold được Đ/đ hay Á/á, khiến text viết hoa toàn bộ bị nhận nhầm là EN.
     */
    private static final Pattern VIETNAMESE_CHARS = Pattern.compile(
            "[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);

    /** Stopword tiếng Việt dạng KHÔNG dấu — dùng khi người dùng gõ không dấu. */
    private static final Set<String> VI_STOPWORDS = Set.of(
            "cua", "va", "la", "khong", "cho", "nhung", "duoc", "co", "nay", "voi",
            "tren", "trong", "mot", "cac", "nguoi", "den", "tu", "ra", "khi", "nhu",
            "se", "da", "cung", "phai", "the", "nao", "gi", "ai", "toi", "ban",
            "chung", "minh", "can", "lam", "viec", "tot", "cai");

    private static final Set<String> EN_STOPWORDS = Set.of(
            "the", "and", "is", "of", "to", "in", "that", "it", "for", "on",
            "with", "as", "this", "are", "was", "be", "have", "has", "not", "but",
            "they", "from", "which", "you", "we", "should", "a", "an");

    public Direction detect(String text) {
        if (text == null || text.isBlank()) {
            return Direction.EN_VI;
        }
        if (VIETNAMESE_CHARS.matcher(text).find()) {
            return Direction.VI_EN;
        }
        String[] tokens = text.toLowerCase().split("[^a-z]+");
        long viHits = Arrays.stream(tokens).filter(VI_STOPWORDS::contains).count();
        long enHits = Arrays.stream(tokens).filter(EN_STOPWORDS::contains).count();
        return viHits > enHits ? Direction.VI_EN : Direction.EN_VI;
    }
}
```

- [ ] **Step 6: Chạy test để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest='LanguageDetectorTest,ModeTest'`
Expected: PASS, tất cả case.

- [ ] **Step 7: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator/translation backend/src/test/java/com/hiepnn/ieltstranslator/translation
git commit -m "feat: detect ngôn ngữ và chế độ tra từ/tra câu"
```

---

### Task 3: GeminiClient với structured output

Đường lỗi của client này (429, 5xx, JSON hỏng, timeout) không tự nhiên xảy ra lúc dev, nên phải ép nó xảy ra bằng WireMock.

**Files:**
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/common/gemini/{GeminiProperties,GeminiConfig,GeminiClient}.java`
- Modify: `backend/src/main/resources/application.yml` (thêm `retry-backoff-millis`)
- Modify: `backend/src/main/java/com/hiepnn/ieltstranslator/IeltsTranslatorApplication.java` (thêm `@ConfigurationPropertiesScan`)
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/common/gemini/GeminiClientTest.java`

**Interfaces:**
- Consumes: `AppException`, `ErrorCode` (Task 1)
- Produces: `GeminiProperties(String apiKey, String model, String baseUrl, int timeoutSeconds, long retryBackoffMillis)`; `GeminiClient` với method `JsonNode generateJson(String prompt, Map<String, Object> responseSchema)`

- [ ] **Step 1: Thêm `retry-backoff-millis` vào `application.yml`**

Trong block `gemini:`, thêm dòng:
```yaml
  retry-backoff-millis: ${GEMINI_RETRY_BACKOFF_MS:1000}
```

- [ ] **Step 2: Viết test thất bại `GeminiClientTest.java`**

```java
package com.hiepnn.ieltstranslator.common.gemini;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.tomakehurst.wiremock.WireMockServer;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.junit.jupiter.api.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.options;
import static org.assertj.core.api.Assertions.*;

class GeminiClientTest {

    private WireMockServer wireMock;
    private GeminiClient client;

    private static final Map<String, Object> SCHEMA =
            Map.of("type", "object", "properties", Map.of("meaning_vi", Map.of("type", "string")));

    @BeforeEach
    void setUp() {
        wireMock = new WireMockServer(options().dynamicPort());
        wireMock.start();

        GeminiProperties props = new GeminiProperties(
                "test-key", "gemini-2.5-flash",
                "http://localhost:" + wireMock.port(), 2, 10L);

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(2));
        factory.setReadTimeout(Duration.ofSeconds(props.timeoutSeconds()));
        RestClient restClient = RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.baseUrl())
                .build();

        client = new GeminiClient(restClient, props, new ObjectMapper());
    }

    @AfterEach
    void tearDown() {
        wireMock.stop();
    }

    private void stubGemini(int status, String body) {
        wireMock.stubFor(post(urlPathMatching("/v1beta/models/.*:generateContent"))
                .willReturn(aResponse().withStatus(status)
                        .withHeader("Content-Type", "application/json")
                        .withBody(body)));
    }

    private String candidateWrapping(String innerJson) {
        return """
               {"candidates":[{"content":{"parts":[{"text":%s}]}}]}
               """.formatted(new ObjectMapper().valueToTree(innerJson).toString());
    }

    @Test
    void returnsParsedJsonOnSuccess() {
        stubGemini(200, candidateWrapping("{\\"meaning_vi\\":\\"tái tạo\\"}"));

        JsonNode result = client.generateJson("prompt bất kỳ", SCHEMA);

        assertThat(result.get("meaning_vi").asText()).isEqualTo("tái tạo");
    }

    @Test
    void sendsApiKeyAndResponseSchema() {
        stubGemini(200, candidateWrapping("{\\"meaning_vi\\":\\"x\\"}"));

        client.generateJson("prompt bất kỳ", SCHEMA);

        wireMock.verify(postRequestedFor(urlPathMatching("/v1beta/models/.*:generateContent"))
                .withQueryParam("key", equalTo("test-key"))
                .withRequestBody(matchingJsonPath("$.generationConfig.responseMimeType",
                        equalTo("application/json")))
                .withRequestBody(matchingJsonPath("$.generationConfig.responseSchema"))
                .withRequestBody(matchingJsonPath("$.contents[0].parts[0].text",
                        equalTo("prompt bất kỳ"))));
    }

    @Test
    void quotaErrorIsNotRetriedAndMapsToGeminiQuota() {
        stubGemini(429, "{\"error\":{\"message\":\"quota exceeded\"}}");

        assertThatThrownBy(() -> client.generateJson("p", SCHEMA))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> {
                    assertThat(((AppException) ex).code()).isEqualTo(ErrorCode.GEMINI_QUOTA);
                    assertThat(((AppException) ex).retryable()).isFalse();
                });

        wireMock.verify(1, postRequestedFor(urlPathMatching("/v1beta/models/.*:generateContent")));
    }

    @Test
    void serverErrorIsRetriedOnceThenFails() {
        stubGemini(503, "{\"error\":\"unavailable\"}");

        assertThatThrownBy(() -> client.generateJson("p", SCHEMA))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.GEMINI_UNAVAILABLE));

        wireMock.verify(2, postRequestedFor(urlPathMatching("/v1beta/models/.*:generateContent")));
    }

    @Test
    void serverErrorThatRecoversOnRetrySucceeds() {
        wireMock.stubFor(post(urlPathMatching("/v1beta/models/.*:generateContent"))
                .inScenario("recover").whenScenarioStateIs("Started")
                .willReturn(aResponse().withStatus(503).withBody("{}"))
                .willSetStateTo("second"));
        wireMock.stubFor(post(urlPathMatching("/v1beta/models/.*:generateContent"))
                .inScenario("recover").whenScenarioStateIs("second")
                .willReturn(aResponse().withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody(candidateWrapping("{\\"meaning_vi\\":\\"ổn\\"}"))));

        JsonNode result = client.generateJson("p", SCHEMA);

        assertThat(result.get("meaning_vi").asText()).isEqualTo("ổn");
    }

    @Test
    void malformedInnerJsonIsRetriedOnceThenMapsToParseError() {
        stubGemini(200, candidateWrapping("khong phai json"));

        assertThatThrownBy(() -> client.generateJson("p", SCHEMA))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.PARSE_ERROR));

        wireMock.verify(2, postRequestedFor(urlPathMatching("/v1beta/models/.*:generateContent")));
    }

    @Test
    void missingCandidatesMapsToParseError() {
        stubGemini(200, "{\"candidates\":[]}");

        assertThatThrownBy(() -> client.generateJson("p", SCHEMA))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.PARSE_ERROR));
    }

    @Test
    void timeoutMapsToGeminiUnavailable() {
        wireMock.stubFor(post(urlPathMatching("/v1beta/models/.*:generateContent"))
                .willReturn(aResponse().withStatus(200)
                        .withFixedDelay(4000)  // > readTimeout 2s
                        .withBody("{}")));

        assertThatThrownBy(() -> client.generateJson("p", SCHEMA))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code())
                        .isEqualTo(ErrorCode.GEMINI_UNAVAILABLE));
    }
}
```

- [ ] **Step 3: Chạy test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest=GeminiClientTest`
Expected: FAIL — chưa có `GeminiProperties`, `GeminiClient`.

- [ ] **Step 4: Viết `GeminiProperties.java`**

```java
package com.hiepnn.ieltstranslator.common.gemini;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "gemini")
public record GeminiProperties(
        String apiKey,
        String model,
        String baseUrl,
        int timeoutSeconds,
        long retryBackoffMillis
) {}
```

- [ ] **Step 5: Thêm `@ConfigurationPropertiesScan` vào `IeltsTranslatorApplication.java`**

```java
package com.hiepnn.ieltstranslator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class IeltsTranslatorApplication {
    public static void main(String[] args) {
        SpringApplication.run(IeltsTranslatorApplication.class, args);
    }
}
```

- [ ] **Step 6: Viết `GeminiConfig.java`**

```java
package com.hiepnn.ieltstranslator.common.gemini;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class GeminiConfig {

    @Bean
    public RestClient geminiRestClient(GeminiProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(props.timeoutSeconds()));
        return RestClient.builder()
                .requestFactory(factory)
                .baseUrl(props.baseUrl())
                .build();
    }
}
```

- [ ] **Step 7: Viết `GeminiClient.java`**

```java
package com.hiepnn.ieltstranslator.common.gemini;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;

@Component
public class GeminiClient {

    private static final Logger log = LoggerFactory.getLogger(GeminiClient.class);
    private static final int MAX_ATTEMPTS = 2;

    private final RestClient restClient;
    private final GeminiProperties props;
    private final ObjectMapper objectMapper;

    public GeminiClient(RestClient geminiRestClient, GeminiProperties props, ObjectMapper objectMapper) {
        this.restClient = geminiRestClient;
        this.props = props;
        this.objectMapper = objectMapper;
    }

    /**
     * Gọi Gemini với structured output. Chỉ retry lỗi tạm thời (5xx, timeout,
     * JSON hỏng) đúng 1 lần. Lỗi quota không retry.
     */
    public JsonNode generateJson(String prompt, Map<String, Object> responseSchema) {
        AppException last = null;
        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            try {
                return callOnce(prompt, responseSchema);
            } catch (AppException ex) {
                // Chỉ retry lỗi tạm thời. Liệt kê cái ĐƯỢC retry (thay vì cái không)
                // để thêm mã lỗi mới về sau không vô tình bật retry cho nó.
                boolean transient_ = ex.code() == ErrorCode.GEMINI_UNAVAILABLE
                                  || ex.code() == ErrorCode.PARSE_ERROR;
                if (!transient_) {
                    throw ex;
                }
                last = ex;
                log.warn("Gemini lần {} thất bại ({}), {}", attempt, ex.code(),
                        attempt < MAX_ATTEMPTS ? "thử lại" : "bỏ cuộc");
                if (attempt < MAX_ATTEMPTS) {
                    sleepBackoff();
                }
            }
        }
        throw last;
    }

    private JsonNode callOnce(String prompt, Map<String, Object> responseSchema) {
        Map<String, Object> body = Map.of(
                "contents", List.of(Map.of("role", "user",
                        "parts", List.of(Map.of("text", prompt)))),
                "generationConfig", Map.of(
                        "responseMimeType", "application/json",
                        "responseSchema", responseSchema));

        ResponseEntity<String> response;
        try {
            response = restClient.post()
                    .uri(uri -> uri.path("/v1beta/models/{model}:generateContent")
                            .queryParam("key", props.apiKey())
                            .build(props.model()))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(status -> true, (req, res) -> { /* xử lý thủ công bên dưới */ })
                    .toEntity(String.class);
        } catch (ResourceAccessException ex) {
            throw AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini không phản hồi kịp");
        }

        int status = response.getStatusCode().value();
        if (status == 429) {
            throw AppException.of(ErrorCode.GEMINI_QUOTA, "Đã hết quota Gemini");
        }
        if (status >= 500) {
            throw AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini trả lỗi HTTP " + status);
        }
        if (status >= 400) {
            // Lỗi cấu hình phía ta (key sai, model sai) — retry không bao giờ cứu được
            throw AppException.of(ErrorCode.INTERNAL,
                    "Gemini từ chối request (HTTP " + status
                    + "). Kiểm tra GEMINI_API_KEY và GEMINI_MODEL trong file .env.");
        }
        return extractPayload(response.getBody());
    }

    private JsonNode extractPayload(String rawBody) {
        try {
            JsonNode root = objectMapper.readTree(rawBody);
            JsonNode candidates = root.path("candidates");
            if (!candidates.isArray() || candidates.isEmpty()) {
                throw AppException.of(ErrorCode.PARSE_ERROR, "Gemini không trả candidate nào");
            }
            String inner = candidates.get(0).path("content").path("parts").path(0).path("text").asText(null);
            if (inner == null) {
                throw AppException.of(ErrorCode.PARSE_ERROR, "Gemini trả candidate rỗng");
            }
            return objectMapper.readTree(inner);
        } catch (AppException ex) {
            throw ex;
        } catch (Exception ex) {
            throw AppException.of(ErrorCode.PARSE_ERROR, "Không đọc được JSON từ Gemini");
        }
    }

    private void sleepBackoff() {
        try {
            Thread.sleep(props.retryBackoffMillis());
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }
}
```

- [ ] **Step 8: Chạy test để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest=GeminiClientTest`
Expected: PASS, cả 8 test.

- [ ] **Step 9: Commit**

```bash
git add backend/src/main/java/com/hiepnn/ieltstranslator backend/src/test/java/com/hiepnn/ieltstranslator/common backend/src/main/resources/application.yml
git commit -m "feat: GeminiClient với structured output, retry và ánh xạ lỗi"
```

---

### Task 4: Prompt files, PromptLoader, TranslationSchemas

Đây là "hợp đồng" với Gemini. Prompt và schema đi cùng nhau nên làm chung một task.

**Files:**
- Create: `backend/src/main/resources/prompts/{en-vi-word,en-vi-sentence,vi-en-word,vi-en-sentence}.md`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/{PromptLoader,PromptTemplate,TranslationSchemas}.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/{PromptLoaderTest,TranslationSchemasTest}.java`

**Interfaces:**
- Consumes: `Direction`, `Mode` (Task 2)
- Produces: `record PromptTemplate(String body, int version)` với `String render(String text, String context)`; `PromptLoader` (`@Component`) với `PromptTemplate load(Direction direction, Mode mode)`; `TranslationSchemas` với `static Map<String, Object> of(Direction direction, Mode mode)`

- [ ] **Step 1: Viết test thất bại `PromptLoaderTest.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLoaderTest {

    private final PromptLoader loader = new PromptLoader();

    @ParameterizedTest
    @CsvSource({
        "EN_VI, WORD", "EN_VI, SENTENCE", "VI_EN, WORD", "VI_EN, SENTENCE"
    })
    void loadsAllFourTemplates(Direction direction, Mode mode) {
        PromptTemplate template = loader.load(direction, mode);

        assertThat(template.version()).isGreaterThanOrEqualTo(1);
        assertThat(template.body()).isNotBlank();
        // doesNotStartWith chứ không phải doesNotContain: body của vi-en-sentence
        // chứa tên trường "band65_version" hợp lệ, không phải header sót lại.
        assertThat(template.body()).doesNotStartWith("version:");
    }

    @Test
    void headerIsStrippedButBodyKeepsFieldNamesContainingVersion() {
        PromptTemplate template = loader.load(Direction.VI_EN, Mode.SENTENCE);

        assertThat(template.version()).isEqualTo(1);
        assertThat(template.body()).doesNotStartWith("version:");
        assertThat(template.body()).contains("band65_version");
    }

    @Test
    void renderSubstitutesTextAndContext() {
        PromptTemplate template = new PromptTemplate(
                "Tra từ: {{TEXT}}\nNgữ cảnh: {{CONTEXT}}", 1);

        String rendered = template.render("renewable", "We need renewable energy.");

        assertThat(rendered).isEqualTo("Tra từ: renewable\nNgữ cảnh: We need renewable energy.");
    }

    @Test
    void renderHandlesNullContext() {
        PromptTemplate template = new PromptTemplate("{{TEXT}}|{{CONTEXT}}", 1);

        assertThat(template.render("x", null)).isEqualTo("x|(không có ngữ cảnh)");
    }

    @Test
    void everyTemplateContainsTextPlaceholder() {
        for (Direction d : Direction.values()) {
            for (Mode m : Mode.values()) {
                assertThat(loader.load(d, m).body())
                        .as("%s/%s phải có {{TEXT}}", d, m)
                        .contains("{{TEXT}}");
            }
        }
    }
}
```

- [ ] **Step 2: Viết test thất bại `TranslationSchemasTest.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class TranslationSchemasTest {

    @SuppressWarnings("unchecked")
    private List<String> requiredOf(Direction d, Mode m) {
        return (List<String>) TranslationSchemas.of(d, m).get("required");
    }

    @Test
    void enViWordRequiresBubbleAndDetailFields() {
        assertThat(requiredOf(Direction.EN_VI, Mode.WORD))
                .contains("term", "ipa", "pos", "meaning_vi", "definition_en",
                          "cefr", "band_level", "register", "collocations",
                          "examples", "synonyms");
    }

    @Test
    void enViSentenceRequiresTranslationAndKeyVocab() {
        assertThat(requiredOf(Direction.EN_VI, Mode.SENTENCE))
                .contains("translation_vi", "key_vocab", "structure_note");
    }

    @Test
    void viEnWordRequiresBestEnAndAlternatives() {
        assertThat(requiredOf(Direction.VI_EN, Mode.WORD))
                .contains("best_en", "alternatives", "collocations", "examples");
    }

    @Test
    void viEnSentenceRequiresBandVersionAndExplanations() {
        assertThat(requiredOf(Direction.VI_EN, Mode.SENTENCE))
                .contains("band65_version", "why_notes", "key_phrases", "avoid");
    }

    @Test
    void allSchemasAreObjectsWithProperties() {
        for (Direction d : Direction.values()) {
            for (Mode m : Mode.values()) {
                Map<String, Object> schema = TranslationSchemas.of(d, m);
                assertThat(schema.get("type")).as("%s/%s", d, m).isEqualTo("object");
                assertThat(schema.get("properties")).as("%s/%s", d, m).isInstanceOf(Map.class);
            }
        }
    }
}
```

- [ ] **Step 3: Chạy cả hai test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest='PromptLoaderTest,TranslationSchemasTest'`
Expected: FAIL — chưa có `PromptLoader`, `PromptTemplate`, `TranslationSchemas`.

- [ ] **Step 4: Viết `prompts/en-vi-word.md`**

```markdown
version: 1
---
Bạn là từ điển Anh-Việt dành cho người luyện thi IELTS mục tiêu band 6.5+.

Phân tích từ/cụm từ tiếng Anh sau và trả về JSON đúng schema đã cho.

Từ cần tra: {{TEXT}}
Câu chứa từ: {{CONTEXT}}

Quy tắc:
- meaning_vi: nghĩa tiếng Việt, TỐI ĐA 8 từ, khớp với câu ngữ cảnh. Đây là thứ hiển thị trong popup nhỏ nên phải thật gọn.
- definition_en: định nghĩa tiếng Anh một câu, dùng từ vựng đơn giản hơn chính từ đang tra.
- ipa: phiên âm IPA giọng Anh-Anh, đặt trong hai dấu gạch chéo.
- pos: từ loại viết tắt tiếng Anh (n, v, adj, adv, prep, phrase).
- cefr: một trong A1, A2, B1, B2, C1, C2.
- band_level: band Lexical Resource mà thí sinh dùng đúng từ này thường đạt. Ước lượng thận trọng, chỉ dùng một trong 5.5, 6.0, 6.5, 7.0, 7.5, 8.0.
- register: một trong academic, neutral, informal.
- collocations: 3 đến 5 collocation phổ biến trong văn viết học thuật. Viết dạng cụm, không viết thành câu.
- examples: đúng 2 ví dụ. Câu tiếng Anh ở mức band 6.5-7.0 (có mệnh đề phụ, không đơn giản hoá quá mức), kèm bản dịch tiếng Việt tự nhiên.
- synonyms: 2 đến 4 từ đồng nghĩa, mỗi từ kèm band ước lượng, sắp xếp band tăng dần.

Nếu từ có nhiều nghĩa, chọn đúng nghĩa khớp câu ngữ cảnh, không liệt kê mọi nghĩa.
```

- [ ] **Step 5: Viết `prompts/en-vi-sentence.md`**

```markdown
version: 1
---
Bạn là giáo viên IELTS Reading, giúp người học hiểu câu tiếng Anh học thuật.

Câu tiếng Anh: {{TEXT}}
Đoạn văn xung quanh: {{CONTEXT}}

Trả về JSON đúng schema:
- translation_vi: bản dịch tiếng Việt tự nhiên, đúng nghĩa, KHÔNG dịch word-by-word. Giữ đúng sắc thái trang trọng của bản gốc.
- key_vocab: 2 đến 5 từ đáng học nhất trong câu. Chỉ chọn từ mức B2 trở lên, bỏ qua từ quá thông dụng. Mỗi từ kèm nghĩa tiếng Việt ngắn và band ước lượng (chỉ dùng 5.5, 6.0, 6.5, 7.0, 7.5, 8.0).
- structure_note: một ghi chú tiếng Việt, 1-2 câu, chỉ ra cấu trúc ngữ pháp đáng chú ý trong câu (mệnh đề quan hệ, bị động, đảo ngữ, mệnh đề nhượng bộ...) và nêu tên cấu trúc đó.

Nếu câu không có cấu trúc gì đặc biệt, structure_note ghi rõ đây là câu đơn giản thay vì bịa ra cấu trúc.
```

- [ ] **Step 6: Viết `prompts/vi-en-word.md`**

```markdown
version: 1
---
Bạn là giáo viên IELTS, giúp người Việt chọn đúng từ tiếng Anh học thuật.

Từ/cụm tiếng Việt: {{TEXT}}
Ngữ cảnh: {{CONTEXT}}

Trả về JSON đúng schema:
- best_en: từ tiếng Anh phù hợp nhất với ngữ cảnh. TỐI ĐA 4 từ. Đây là thứ hiển thị trong popup nhỏ.
- alternatives: 2 đến 4 lựa chọn khác. Mỗi lựa chọn gồm: term, band ước lượng (5.5, 6.0, 6.5, 7.0, 7.5, 8.0), register (academic, neutral, informal), và when_to_use viết bằng tiếng Việt nói rõ khi nào nên dùng từ này thay vì best_en.
- collocations: 3 đến 5 collocation học thuật đi kèm best_en.
- examples: đúng 2 câu tiếng Anh dùng best_en, viết ở mức band 6.5-7.0.

Quan trọng: đừng chọn từ hiếm chỉ vì nó nghe cao cấp. Dùng sai từ khó bị trừ điểm nặng hơn dùng đúng từ vừa phải.
```

- [ ] **Step 7: Viết `prompts/vi-en-sentence.md`**

Đây là prompt cốt lõi của tính năng "band 6.5+". Viết đầy đủ, không rút gọn.

```markdown
version: 1
---
Bạn là giáo viên IELTS Writing. Dịch câu tiếng Việt sau sang tiếng Anh học thuật.

Câu tiếng Việt: {{TEXT}}
Ngữ cảnh: {{CONTEXT}}

Bản dịch phải tương ứng band 6.5-7.0 theo hai tiêu chí sau của IELTS Writing Task 2.

LEXICAL RESOURCE band 6.5-7.0:
- Đủ vốn từ để diễn đạt linh hoạt và chính xác, có dùng một số từ ít phổ biến.
- Có ý thức về văn phong và collocation, dù đôi chỗ chưa hoàn hảo.
- Không dùng cách diễn đạt quá cơ bản như very good, a lot of, things, big problem.
- Không nhồi từ hiếm sai ngữ cảnh. Dùng sai từ khó bị trừ điểm nặng hơn dùng đúng từ vừa phải.

GRAMMATICAL RANGE AND ACCURACY band 6.5-7.0:
- Đa dạng cấu trúc câu, có câu phức.
- Phần lớn câu không có lỗi ngữ pháp.
- Có ít nhất một cấu trúc nâng cao dùng đúng chỗ: mệnh đề quan hệ, mệnh đề trạng ngữ, đảo ngữ, danh động từ làm chủ ngữ, hoặc bị động khi hợp lý.

Trả về JSON đúng schema:
- band65_version: bản dịch chính. Giữ nguyên nghĩa câu gốc, KHÔNG thêm ý mới, KHÔNG bỏ ý nào.
- why_notes: 2 đến 4 ghi chú bằng tiếng Việt giải thích vì sao chọn từ hoặc cấu trúc đó. Mỗi ghi chú phải chỉ đích danh từ/cụm cụ thể trong bản dịch, không nói chung chung.
- key_phrases: 2 đến 4 cụm đáng học thuộc, trích từ chính bản dịch.
- avoid: 2 đến 3 cách diễn đạt tiếng Anh quá cơ bản mà người học Việt Nam hay dùng cho câu này. Mỗi mục gồm cụm nên tránh và lý do ngắn bằng tiếng Việt.

Viết tự nhiên như người bản xứ viết học thuật, không viết cứng nhắc kiểu dịch máy.
```

- [ ] **Step 8: Viết `PromptTemplate.java`**

```java
package com.hiepnn.ieltstranslator.translation;

public record PromptTemplate(String body, int version) {

    private static final String NO_CONTEXT = "(không có ngữ cảnh)";

    public String render(String text, String context) {
        String safeContext = (context == null || context.isBlank()) ? NO_CONTEXT : context;
        return body.replace("{{TEXT}}", text == null ? "" : text)
                   .replace("{{CONTEXT}}", safeContext);
    }
}
```

- [ ] **Step 9: Viết `PromptLoader.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Đọc prompt từ classpath. Mỗi file có header "version: N", một dòng "---",
 * rồi tới nội dung. Version đi vào cache key nên sửa prompt là cache tự hết hiệu lực.
 */
@Component
public class PromptLoader {

    private final Map<String, PromptTemplate> cache = new ConcurrentHashMap<>();

    public PromptTemplate load(Direction direction, Mode mode) {
        String fileName = fileNameFor(direction, mode);
        return cache.computeIfAbsent(fileName, this::readTemplate);
    }

    private String fileNameFor(Direction direction, Mode mode) {
        String dir = direction == Direction.EN_VI ? "en-vi" : "vi-en";
        String md = mode == Mode.WORD ? "word" : "sentence";
        return "prompts/" + dir + "-" + md + ".md";
    }

    private PromptTemplate readTemplate(String path) {
        String raw;
        try {
            raw = new String(new ClassPathResource(path).getInputStream().readAllBytes(),
                             StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Không đọc được prompt: " + path, e);
        }

        // Quét theo dòng, chỉ chấp nhận dòng đúng bằng "---". Dùng indexOf("\n---")
        // sẽ khớp nhầm cả đường kẻ ngang markdown nằm trong thân prompt.
        String[] lines = raw.split("\n", -1);
        int separator = -1;
        for (int i = 0; i < lines.length; i++) {
            if (lines[i].strip().equals("---")) {
                separator = i;
                break;
            }
        }
        if (separator < 0) {
            throw new IllegalStateException("Prompt thiếu dòng phân cách '---': " + path);
        }
        String header = String.join("\n", Arrays.copyOfRange(lines, 0, separator)).trim();
        String body = String.join("\n",
                Arrays.copyOfRange(lines, separator + 1, lines.length)).trim();

        if (!header.startsWith("version:")) {
            throw new IllegalStateException("Prompt thiếu header 'version:': " + path);
        }
        int version;
        try {
            version = Integer.parseInt(header.substring("version:".length()).trim());
        } catch (NumberFormatException e) {
            throw new IllegalStateException("Prompt có version không phải số: " + path, e);
        }
        return new PromptTemplate(body, version);
    }
}
```

- [ ] **Step 10: Viết `TranslationSchemas.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Response schema gửi cho Gemini (tập con OpenAPI mà Gemini chấp nhận). */
public final class TranslationSchemas {

    private static final List<String> BANDS =
            List.of("5.5", "6.0", "6.5", "7.0", "7.5", "8.0");

    private TranslationSchemas() {}

    public static Map<String, Object> of(Direction direction, Mode mode) {
        if (direction == Direction.EN_VI) {
            return mode == Mode.WORD ? enViWord() : enViSentence();
        }
        return mode == Mode.WORD ? viEnWord() : viEnSentence();
    }

    private static Map<String, Object> enViWord() {
        return object(
                Map.of("term", str(), "lemma", str(), "pos", str(), "ipa", str(),
                       "meaning_vi", str(), "definition_en", str(),
                       "cefr", enumOf(List.of("A1", "A2", "B1", "B2", "C1", "C2")),
                       "band_level", enumOf(BANDS),
                       "register", enumOf(List.of("academic", "neutral", "informal")),
                       "collocations", arrayOf(str())),
                Map.of("examples", arrayOf(object(
                               Map.of("en", str(), "vi", str()), List.of("en", "vi"))),
                       "synonyms", arrayOf(object(
                               Map.of("term", str(), "band", enumOf(BANDS)), List.of("term", "band")))),
                List.of("term", "lemma", "pos", "ipa", "meaning_vi", "definition_en",
                        "cefr", "band_level", "register", "collocations", "examples", "synonyms"));
    }

    private static Map<String, Object> enViSentence() {
        return object(
                Map.of("translation_vi", str(),
                       "key_vocab", arrayOf(object(
                               Map.of("term", str(), "meaning_vi", str(), "band_level", enumOf(BANDS)),
                               List.of("term", "meaning_vi", "band_level"))),
                       "structure_note", str()),
                Map.of(),
                List.of("translation_vi", "key_vocab", "structure_note"));
    }

    private static Map<String, Object> viEnWord() {
        return object(
                Map.of("best_en", str(),
                       "alternatives", arrayOf(object(
                               Map.of("term", str(), "band", enumOf(BANDS),
                                      "register", enumOf(List.of("academic", "neutral", "informal")),
                                      "when_to_use", str()),
                               List.of("term", "band", "register", "when_to_use"))),
                       "collocations", arrayOf(str()),
                       "examples", arrayOf(str())),
                Map.of(),
                List.of("best_en", "alternatives", "collocations", "examples"));
    }

    private static Map<String, Object> viEnSentence() {
        return object(
                Map.of("band65_version", str(),
                       "why_notes", arrayOf(str()),
                       "key_phrases", arrayOf(str()),
                       "avoid", arrayOf(object(
                               Map.of("phrase", str(), "reason", str()),
                               List.of("phrase", "reason")))),
                Map.of(),
                List.of("band65_version", "why_notes", "key_phrases", "avoid"));
    }

    // --- helper dựng schema ---

    private static Map<String, Object> str() {
        return Map.of("type", "string");
    }

    private static Map<String, Object> enumOf(List<String> values) {
        return Map.of("type", "string", "enum", values);
    }

    private static Map<String, Object> arrayOf(Map<String, Object> items) {
        return Map.of("type", "array", "items", items);
    }

    private static Map<String, Object> object(Map<String, Object> props, List<String> required) {
        return object(props, Map.of(), required);
    }

    /** Gộp hai map property để né giới hạn 10 cặp của Map.of(). */
    private static Map<String, Object> object(Map<String, Object> propsA,
                                              Map<String, Object> propsB,
                                              List<String> required) {
        Map<String, Object> properties = new LinkedHashMap<>();
        properties.putAll(propsA);
        properties.putAll(propsB);
        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("type", "object");
        schema.put("properties", properties);
        schema.put("required", required);
        return schema;
    }
}
```

- [ ] **Step 11: Chạy test để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest='PromptLoaderTest,TranslationSchemasTest'`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add backend/src/main/resources/prompts backend/src/main/java/com/hiepnn/ieltstranslator/translation backend/src/test/java/com/hiepnn/ieltstranslator/translation
git commit -m "feat: 4 prompt template và response schema cho Gemini"
```

---

### Task 5: TranslationService, cache, POST /api/translate

**Files:**
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/cache/{LookupCache,LookupCacheRepository}.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/dto/{TranslateRequest,TranslateResponse}.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/translation/{TranslationService,TranslateController}.java`
- Create: `backend/src/test/java/com/hiepnn/ieltstranslator/AbstractPostgresIT.java`
- Modify: `backend/src/test/java/com/hiepnn/ieltstranslator/health/HealthControllerIT.java` (dùng base class)
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/TranslationServiceIT.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/translation/TranslateControllerIT.java`

**Interfaces:**
- Consumes: `LanguageDetector`, `Mode`, `PromptLoader`, `TranslationSchemas` (Task 2, 4), `GeminiClient` (Task 3), `AppException`/`ErrorCode` (Task 1)
- Produces: `record TranslateRequest(String text, String contextSentence, String sourceUrl, String pageTitle)`; `record TranslateResponse(Direction direction, Mode mode, boolean cached, JsonNode payload)`; `TranslationService.translate(TranslateRequest) → TranslateResponse`; `POST /api/translate`

- [ ] **Step 1: Tạo base class Testcontainers `AbstractPostgresIT.java`**

```java
package com.hiepnn.ieltstranslator;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers
public abstract class AbstractPostgresIT {

    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>("postgres:16-alpine");

    static {
        POSTGRES.start();   // dùng chung một container cho mọi test class
    }

    @DynamicPropertySource
    static void defaultProps(DynamicPropertyRegistry registry) {
        registry.add("gemini.api-key", () -> "test-key");
        registry.add("gemini.retry-backoff-millis", () -> 10L);
    }
}
```

Sửa `HealthControllerIT` thành `class HealthControllerIT extends AbstractPostgresIT`, bỏ các annotation `@SpringBootTest`, `@Testcontainers`, khối `@Container` và `@DynamicPropertySource` trùng lặp, giữ lại `@AutoConfigureMockMvc`.

- [ ] **Step 2: Viết test thất bại `TranslationServiceIT.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class TranslationServiceIT extends AbstractPostgresIT {

    @Autowired TranslationService service;
    @Autowired LookupCacheRepository cacheRepository;
    @Autowired ObjectMapper objectMapper;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void reset() {
        cacheRepository.deleteAll();
        when(geminiClient.generateJson(anyString(), any()))
                .thenReturn(objectMapper.createObjectNode().put("meaning_vi", "tái tạo"));
    }

    @Test
    void englishWordRoutesToEnViWordMode() {
        TranslateResponse response = service.translate(
                new TranslateRequest("renewable", "We need renewable energy.", null, null));

        assertThat(response.direction()).isEqualTo(Direction.EN_VI);
        assertThat(response.mode()).isEqualTo(Mode.WORD);
        assertThat(response.cached()).isFalse();
        assertThat(response.payload().get("meaning_vi").asText()).isEqualTo("tái tạo");
    }

    @Test
    void vietnameseSentenceRoutesToViEnSentenceMode() {
        TranslateResponse response = service.translate(new TranslateRequest(
                "Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo", null, null, null));

        assertThat(response.direction()).isEqualTo(Direction.VI_EN);
        assertThat(response.mode()).isEqualTo(Mode.SENTENCE);
    }

    @Test
    void firstCallHitsGeminiAndPersistsCache() {
        service.translate(new TranslateRequest("renewable", null, null, null));

        verify(geminiClient, times(1)).generateJson(anyString(), any());
        assertThat(cacheRepository.count()).isEqualTo(1);
    }

    @Test
    void secondIdenticalCallServesFromCacheWithoutCallingGemini() {
        TranslateRequest request = new TranslateRequest("renewable", null, null, null);

        service.translate(request);
        clearInvocations(geminiClient);
        TranslateResponse second = service.translate(request);

        verifyNoInteractions(geminiClient);
        assertThat(second.cached()).isTrue();
        assertThat(second.payload().get("meaning_vi").asText()).isEqualTo("tái tạo");
        assertThat(cacheRepository.count()).isEqualTo(1);
    }

    @Test
    void cacheHitIncrementsHitCount() {
        TranslateRequest request = new TranslateRequest("renewable", null, null, null);
        service.translate(request);
        service.translate(request);
        service.translate(request);

        assertThat(cacheRepository.findAll().get(0).getHitCount()).isEqualTo(2);
    }

    @Test
    void differentContextDoesNotShareCacheEntry() {
        service.translate(new TranslateRequest("renewable", "context A", null, null));
        service.translate(new TranslateRequest("renewable", "context B", null, null));

        assertThat(cacheRepository.count()).isEqualTo(2);
    }

    @Test
    void textOverLimitIsRejected() {
        String tooLong = "a".repeat(1501);

        assertThatThrownBy(() -> service.translate(new TranslateRequest(tooLong, null, null, null)))
                .isInstanceOf(com.hiepnn.ieltstranslator.common.AppException.class)
                .satisfies(ex -> assertThat(
                        ((com.hiepnn.ieltstranslator.common.AppException) ex).code())
                        .isEqualTo(com.hiepnn.ieltstranslator.common.ErrorCode.TEXT_TOO_LONG));

        verifyNoInteractions(geminiClient);
    }

    @Test
    void geminiIsCalledWithSchemaMatchingDetectedRoute() {
        service.translate(new TranslateRequest("renewable", null, null, null));

        verify(geminiClient).generateJson(anyString(),
                eq(TranslationSchemas.of(Direction.EN_VI, Mode.WORD)));
    }

    @Test
    void promptSentToGeminiContainsTheSelectedText() {
        service.translate(new TranslateRequest("renewable", "some context", null, null));

        verify(geminiClient).generateJson(
                argThat(prompt -> prompt.contains("renewable") && prompt.contains("some context")),
                any());
    }
}
```

- [ ] **Step 3: Chạy test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest=TranslationServiceIT`
Expected: FAIL — chưa có `TranslationService`, `LookupCacheRepository`, DTO.

- [ ] **Step 4: Viết entity `cache/LookupCache.java`**

```java
package com.hiepnn.ieltstranslator.translation.cache;

import com.fasterxml.jackson.databind.JsonNode;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import org.hibernate.annotations.Type;

import java.time.Instant;

@Entity
@Table(name = "lookup_cache")
public class LookupCache {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "source_hash", nullable = false, unique = true)
    private String sourceHash;

    @Column(name = "source_text", nullable = false)
    private String sourceText;

    @Column(nullable = false)
    private String direction;

    @Column(nullable = false)
    private String mode;

    @Column(nullable = false)
    private String model;

    @Column(name = "prompt_version", nullable = false)
    private int promptVersion;

    @Type(JsonType.class)
    @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode response;

    @Column(name = "hit_count", nullable = false)
    private int hitCount;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected LookupCache() {}

    public LookupCache(String sourceHash, String sourceText, String direction, String mode,
                       String model, int promptVersion, JsonNode response) {
        this.sourceHash = sourceHash;
        this.sourceText = sourceText;
        this.direction = direction;
        this.mode = mode;
        this.model = model;
        this.promptVersion = promptVersion;
        this.response = response;
        this.hitCount = 0;
        this.createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public JsonNode getResponse() { return response; }
    public int getHitCount() { return hitCount; }
}
```

- [ ] **Step 5: Viết `cache/LookupCacheRepository.java`**

```java
package com.hiepnn.ieltstranslator.translation.cache;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface LookupCacheRepository extends JpaRepository<LookupCache, Long> {

    Optional<LookupCache> findBySourceHash(String sourceHash);

    @Modifying
    @Query("UPDATE LookupCache c SET c.hitCount = c.hitCount + 1 WHERE c.id = :id")
    void incrementHitCount(@Param("id") Long id);
}
```

- [ ] **Step 6: Viết DTO `dto/TranslateRequest.java` và `dto/TranslateResponse.java`**

```java
package com.hiepnn.ieltstranslator.translation.dto;

import jakarta.validation.constraints.NotBlank;

public record TranslateRequest(
        @NotBlank String text,
        String contextSentence,
        String sourceUrl,
        String pageTitle
) {}
```

```java
package com.hiepnn.ieltstranslator.translation.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.translation.Direction;
import com.hiepnn.ieltstranslator.translation.Mode;

public record TranslateResponse(
        Direction direction,
        Mode mode,
        boolean cached,
        JsonNode payload
) {}
```

- [ ] **Step 7: Viết `TranslationService.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.common.gemini.GeminiProperties;
import com.hiepnn.ieltstranslator.translation.cache.LookupCache;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;

@Service
public class TranslationService {

    /** Giới hạn cứng phía server; content script cũng chặn ở cùng con số. */
    private static final int MAX_TEXT_LENGTH = 1500;

    private final LanguageDetector languageDetector;
    private final PromptLoader promptLoader;
    private final GeminiClient geminiClient;
    private final GeminiProperties geminiProperties;
    private final LookupCacheRepository cacheRepository;

    public TranslationService(LanguageDetector languageDetector,
                              PromptLoader promptLoader,
                              GeminiClient geminiClient,
                              GeminiProperties geminiProperties,
                              LookupCacheRepository cacheRepository) {
        this.languageDetector = languageDetector;
        this.promptLoader = promptLoader;
        this.geminiClient = geminiClient;
        this.geminiProperties = geminiProperties;
        this.cacheRepository = cacheRepository;
    }

    @Transactional
    public TranslateResponse translate(TranslateRequest request) {
        String text = request.text() == null ? "" : request.text().trim();
        if (text.length() > MAX_TEXT_LENGTH) {
            throw AppException.of(ErrorCode.TEXT_TOO_LONG,
                    "Đoạn bôi đen quá dài (tối đa " + MAX_TEXT_LENGTH + " ký tự)");
        }

        Direction direction = languageDetector.detect(text);
        Mode mode = Mode.of(text);
        PromptTemplate template = promptLoader.load(direction, mode);
        String context = request.contextSentence();
        String hash = cacheKey(text, context, direction, mode, template.version());

        Optional<LookupCache> cached = cacheRepository.findBySourceHash(hash);
        if (cached.isPresent()) {
            cacheRepository.incrementHitCount(cached.get().getId());
            return new TranslateResponse(direction, mode, true, cached.get().getResponse());
        }

        Map<String, Object> schema = TranslationSchemas.of(direction, mode);
        JsonNode payload = geminiClient.generateJson(template.render(text, context), schema);

        cacheRepository.save(new LookupCache(hash, text, direction.name(), mode.name(),
                geminiProperties.model(), template.version(), payload));

        return new TranslateResponse(direction, mode, false, payload);
    }

    private String cacheKey(String text, String context, Direction direction,
                            Mode mode, int promptVersion) {
        String material = String.join(" ",
                text,
                context == null ? "" : context,
                direction.name(),
                mode.name(),
                geminiProperties.model(),
                String.valueOf(promptVersion));
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(material.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("JVM không có SHA-256", e);
        }
    }
}
```

- [ ] **Step 8: Chạy test service để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest=TranslationServiceIT`
Expected: PASS, cả 9 test.

- [ ] **Step 9: Viết test thất bại `TranslateControllerIT.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.common.gemini.GeminiClient;
import com.hiepnn.ieltstranslator.translation.cache.LookupCacheRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class TranslateControllerIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired LookupCacheRepository cacheRepository;

    @MockitoBean GeminiClient geminiClient;

    @BeforeEach
    void reset() {
        cacheRepository.deleteAll();
    }

    @Test
    void returnsDirectionModeAndPayload() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenReturn(objectMapper.createObjectNode().put("meaning_vi", "tái tạo"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                 {"text":"renewable","contextSentence":"We need renewable energy."}
                                 """))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.direction").value("EN_VI"))
               .andExpect(jsonPath("$.mode").value("WORD"))
               .andExpect(jsonPath("$.cached").value(false))
               .andExpect(jsonPath("$.payload.meaning_vi").value("tái tạo"));
    }

    @Test
    void quotaErrorReturns429WithErrorShape() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_QUOTA, "Đã hết quota Gemini"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"renewable\"}"))
               .andExpect(status().isTooManyRequests())
               .andExpect(jsonPath("$.code").value("GEMINI_QUOTA"))
               .andExpect(jsonPath("$.retryable").value(false))
               .andExpect(jsonPath("$.message").isNotEmpty());
    }

    @Test
    void unavailableErrorReturns503AndIsMarkedRetryable() throws Exception {
        when(geminiClient.generateJson(anyString(), any()))
                .thenThrow(AppException.of(ErrorCode.GEMINI_UNAVAILABLE, "Gemini không phản hồi kịp"));

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"text\":\"renewable\"}"))
               .andExpect(status().isServiceUnavailable())
               .andExpect(jsonPath("$.code").value("GEMINI_UNAVAILABLE"))
               .andExpect(jsonPath("$.retryable").value(true));
    }

    @Test
    void textOverLimitReturns400() throws Exception {
        String tooLong = "a".repeat(1501);

        mockMvc.perform(post("/api/translate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                java.util.Map.of("text", tooLong))))
               .andExpect(status().isBadRequest())
               .andExpect(jsonPath("$.code").value("TEXT_TOO_LONG"));
    }
}
```

- [ ] **Step 10: Chạy test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest=TranslateControllerIT`
Expected: FAIL — 404, chưa có `TranslateController`.

- [ ] **Step 11: Viết `TranslateController.java`**

```java
package com.hiepnn.ieltstranslator.translation;

import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/translate")
public class TranslateController {

    private final TranslationService translationService;

    public TranslateController(TranslationService translationService) {
        this.translationService = translationService;
    }

    @PostMapping
    public TranslateResponse translate(@Valid @RequestBody TranslateRequest request) {
        return translationService.translate(request);
    }
}
```

- [ ] **Step 12: Chạy toàn bộ test backend**

Run: `cd backend && mvn -q test`
Expected: PASS toàn bộ.

- [ ] **Step 13: Commit**

```bash
git add backend/
git commit -m "feat: POST /api/translate với cache PostgreSQL"
```

---

### Task 6: Sổ từ vựng — lưu, tìm kiếm, xoá, export CSV

**Files:**
- Create: `backend/src/main/resources/db/migration/V2__vocab_entry.sql`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/{VocabEntry,VocabEntryRepository,VocabService,VocabController,CsvExporter}.java`
- Create: `backend/src/main/java/com/hiepnn/ieltstranslator/vocabulary/dto/{SaveVocabRequest,SaveVocabResponse,VocabEntryDto}.java`
- Test: `backend/src/test/java/com/hiepnn/ieltstranslator/vocabulary/{VocabServiceIT,CsvExporterTest,VocabControllerIT}.java`

**Interfaces:**
- Consumes: `AppException`, `ErrorCode` (Task 1)
- Produces: `SaveVocabRequest(String term, String lemma, String lang, String pos, String ipa, String meaningVi, String definitionEn, String cefr, String bandLevel, List<String> tags, String sourceUrl, String sourceSentence, JsonNode collocations, JsonNode examples)`; `SaveVocabResponse(Long id, boolean alreadyExists)`; `VocabService` với `save`, `search`, `findById`, `delete`, `exportCsv`; endpoints `POST /api/vocab`, `GET /api/vocab`, `GET /api/vocab/{id}`, `DELETE /api/vocab/{id}`, `GET /api/vocab/export.csv`

- [ ] **Step 1: Viết migration `V2__vocab_entry.sql`**

```sql
CREATE TABLE vocab_entry (
    id              BIGSERIAL   PRIMARY KEY,
    term            TEXT        NOT NULL,
    lemma           TEXT,
    lang            VARCHAR(8)  NOT NULL,
    pos             VARCHAR(16) NOT NULL DEFAULT '',
    ipa             TEXT,
    meaning_vi      TEXT        NOT NULL,
    definition_en   TEXT,
    cefr            VARCHAR(4),
    band_level      VARCHAR(8),
    tags            TEXT[]      NOT NULL DEFAULT '{}',
    source_url      TEXT,
    source_sentence TEXT,
    collocations    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    examples        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_vocab_term_pos UNIQUE (term, pos)
);

CREATE INDEX idx_vocab_created_at ON vocab_entry (created_at DESC);
CREATE INDEX idx_vocab_tags ON vocab_entry USING GIN (tags);
```

`pos` mặc định chuỗi rỗng thay vì NULL, vì NULL trong PostgreSQL không so sánh bằng nhau nên `UNIQUE (term, pos)` sẽ không chặn được trùng.

- [ ] **Step 2: Viết test thất bại `VocabServiceIT.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.PageRequest;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

class VocabServiceIT extends AbstractPostgresIT {

    @Autowired VocabService service;
    @Autowired VocabEntryRepository repository;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void reset() {
        repository.deleteAll();
    }

    private SaveVocabRequest request(String term, String pos, String meaning, List<String> tags) {
        return new SaveVocabRequest(term, term, "en", pos, "/test/", meaning,
                "an English definition", "B2", "6.5", tags,
                "https://example.com", "A source sentence.",
                objectMapper.createArrayNode().add("renewable energy"),
                objectMapper.createArrayNode());
    }

    @Test
    void savesNewEntry() {
        SaveVocabResponse response = service.save(request("renewable", "adj", "tái tạo", List.of()));

        assertThat(response.id()).isNotNull();
        assertThat(response.alreadyExists()).isFalse();
        assertThat(repository.count()).isEqualTo(1);
    }

    @Test
    void savingSameTermAndPosReturnsAlreadyExistsWithoutDuplicating() {
        SaveVocabResponse first = service.save(request("renewable", "adj", "tái tạo", List.of()));
        SaveVocabResponse second = service.save(request("renewable", "adj", "nghĩa khác", List.of()));

        assertThat(second.alreadyExists()).isTrue();
        assertThat(second.id()).isEqualTo(first.id());
        assertThat(repository.count()).isEqualTo(1);
    }

    @Test
    void existingEntryKeepsItsOriginalMeaning() {
        service.save(request("renewable", "adj", "tái tạo", List.of()));
        service.save(request("renewable", "adj", "nghĩa bị ghi đè", List.of()));

        assertThat(repository.findAll().get(0).getMeaningVi()).isEqualTo("tái tạo");
    }

    @Test
    void savingExistingEntryMergesNewTags() {
        service.save(request("renewable", "adj", "tái tạo", List.of("environment")));
        service.save(request("renewable", "adj", "tái tạo", List.of("environment", "writing")));

        assertThat(repository.findAll().get(0).getTags())
                .containsExactlyInAnyOrder("environment", "writing");
    }

    @Test
    void sameTermWithDifferentPosAreSeparateEntries() {
        service.save(request("run", "v", "chạy", List.of()));
        service.save(request("run", "n", "lượt chạy", List.of()));

        assertThat(repository.count()).isEqualTo(2);
    }

    @Test
    void searchMatchesTermSubstringCaseInsensitively() {
        service.save(request("renewable", "adj", "tái tạo", List.of()));
        service.save(request("mitigate", "v", "giảm nhẹ", List.of()));

        List<VocabEntryDto> found = service.search("RENEW", null, PageRequest.of(0, 20)).getContent();

        assertThat(found).hasSize(1);
        assertThat(found.get(0).term()).isEqualTo("renewable");
    }

    @Test
    void searchMatchesVietnameseMeaning() {
        service.save(request("mitigate", "v", "giảm nhẹ", List.of()));

        assertThat(service.search("giảm", null, PageRequest.of(0, 20)).getContent()).hasSize(1);
    }

    @Test
    void searchFiltersByTag() {
        service.save(request("renewable", "adj", "tái tạo", List.of("environment")));
        service.save(request("mitigate", "v", "giảm nhẹ", List.of("writing")));

        List<VocabEntryDto> found = service.search(null, "writing", PageRequest.of(0, 20)).getContent();

        assertThat(found).hasSize(1);
        assertThat(found.get(0).term()).isEqualTo("mitigate");
    }

    @Test
    void searchWithoutFiltersReturnsAllNewestFirst() {
        service.save(request("first", "n", "một", List.of()));
        service.save(request("second", "n", "hai", List.of()));

        List<VocabEntryDto> found = service.search(null, null, PageRequest.of(0, 20)).getContent();

        assertThat(found).extracting(VocabEntryDto::term).containsExactly("second", "first");
    }

    @Test
    void deleteRemovesEntry() {
        Long id = service.save(request("renewable", "adj", "tái tạo", List.of())).id();

        service.delete(id);

        assertThat(repository.count()).isZero();
    }

    @Test
    void deletingUnknownIdThrowsNotFound() {
        assertThatThrownBy(() -> service.delete(999999L))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code()).isEqualTo(ErrorCode.NOT_FOUND));
    }

    @Test
    void findByIdReturnsEntry() {
        Long id = service.save(request("renewable", "adj", "tái tạo", List.of())).id();

        assertThat(service.findById(id).term()).isEqualTo("renewable");
    }
}
```

- [ ] **Step 3: Viết test thất bại `CsvExporterTest.java`**

CSV là chỗ dễ hỏng âm thầm khi nghĩa tiếng Việt có dấu phẩy hoặc dấu ngoặc kép.

```java
package com.hiepnn.ieltstranslator.vocabulary;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CsvExporterTest {

    private final CsvExporter exporter = new CsvExporter();

    private VocabEntry entry(String term, String meaning, List<String> tags) {
        VocabEntry e = new VocabEntry();
        e.setTerm(term);
        e.setPos("adj");
        e.setIpa("/test/");
        e.setMeaningVi(meaning);
        e.setDefinitionEn("a definition");
        e.setCefr("B2");
        e.setBandLevel("6.5");
        e.setTags(tags.toArray(new String[0]));
        e.setSourceUrl("https://example.com");
        e.setCreatedAt(Instant.parse("2026-08-03T10:15:30Z"));
        return e;
    }

    @Test
    void writesHeaderRow() {
        String csv = exporter.toCsv(List.of());

        assertThat(csv.lines().findFirst()).contains(
                "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at");
    }

    @Test
    void writesOneRowPerEntry() {
        String csv = exporter.toCsv(List.of(
                entry("renewable", "tái tạo", List.of("environment")),
                entry("mitigate", "giảm nhẹ", List.of())));

        assertThat(csv.lines().count()).isEqualTo(3);   // header + 2 dòng
    }

    @Test
    void quotesFieldContainingComma() {
        String csv = exporter.toCsv(List.of(entry("renewable", "tái tạo, phục hồi", List.of())));

        assertThat(csv).contains("\"tái tạo, phục hồi\"");
    }

    @Test
    void escapesDoubleQuoteByDoubling() {
        String csv = exporter.toCsv(List.of(entry("renewable", "nghĩa \"đặc biệt\"", List.of())));

        assertThat(csv).contains("\"nghĩa \"\"đặc biệt\"\"\"");
    }

    @Test
    void quotesFieldContainingNewline() {
        String csv = exporter.toCsv(List.of(entry("renewable", "dòng một\ndòng hai", List.of())));

        assertThat(csv).contains("\"dòng một\ndòng hai\"");
    }

    @Test
    void joinsTagsWithSemicolon() {
        String csv = exporter.toCsv(List.of(entry("renewable", "tái tạo", List.of("a", "b"))));

        assertThat(csv).contains("a;b");
    }
}
```

- [ ] **Step 4: Chạy cả hai test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest='VocabServiceIT,CsvExporterTest'`
Expected: FAIL — chưa có class trong package `vocabulary`.

- [ ] **Step 5: Viết entity `VocabEntry.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.JsonNode;
import io.hypersistence.utils.hibernate.type.array.StringArrayType;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import org.hibernate.annotations.Type;

import java.time.Instant;

@Entity
@Table(name = "vocab_entry")
public class VocabEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String term;

    private String lemma;

    @Column(nullable = false)
    private String lang;

    @Column(nullable = false)
    private String pos = "";

    private String ipa;

    @Column(name = "meaning_vi", nullable = false)
    private String meaningVi;

    @Column(name = "definition_en")
    private String definitionEn;

    private String cefr;

    @Column(name = "band_level")
    private String bandLevel;

    @Type(StringArrayType.class)
    @Column(columnDefinition = "text[]", nullable = false)
    private String[] tags = new String[0];

    @Column(name = "source_url")
    private String sourceUrl;

    @Column(name = "source_sentence")
    private String sourceSentence;

    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private JsonNode collocations;

    @Type(JsonType.class)
    @Column(columnDefinition = "jsonb", nullable = false)
    private JsonNode examples;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public String getTerm() { return term; }
    public void setTerm(String term) { this.term = term; }
    public String getLemma() { return lemma; }
    public void setLemma(String lemma) { this.lemma = lemma; }
    public String getLang() { return lang; }
    public void setLang(String lang) { this.lang = lang; }
    public String getPos() { return pos; }
    public void setPos(String pos) { this.pos = pos == null ? "" : pos; }
    public String getIpa() { return ipa; }
    public void setIpa(String ipa) { this.ipa = ipa; }
    public String getMeaningVi() { return meaningVi; }
    public void setMeaningVi(String meaningVi) { this.meaningVi = meaningVi; }
    public String getDefinitionEn() { return definitionEn; }
    public void setDefinitionEn(String definitionEn) { this.definitionEn = definitionEn; }
    public String getCefr() { return cefr; }
    public void setCefr(String cefr) { this.cefr = cefr; }
    public String getBandLevel() { return bandLevel; }
    public void setBandLevel(String bandLevel) { this.bandLevel = bandLevel; }
    public String[] getTags() { return tags; }
    public void setTags(String[] tags) { this.tags = tags == null ? new String[0] : tags; }
    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }
    public String getSourceSentence() { return sourceSentence; }
    public void setSourceSentence(String s) { this.sourceSentence = s; }
    public JsonNode getCollocations() { return collocations; }
    public void setCollocations(JsonNode collocations) { this.collocations = collocations; }
    public JsonNode getExamples() { return examples; }
    public void setExamples(JsonNode examples) { this.examples = examples; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
```

- [ ] **Step 6: Viết `VocabEntryRepository.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface VocabEntryRepository extends JpaRepository<VocabEntry, Long> {

    Optional<VocabEntry> findByTermAndPos(String term, String pos);

    List<VocabEntry> findAllByOrderByCreatedAtDesc();

    @Query(value = """
            SELECT * FROM vocab_entry
            WHERE (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            ORDER BY created_at DESC
            """,
            countQuery = """
            SELECT count(*) FROM vocab_entry
            WHERE (CAST(:q AS text) IS NULL
                   OR term ILIKE '%' || CAST(:q AS text) || '%'
                   OR meaning_vi ILIKE '%' || CAST(:q AS text) || '%')
              AND (CAST(:tag AS text) IS NULL
                   OR tags @> ARRAY[CAST(:tag AS text)])
            """,
            nativeQuery = true)
    Page<VocabEntry> search(@Param("q") String q, @Param("tag") String tag, Pageable pageable);
}
```

`CAST(:q AS text)` là bắt buộc — không có nó PostgreSQL không suy được kiểu của tham số khi so với NULL và sẽ báo lỗi.

- [ ] **Step 7: Viết DTO**

```java
package com.hiepnn.ieltstranslator.vocabulary.dto;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

public record SaveVocabRequest(
        @NotBlank String term,
        String lemma,
        @NotBlank String lang,
        String pos,
        String ipa,
        @NotBlank String meaningVi,
        String definitionEn,
        String cefr,
        String bandLevel,
        List<String> tags,
        String sourceUrl,
        String sourceSentence,
        JsonNode collocations,
        JsonNode examples
) {}
```

```java
package com.hiepnn.ieltstranslator.vocabulary.dto;

public record SaveVocabResponse(Long id, boolean alreadyExists) {}
```

```java
package com.hiepnn.ieltstranslator.vocabulary.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.time.Instant;
import java.util.List;

public record VocabEntryDto(
        Long id, String term, String lemma, String lang, String pos, String ipa,
        String meaningVi, String definitionEn, String cefr, String bandLevel,
        List<String> tags, String sourceUrl, String sourceSentence,
        JsonNode collocations, JsonNode examples, Instant createdAt
) {}
```

- [ ] **Step 8: Viết `CsvExporter.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import org.springframework.stereotype.Component;

import java.util.List;
import java.util.stream.Collectors;

@Component
public class CsvExporter {

    private static final String HEADER =
            "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at";

    public String toCsv(List<VocabEntry> entries) {
        StringBuilder sb = new StringBuilder(HEADER);
        for (VocabEntry e : entries) {
            sb.append('\n')
              .append(String.join(",",
                      escape(e.getTerm()),
                      escape(e.getPos()),
                      escape(e.getIpa()),
                      escape(e.getMeaningVi()),
                      escape(e.getDefinitionEn()),
                      escape(e.getCefr()),
                      escape(e.getBandLevel()),
                      escape(String.join(";", e.getTags())),
                      escape(e.getSourceUrl()),
                      escape(e.getCreatedAt() == null ? "" : e.getCreatedAt().toString())));
        }
        return sb.toString();
    }

    /** Bọc dấu ngoặc kép khi field chứa dấu phẩy, ngoặc kép hoặc xuống dòng (RFC 4180). */
    private String escape(String value) {
        if (value == null) {
            return "";
        }
        if (value.contains(",") || value.contains("\"") || value.contains("\n") || value.contains("\r")) {
            return '"' + value.replace("\"", "\"\"") + '"';
        }
        return value;
    }
}
```

- [ ] **Step 9: Viết `VocabService.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

@Service
public class VocabService {

    private final VocabEntryRepository repository;
    private final CsvExporter csvExporter;
    private final ObjectMapper objectMapper;

    public VocabService(VocabEntryRepository repository, CsvExporter csvExporter,
                        ObjectMapper objectMapper) {
        this.repository = repository;
        this.csvExporter = csvExporter;
        this.objectMapper = objectMapper;
    }

    /**
     * Lưu từ mới. Nếu (term, pos) đã có thì KHÔNG ghi đè nội dung cũ — chỉ gộp
     * thêm tag mới — và báo alreadyExists để UI hiện "Đã có trong sổ".
     */
    @Transactional
    public SaveVocabResponse save(SaveVocabRequest request) {
        String pos = request.pos() == null ? "" : request.pos();
        Optional<VocabEntry> existing = repository.findByTermAndPos(request.term(), pos);

        if (existing.isPresent()) {
            VocabEntry entry = existing.get();
            mergeTags(entry, request.tags());
            return new SaveVocabResponse(entry.getId(), true);
        }

        VocabEntry entry = new VocabEntry();
        entry.setTerm(request.term());
        entry.setLemma(request.lemma());
        entry.setLang(request.lang());
        entry.setPos(pos);
        entry.setIpa(request.ipa());
        entry.setMeaningVi(request.meaningVi());
        entry.setDefinitionEn(request.definitionEn());
        entry.setCefr(request.cefr());
        entry.setBandLevel(request.bandLevel());
        entry.setTags(request.tags() == null ? new String[0] : request.tags().toArray(new String[0]));
        entry.setSourceUrl(request.sourceUrl());
        entry.setSourceSentence(request.sourceSentence());
        entry.setCollocations(request.collocations() == null
                ? objectMapper.createArrayNode() : request.collocations());
        entry.setExamples(request.examples() == null
                ? objectMapper.createArrayNode() : request.examples());

        return new SaveVocabResponse(repository.save(entry).getId(), false);
    }

    private void mergeTags(VocabEntry entry, List<String> incoming) {
        if (incoming == null || incoming.isEmpty()) {
            return;
        }
        Set<String> merged = new LinkedHashSet<>(List.of(entry.getTags()));
        merged.addAll(incoming);
        entry.setTags(merged.toArray(new String[0]));
    }

    @Transactional(readOnly = true)
    public Page<VocabEntryDto> search(String q, String tag, Pageable pageable) {
        String normalisedQ = (q == null || q.isBlank()) ? null : q;
        String normalisedTag = (tag == null || tag.isBlank()) ? null : tag;
        return repository.search(normalisedQ, normalisedTag, pageable).map(this::toDto);
    }

    @Transactional(readOnly = true)
    public VocabEntryDto findById(Long id) {
        return repository.findById(id).map(this::toDto)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id));
    }

    @Transactional
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id);
        }
        repository.deleteById(id);
    }

    @Transactional(readOnly = true)
    public String exportCsv() {
        return csvExporter.toCsv(repository.findAllByOrderByCreatedAtDesc());
    }

    private VocabEntryDto toDto(VocabEntry e) {
        return new VocabEntryDto(e.getId(), e.getTerm(), e.getLemma(), e.getLang(), e.getPos(),
                e.getIpa(), e.getMeaningVi(), e.getDefinitionEn(), e.getCefr(), e.getBandLevel(),
                List.of(e.getTags()), e.getSourceUrl(), e.getSourceSentence(),
                e.getCollocations(), e.getExamples(), e.getCreatedAt());
    }
}
```

- [ ] **Step 10: Chạy test service và CSV để xác nhận pass**

Run: `cd backend && mvn -q test -Dtest='VocabServiceIT,CsvExporterTest'`
Expected: PASS

- [ ] **Step 11: Viết test thất bại `VocabControllerIT.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class VocabControllerIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired VocabEntryRepository repository;

    private static final String BODY = """
            {"term":"renewable","lemma":"renewable","lang":"en","pos":"adj",
             "ipa":"/rɪˈnjuːəbl/","meaningVi":"tái tạo","definitionEn":"able to be renewed",
             "cefr":"B2","bandLevel":"6.5","tags":["environment"],
             "sourceUrl":"https://example.com","sourceSentence":"We need renewable energy.",
             "collocations":["renewable energy"],"examples":[]}
            """;

    @BeforeEach
    void reset() {
        repository.deleteAll();
    }

    @Test
    void savesAndReturnsId() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.id").isNumber())
               .andExpect(jsonPath("$.alreadyExists").value(false));
    }

    @Test
    void secondSaveReportsAlreadyExists() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.alreadyExists").value(true));
    }

    @Test
    void searchReturnsPagedResult() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(get("/api/vocab").param("q", "renew"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.content[0].term").value("renewable"))
               .andExpect(jsonPath("$.totalElements").value(1));
    }

    @Test
    void deleteReturns204ThenGetReturns404() throws Exception {
        String response = mockMvc.perform(post("/api/vocab")
                        .contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andReturn().getResponse().getContentAsString();
        long id = com.jayway.jsonpath.JsonPath.parse(response).read("$.id", Integer.class);

        mockMvc.perform(delete("/api/vocab/" + id)).andExpect(status().isNoContent());
        mockMvc.perform(get("/api/vocab/" + id))
               .andExpect(status().isNotFound())
               .andExpect(jsonPath("$.code").value("NOT_FOUND"));
    }

    @Test
    void exportReturnsCsvWithHeaderRow() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(get("/api/vocab/export.csv"))
               .andExpect(status().isOk())
               .andExpect(header().string("Content-Disposition",
                       "attachment; filename=\"vocabulary.csv\""))
               .andExpect(content().string(org.hamcrest.Matchers.startsWith("term,pos,ipa")))
               .andExpect(content().string(org.hamcrest.Matchers.containsString("renewable")));
    }
}
```

- [ ] **Step 12: Chạy test để xác nhận thất bại**

Run: `cd backend && mvn -q test -Dtest=VocabControllerIT`
Expected: FAIL — 404, chưa có `VocabController`.

- [ ] **Step 13: Viết `VocabController.java`**

```java
package com.hiepnn.ieltstranslator.vocabulary;

import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/vocab")
public class VocabController {

    private final VocabService vocabService;

    public VocabController(VocabService vocabService) {
        this.vocabService = vocabService;
    }

    @PostMapping
    public SaveVocabResponse save(@Valid @RequestBody SaveVocabRequest request) {
        return vocabService.save(request);
    }

    @GetMapping
    public Page<VocabEntryDto> search(@RequestParam(required = false) String q,
                                      @RequestParam(required = false) String tag,
                                      @RequestParam(defaultValue = "0") int page,
                                      @RequestParam(defaultValue = "20") int size) {
        return vocabService.search(q, tag, PageRequest.of(page, Math.min(size, 100)));
    }

    @GetMapping("/{id}")
    public VocabEntryDto findById(@PathVariable Long id) {
        return vocabService.findById(id);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        vocabService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping(value = "/export.csv", produces = "text/csv")
    public ResponseEntity<String> exportCsv() {
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"vocabulary.csv\"")
                .contentType(MediaType.parseMediaType("text/csv; charset=UTF-8"))
                .body(vocabService.exportCsv());
    }
}
```

Lưu ý: `/export.csv` phải khai báo trước `/{id}` trong tư duy routing — Spring khớp path cụ thể trước path biến nên thứ tự trong file không quan trọng, nhưng nếu sau này đổi sang `/{id}` kiểu String thì phải kiểm tra lại.

- [ ] **Step 14: Chạy toàn bộ test backend**

Run: `cd backend && mvn -q test`
Expected: PASS toàn bộ. Backend Phase 1 hoàn tất.

- [ ] **Step 15: Commit**

```bash
git add backend/
git commit -m "feat: sổ từ vựng — lưu, tìm kiếm, xoá, export CSV"
```

---

### Task 7: Extension scaffold, extension ID cố định, shared types

**Files:**
- Create: `extension/{package.json,vite.config.ts,tsconfig.json,manifest.config.ts,vitest.setup.ts}`
- Create: `extension/key.pem` (KHÔNG commit), `extension/src/shared/{types.ts,summary.ts,settings.ts,messages.ts}`
- Modify: `.gitignore` (thêm `extension/key.pem`)
- Modify: `.env` (điền `EXTENSION_ID`)
- Test: `extension/src/shared/{summary.test.ts,settings.test.ts}`

**Interfaces:**
- Consumes: hình dạng JSON của backend (Task 4, 5, 6)
- Produces: types `Direction`, `Mode`, `TranslateResult`, `ApiError`, 4 payload interface, `VocabEntryDto`, `PageResponse<T>`; `shortMeaning(result: TranslateResult): string`; `Settings`, `DEFAULT_SETTINGS`, `loadSettings()`, `saveSettings(patch)`; message union `ExtensionRequest` / `ExtensionResponse`

- [ ] **Step 1: Sinh cặp khoá và tính extension ID cố định**

Run:
```bash
mkdir -p extension
openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -nocrypt -out extension/key.pem
echo "PUBLIC KEY (dán vào manifest.config.ts):"
openssl rsa -in extension/key.pem -pubout -outform DER 2>/dev/null | base64 | tr -d '\n'
echo ""
echo "EXTENSION ID (dán vào .env):"
openssl rsa -in extension/key.pem -pubout -outform DER 2>/dev/null \
  | openssl dgst -sha256 -binary | head -c 16 | xxd -p | tr '0-9a-f' 'a-p'
```

Ghi lại cả hai giá trị. Thêm `extension/key.pem` vào `.gitignore` và điền `EXTENSION_ID=<giá trị vừa in>` vào `.env`.

- [ ] **Step 2: Tạo `extension/package.json`**

```json
{
  "name": "ielts-translator-extension",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@crxjs/vite-plugin": "^2.0.0-beta.28",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/chrome": "^0.0.287",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^25.0.1",
    "typescript": "^5.7.2",
    "vite": "^5.4.11",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 3: Tạo `extension/manifest.config.ts`**

Thay `<PUBLIC_KEY>` bằng chuỗi base64 in ra ở Step 1.

```ts
import { defineManifest } from '@crxjs/vite-plugin';

export default defineManifest({
  manifest_version: 3,
  name: 'IELTS Translator',
  version: '0.1.0',
  description: 'Dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+ và học từ mới',
  key: '<PUBLIC_KEY>',
  permissions: ['storage', 'sidePanel'],
  host_permissions: ['http://127.0.0.1:8080/*'],
  action: { default_title: 'IELTS Translator' },
  background: { service_worker: 'src/background/service-worker.ts', type: 'module' },
  side_panel: { default_path: 'src/sidepanel/index.html' },
  options_page: 'src/options/index.html',
  content_scripts: [
    {
      matches: ['<all_urls>'],
      js: ['src/content/index.ts'],
      run_at: 'document_idle',
    },
  ],
  commands: {
    'translate-selection': {
      suggested_key: { default: 'Alt+T' },
      description: 'Dịch đoạn đang bôi đen',
    },
  },
});
```

- [ ] **Step 4: Tạo `extension/vite.config.ts`, `tsconfig.json`, `vitest.setup.ts`**

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { crx } from '@crxjs/vite-plugin';
import manifest from './manifest.config';

export default defineConfig({
  plugins: [react(), crx({ manifest })],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
});
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["chrome", "vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "manifest.config.ts", "vite.config.ts", "vitest.setup.ts"]
}
```

```ts
// vitest.setup.ts
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// chrome.storage.local giả lập bằng Map, đủ cho mọi test Phase 1
const store = new Map<string, unknown>();

vi.stubGlobal('chrome', {
  storage: {
    local: {
      get: async (keys: string[]) => {
        const result: Record<string, unknown> = {};
        for (const key of keys) {
          if (store.has(key)) result[key] = store.get(key);
        }
        return result;
      },
      set: async (items: Record<string, unknown>) => {
        for (const [key, value] of Object.entries(items)) store.set(key, value);
      },
      clear: async () => store.clear(),
    },
  },
  runtime: { sendMessage: vi.fn(), lastError: undefined },
  sidePanel: { open: vi.fn(), setPanelBehavior: vi.fn() },
});
```

- [ ] **Step 5: Viết `src/shared/types.ts`**

```ts
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
```

- [ ] **Step 6: Viết test thất bại `src/shared/summary.test.ts`**

Bubble phải rút được một dòng ngắn từ cả 4 hình dạng payload — đây là chỗ dễ vỡ khi payload đổi.

```ts
import { describe, it, expect } from 'vitest';
import { shortMeaning } from './summary';
import type { TranslateResult } from './types';

const base = { cached: false, sourceText: 'x' };

describe('shortMeaning', () => {
  it('lấy meaning_vi cho EN→VI tra từ', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD',
      payload: { meaning_vi: 'tái tạo' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('tái tạo');
  });

  it('lấy translation_vi cho EN→VI tra câu', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'SENTENCE',
      payload: { translation_vi: 'Chính phủ nên đầu tư nhiều hơn.' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('Chính phủ nên đầu tư nhiều hơn.');
  });

  it('lấy best_en cho VI→EN tra từ', () => {
    const result = {
      ...base, direction: 'VI_EN', mode: 'WORD',
      payload: { best_en: 'renewable' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('renewable');
  });

  it('lấy band65_version cho VI→EN tra câu', () => {
    const result = {
      ...base, direction: 'VI_EN', mode: 'SENTENCE',
      payload: { band65_version: 'The government should invest more.' },
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('The government should invest more.');
  });

  it('trả chuỗi rỗng khi payload thiếu trường mong đợi', () => {
    const result = {
      ...base, direction: 'EN_VI', mode: 'WORD', payload: {},
    } as TranslateResult;

    expect(shortMeaning(result)).toBe('');
  });
});
```

- [ ] **Step 7: Viết test thất bại `src/shared/settings.test.ts`**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from './settings';

describe('settings', () => {
  beforeEach(async () => {
    await chrome.storage.local.clear();
  });

  it('trả về mặc định khi chưa lưu gì', async () => {
    expect(await loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it('lưu rồi đọc lại đúng giá trị', async () => {
    await saveSettings({ triggerMode: 'hotkey' });

    expect((await loadSettings()).triggerMode).toBe('hotkey');
  });

  it('gộp giá trị đã lưu lên trên mặc định, không mất field khác', async () => {
    await saveSettings({ backendUrl: 'http://localhost:9999' });

    const settings = await loadSettings();
    expect(settings.backendUrl).toBe('http://localhost:9999');
    expect(settings.triggerMode).toBe(DEFAULT_SETTINGS.triggerMode);
  });

  it('bỏ qua field lạ còn sót trong storage', async () => {
    await chrome.storage.local.set({ settings: { backendUrl: 'http://x', obsoleteField: 1 } });

    expect(await loadSettings()).not.toHaveProperty('obsoleteField');
  });

  it('cắt dấu / thừa ở cuối backendUrl', async () => {
    await saveSettings({ backendUrl: 'http://127.0.0.1:8080/' });

    expect((await loadSettings()).backendUrl).toBe('http://127.0.0.1:8080');
  });
});
```

- [ ] **Step 8: Cài dependency và chạy test để xác nhận thất bại**

Run: `cd extension && npm install && npm test`
Expected: FAIL — chưa có `summary.ts`, `settings.ts`.

- [ ] **Step 9: Viết `src/shared/summary.ts`**

```ts
import type { TranslateResult } from './types';

/** Rút một dòng ngắn để hiện trong bubble, bất kể payload thuộc hình dạng nào. */
export function shortMeaning(result: TranslateResult): string {
  const payload = result.payload as Record<string, unknown>;
  const key =
    result.direction === 'EN_VI'
      ? result.mode === 'WORD'
        ? 'meaning_vi'
        : 'translation_vi'
      : result.mode === 'WORD'
        ? 'best_en'
        : 'band65_version';

  const value = payload[key];
  return typeof value === 'string' ? value : '';
}
```

- [ ] **Step 10: Viết `src/shared/settings.ts`**

```ts
export type TriggerMode = 'auto' | 'hotkey';

export interface Settings {
  backendUrl: string;
  triggerMode: TriggerMode;
  voiceName: string | null;
}

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: 'http://127.0.0.1:8080',
  triggerMode: 'auto',
  voiceName: null,
};

const STORAGE_KEY = 'settings';

function normalise(raw: Partial<Settings>): Settings {
  const merged = { ...DEFAULT_SETTINGS, ...raw };
  return {
    backendUrl: merged.backendUrl.replace(/\/+$/, ''),
    triggerMode: merged.triggerMode === 'hotkey' ? 'hotkey' : 'auto',
    voiceName: merged.voiceName ?? null,
  };
}

export async function loadSettings(): Promise<Settings> {
  const stored = await chrome.storage.local.get([STORAGE_KEY]);
  return normalise((stored[STORAGE_KEY] ?? {}) as Partial<Settings>);
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const next = normalise({ ...(await loadSettings()), ...patch });
  await chrome.storage.local.set({ [STORAGE_KEY]: next });
  return next;
}
```

- [ ] **Step 11: Viết `src/shared/messages.ts`**

```ts
import type { ApiError, PageResponse, SaveVocabResponse, TranslateResult, VocabEntryDto } from './types';

export interface TranslateSelectionRequest {
  type: 'TRANSLATE_SELECTION';
  text: string;
  contextSentence: string | null;
  sourceUrl: string;
  pageTitle: string;
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

export type ExtensionRequest =
  | TranslateSelectionRequest
  | OpenPanelRequest
  | SaveWordRequest
  | SearchVocabRequest
  | DeleteVocabRequest
  | GetLastResultRequest
  | HealthRequest;

export type ExtensionResponse<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export interface ResponseMap {
  TRANSLATE_SELECTION: TranslateResult;
  OPEN_PANEL_WITH_RESULT: null;
  SAVE_WORD: SaveVocabResponse;
  SEARCH_VOCAB: PageResponse<VocabEntryDto>;
  DELETE_VOCAB: null;
  GET_LAST_RESULT: TranslateResult | null;
  CHECK_HEALTH: { status: string; dbConnected: boolean; geminiConfigured: boolean };
}

/** Gửi message tới service worker và nhận về kết quả đã phân biệt ok/lỗi. */
export async function sendToBackground<R extends ExtensionRequest>(
  request: R,
): Promise<ExtensionResponse<ResponseMap[R['type']]>> {
  return chrome.runtime.sendMessage(request);
}
```

- [ ] **Step 12: Chạy test để xác nhận pass**

Run: `cd extension && npm test`
Expected: PASS, 10 test.

- [ ] **Step 13: Xác nhận build được**

Run: `cd extension && npm run build`
Expected: build thành công, sinh thư mục `dist/`. Chưa load vào Chrome được vì các entry point còn trống — sẽ hoàn thiện ở Task 8-12.

- [ ] **Step 14: Commit**

```bash
git add .gitignore extension/package.json extension/package-lock.json extension/vite.config.ts extension/tsconfig.json extension/manifest.config.ts extension/vitest.setup.ts extension/src/shared
git commit -m "feat: scaffold extension với Vite/CRXJS, shared types và settings"
```

---

### Task 8: Service worker — API client, health cache, định tuyến message

Service worker là chỗ duy nhất chạm mạng nên toàn bộ ánh xạ lỗi phải đúng ở đây.

**Files:**
- Create: `extension/src/background/{api-client.ts,service-worker.ts}`
- Test: `extension/src/background/api-client.test.ts`

**Interfaces:**
- Consumes: `Settings` (Task 7), types và message union (Task 7)
- Produces: `ApiClient` class với `translate()`, `saveVocab()`, `searchVocab()`, `deleteVocab()`, `health()`; `toApiError(unknown): ApiError`

- [ ] **Step 1: Viết test thất bại `src/background/api-client.test.ts`**

```ts
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { ApiClient } from './api-client';

const BASE_URL = 'http://127.0.0.1:8080';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let client: ApiClient;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    client = new ApiClient(() => Promise.resolve(BASE_URL));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('POST /api/translate và gắn sourceText vào kết quả', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      direction: 'EN_VI', mode: 'WORD', cached: false, payload: { meaning_vi: 'tái tạo' },
    }));

    const result = await client.translate({
      text: 'renewable', contextSentence: 'We need renewable energy.',
      sourceUrl: 'https://example.com', pageTitle: 'Example',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/translate`,
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.sourceText).toBe('renewable');
    expect(result.sourceSentence).toBe('We need renewable energy.');
  });

  it('ném đúng ApiError khi backend trả lỗi có cấu trúc', async () => {
    fetchMock.mockResolvedValue(jsonResponse(
      { code: 'GEMINI_QUOTA', message: 'Đã hết quota Gemini', retryable: false }, 429));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'GEMINI_QUOTA', retryable: false });
  });

  it('ánh xạ lỗi mạng thành BACKEND_DOWN và đánh dấu retryable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'BACKEND_DOWN', retryable: true });
  });

  it('ánh xạ phản hồi không phải JSON thành INTERNAL', async () => {
    fetchMock.mockResolvedValue(new Response('<html>lỗi</html>', { status: 500 }));

    await expect(client.translate({
      text: 'x', contextSentence: null, sourceUrl: '', pageTitle: '',
    })).rejects.toMatchObject({ code: 'INTERNAL' });
  });

  it('cache kết quả health trong 30 giây', async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(jsonResponse({
      status: 'UP', dbConnected: true, geminiConfigured: true,
    }));

    await client.health();
    await client.health();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(31_000);
    await client.health();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('không cache health khi lần gọi trước thất bại', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(client.health()).rejects.toMatchObject({ code: 'BACKEND_DOWN' });

    fetchMock.mockResolvedValue(jsonResponse({
      status: 'UP', dbConnected: true, geminiConfigured: true,
    }));
    await client.health();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('searchVocab dựng đúng query string, bỏ tham số rỗng', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      content: [], totalElements: 0, totalPages: 0, number: 0,
    }));

    await client.searchVocab({ query: 'renew', tag: null, page: 2 });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('q=renew');
    expect(calledUrl).toContain('page=2');
    expect(calledUrl).not.toContain('tag=');
  });

  it('deleteVocab gọi đúng method DELETE', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await client.deleteVocab(42);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE_URL}/api/vocab/42`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `cd extension && npm test -- api-client`
Expected: FAIL — chưa có `api-client.ts`.

- [ ] **Step 3: Viết `src/background/api-client.ts`**

```ts
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
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `cd extension && npm test -- api-client`
Expected: PASS, 8 test.

- [ ] **Step 5: Viết `src/background/service-worker.ts`**

```ts
import { ApiClient } from './api-client';
import { loadSettings } from '../shared/settings';
import type { ExtensionRequest, ExtensionResponse } from '../shared/messages';
import type { ApiError, TranslateResult } from '../shared/types';

const client = new ApiClient(async () => (await loadSettings()).backendUrl);

/** Kết quả dịch gần nhất, để side panel đọc lại khi vừa mở. */
let lastResult: TranslateResult | null = null;

function toApiError(error: unknown): ApiError {
  if (error && typeof error === 'object' && 'code' in error) {
    return error as ApiError;
  }
  return { code: 'INTERNAL', message: 'Lỗi không xác định trong extension', retryable: false };
}

async function handle(request: ExtensionRequest, senderTabId?: number): Promise<unknown> {
  switch (request.type) {
    case 'TRANSLATE_SELECTION': {
      const result = await client.translate({
        text: request.text,
        contextSentence: request.contextSentence,
        sourceUrl: request.sourceUrl,
        pageTitle: request.pageTitle,
      });
      lastResult = result;
      return result;
    }
    case 'OPEN_PANEL_WITH_RESULT': {
      lastResult = request.result;
      if (senderTabId !== undefined) {
        await chrome.sidePanel.open({ tabId: senderTabId });
      }
      return null;
    }
    case 'GET_LAST_RESULT':
      return lastResult;
    case 'SAVE_WORD':
      return client.saveVocab(buildVocabPayload(request.result, request.tags));
    case 'SEARCH_VOCAB':
      return client.searchVocab({ query: request.query, tag: request.tag, page: request.page });
    case 'DELETE_VOCAB':
      return client.deleteVocab(request.id);
    case 'CHECK_HEALTH':
      return client.health();
  }
}

/** Chuyển kết quả dịch thành body cho POST /api/vocab. */
function buildVocabPayload(result: TranslateResult, tags: string[]) {
  const payload = result.payload as Record<string, unknown>;
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

chrome.runtime.onMessage.addListener((request: ExtensionRequest, sender, sendResponse) => {
  handle(request, sender.tab?.id)
    .then((data) => sendResponse({ ok: true, data } satisfies ExtensionResponse<unknown>))
    .catch((error) => sendResponse({ ok: false, error: toApiError(error) } satisfies ExtensionResponse<never>));
  return true;   // giữ kênh mở cho phản hồi bất đồng bộ
});

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {
  /* Chrome cũ không hỗ trợ — bỏ qua, người dùng vẫn mở panel từ bubble được */
});
```

- [ ] **Step 6: Chạy toàn bộ test và typecheck**

Run: `cd extension && npm test && npm run build`
Expected: test PASS, build thành công.

- [ ] **Step 7: Commit**

```bash
git add extension/src/background
git commit -m "feat: service worker với API client, cache health và định tuyến message"
```

---

### Task 9: Content script — trích selection và bubble trong Shadow DOM

Bubble viết bằng DOM thuần, không dùng React: nó chỉ có vài phần tử, và tránh nhét React vào mọi trang web người dùng ghé thăm.

**Files:**
- Create: `extension/src/content/{selection.ts,bubble.ts,bubble.css.ts,index.ts}`
- Test: `extension/src/content/{selection.test.ts,bubble.test.ts}`

**Interfaces:**
- Consumes: `sendToBackground` (Task 7), `shortMeaning` (Task 7), `loadSettings` (Task 7)
- Produces: `validateSelection(text: string): SelectionCheck`; `extractContextSentence(containerText: string, selectedText: string): string | null`; `showLoadingBubble(rect)`, `showResultBubble(rect, text, handlers)`, `showErrorBubble(rect, message, retryable, handlers)`, `hideBubble()`; `interface BubbleHandlers { onSpeak(): void; onSave(): void; onExpand(): void; onRetry(): void }`

- [ ] **Step 1: Viết test thất bại `src/content/selection.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { validateSelection, extractContextSentence, MAX_SELECTION_LENGTH } from './selection';

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

describe('extractContextSentence', () => {
  const paragraph =
    'The sun is hot. We need renewable energy now. It is urgent.';

  it('lấy đúng câu chứa từ được chọn', () => {
    expect(extractContextSentence(paragraph, 'renewable'))
      .toBe('We need renewable energy now.');
  });

  it('lấy câu đầu tiên khi từ nằm ở câu đầu', () => {
    expect(extractContextSentence(paragraph, 'sun')).toBe('The sun is hot.');
  });

  it('gộp cả hai câu khi selection trải qua ranh giới câu', () => {
    expect(extractContextSentence(paragraph, 'now. It is'))
      .toBe('We need renewable energy now. It is urgent.');
  });

  it('trả toàn bộ text khi không có dấu kết câu', () => {
    expect(extractContextSentence('renewable energy sources', 'energy'))
      .toBe('renewable energy sources');
  });

  it('xử lý được dấu chấm hỏi và chấm than', () => {
    expect(extractContextSentence('Is it hot? Yes it is!', 'Yes')).toBe('Yes it is!');
  });

  it('xử lý được câu tiếng Việt có dấu', () => {
    const text = 'Trời rất nóng. Chúng ta cần năng lượng tái tạo. Việc này gấp.';
    expect(extractContextSentence(text, 'tái tạo'))
      .toBe('Chúng ta cần năng lượng tái tạo.');
  });

  it('trả null khi không tìm thấy selection trong container', () => {
    expect(extractContextSentence(paragraph, 'không tồn tại')).toBeNull();
  });

  it('cắt bớt khi câu ngữ cảnh quá dài', () => {
    const long = 'x'.repeat(500) + ' target ' + 'y'.repeat(500);
    const context = extractContextSentence(long, 'target');
    expect(context!.length).toBeLessThanOrEqual(400);
    expect(context).toContain('target');
  });
});
```

- [ ] **Step 2: Viết test thất bại `src/content/bubble.test.ts`**

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  showLoadingBubble, showResultBubble, showErrorBubble, hideBubble, BUBBLE_HOST_ID,
} from './bubble';

const rect = { left: 100, top: 200, bottom: 220, width: 80, height: 20 } as DOMRect;

function shadow(): ShadowRoot {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (!host?.shadowRoot) throw new Error('Chưa có bubble trong DOM');
  return host.shadowRoot;
}

function handlers() {
  return { onSpeak: vi.fn(), onSave: vi.fn(), onExpand: vi.fn(), onRetry: vi.fn() };
}

describe('bubble', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    hideBubble();
  });

  it('bubble loading hiện trạng thái đang tải', () => {
    showLoadingBubble(rect);

    expect(shadow().textContent).toContain('Đang dịch');
  });

  it('bubble kết quả hiện nghĩa và 3 nút', () => {
    showResultBubble(rect, 'tái tạo', handlers());

    const root = shadow();
    expect(root.textContent).toContain('tái tạo');
    expect(root.querySelector('[data-action="speak"]')).not.toBeNull();
    expect(root.querySelector('[data-action="save"]')).not.toBeNull();
    expect(root.querySelector('[data-action="expand"]')).not.toBeNull();
  });

  it('bấm nút gọi đúng handler', () => {
    const h = handlers();
    showResultBubble(rect, 'tái tạo', h);

    (shadow().querySelector('[data-action="save"]') as HTMLElement).click();
    (shadow().querySelector('[data-action="expand"]') as HTMLElement).click();

    expect(h.onSave).toHaveBeenCalledOnce();
    expect(h.onExpand).toHaveBeenCalledOnce();
    expect(h.onSpeak).not.toHaveBeenCalled();
  });

  it('chỉ tồn tại một bubble dù gọi nhiều lần', () => {
    showLoadingBubble(rect);
    showResultBubble(rect, 'tái tạo', handlers());
    showResultBubble(rect, 'khác', handlers());

    expect(document.querySelectorAll(`#${BUBBLE_HOST_ID}`)).toHaveLength(1);
    expect(shadow().textContent).toContain('khác');
  });

  it('bubble lỗi hiện thông báo và nút thử lại khi lỗi có thể retry', () => {
    const h = handlers();
    showErrorBubble(rect, 'Backend chưa chạy', true, h);

    expect(shadow().textContent).toContain('Backend chưa chạy');
    (shadow().querySelector('[data-action="retry"]') as HTMLElement).click();
    expect(h.onRetry).toHaveBeenCalledOnce();
  });

  it('bubble lỗi không có nút thử lại khi lỗi không thể retry', () => {
    showErrorBubble(rect, 'Đã hết quota Gemini', false, handlers());

    expect(shadow().querySelector('[data-action="retry"]')).toBeNull();
  });

  it('hideBubble gỡ hẳn host khỏi DOM', () => {
    showResultBubble(rect, 'tái tạo', handlers());
    hideBubble();

    expect(document.getElementById(BUBBLE_HOST_ID)).toBeNull();
  });

  it('nội dung nằm trong shadow root, không lọt ra document', () => {
    showResultBubble(rect, 'tái tạo', handlers());

    expect(document.body.textContent).not.toContain('tái tạo');
  });
});
```

- [ ] **Step 3: Chạy test để xác nhận thất bại**

Run: `cd extension && npm test -- content`
Expected: FAIL — chưa có `selection.ts`, `bubble.ts`.

- [ ] **Step 4: Viết `src/content/selection.ts`**

```ts
export const MAX_SELECTION_LENGTH = 1500;
const MAX_CONTEXT_LENGTH = 400;

export type SelectionCheck =
  | { ok: true; text: string }
  | { ok: false; reason: 'EMPTY' | 'TOO_LONG' };

export function validateSelection(raw: string): SelectionCheck {
  const text = raw.trim();
  if (text.length === 0) return { ok: false, reason: 'EMPTY' };
  if (text.length > MAX_SELECTION_LENGTH) return { ok: false, reason: 'TOO_LONG' };
  return { ok: true, text };
}

/**
 * Tìm câu chứa đoạn được chọn. Mở rộng sang trái tới dấu kết câu gần nhất và
 * sang phải tới dấu kết câu tiếp theo. Trả null nếu không tìm thấy selection.
 */
export function extractContextSentence(
  containerText: string,
  selectedText: string,
): string | null {
  const start = containerText.indexOf(selectedText);
  if (start < 0) return null;
  const end = start + selectedText.length;

  let left = 0;
  for (let i = start - 1; i >= 0; i--) {
    if ('.!?'.includes(containerText[i])) {
      left = i + 1;
      break;
    }
  }

  let right = containerText.length;
  for (let i = end; i < containerText.length; i++) {
    if ('.!?'.includes(containerText[i])) {
      right = i + 1;
      break;
    }
  }

  const sentence = containerText.slice(left, right).trim();
  return sentence.length > MAX_CONTEXT_LENGTH
    ? trimAround(sentence, selectedText)
    : sentence;
}

/** Giữ đoạn được chọn ở giữa khi phải cắt bớt câu quá dài. */
function trimAround(sentence: string, selectedText: string): string {
  const index = sentence.indexOf(selectedText);
  const budget = MAX_CONTEXT_LENGTH - selectedText.length;
  const half = Math.max(0, Math.floor(budget / 2));
  const from = Math.max(0, index - half);
  return sentence.slice(from, from + MAX_CONTEXT_LENGTH);
}
```

- [ ] **Step 5: Viết `src/content/bubble.css.ts`**

```ts
export const BUBBLE_CSS = `
:host { all: initial; }
.bubble {
  position: fixed;
  z-index: 2147483647;
  max-width: 320px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #1f2430;
  color: #f2f4f8;
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.bubble.error { background: #4a2020; }
.text { flex: 1; word-break: break-word; }
button {
  all: unset;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 13px;
  line-height: 1.4;
}
button:hover { background: rgba(255, 255, 255, 0.14); }
button:focus-visible { outline: 2px solid #7aa7ff; }
`;
```

- [ ] **Step 6: Viết `src/content/bubble.ts`**

```ts
import { BUBBLE_CSS } from './bubble.css';

export const BUBBLE_HOST_ID = 'ielts-translator-bubble-host';

export interface BubbleHandlers {
  onSpeak(): void;
  onSave(): void;
  onExpand(): void;
  onRetry(): void;
}

function mountShadow(): ShadowRoot {
  hideBubble();
  const host = document.createElement('div');
  host.id = BUBBLE_HOST_ID;
  document.body.appendChild(host);

  const root = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = BUBBLE_CSS;
  root.appendChild(style);
  return root;
}

function positionedContainer(rect: DOMRect, extraClass = ''): HTMLDivElement {
  const container = document.createElement('div');
  container.className = `bubble ${extraClass}`.trim();
  container.style.left = `${Math.max(8, rect.left)}px`;
  container.style.top = `${rect.bottom + 8}px`;
  return container;
}

function button(label: string, action: string, title: string, onClick: () => void): HTMLButtonElement {
  const el = document.createElement('button');
  el.textContent = label;
  el.dataset.action = action;
  el.title = title;
  el.addEventListener('click', (event) => {
    event.stopPropagation();
    onClick();
  });
  return el;
}

export function showLoadingBubble(rect: DOMRect): void {
  const root = mountShadow();
  const container = positionedContainer(rect);
  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = 'Đang dịch…';
  container.appendChild(text);
  root.appendChild(container);
}

export function showResultBubble(rect: DOMRect, meaning: string, handlers: BubbleHandlers): void {
  const root = mountShadow();
  const container = positionedContainer(rect);

  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = meaning;
  container.appendChild(text);

  container.appendChild(button('🔊', 'speak', 'Phát âm', handlers.onSpeak));
  container.appendChild(button('+', 'save', 'Lưu vào sổ từ', handlers.onSave));
  container.appendChild(button('⤢', 'expand', 'Mở side panel', handlers.onExpand));

  root.appendChild(container);
}

export function showErrorBubble(
  rect: DOMRect, message: string, retryable: boolean, handlers: BubbleHandlers,
): void {
  const root = mountShadow();
  const container = positionedContainer(rect, 'error');

  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = message;
  container.appendChild(text);

  if (retryable) {
    container.appendChild(button('Thử lại', 'retry', 'Gọi lại backend', handlers.onRetry));
  }
  root.appendChild(container);
}

export function hideBubble(): void {
  document.getElementById(BUBBLE_HOST_ID)?.remove();
}
```

- [ ] **Step 7: Chạy test để xác nhận pass**

Run: `cd extension && npm test -- content`
Expected: PASS, 18 test.

- [ ] **Step 8: Viết `src/content/index.ts`**

```ts
import { validateSelection, extractContextSentence } from './selection';
import {
  showLoadingBubble, showResultBubble, showErrorBubble, hideBubble, BUBBLE_HOST_ID,
} from './bubble';
import { sendToBackground } from '../shared/messages';
import { shortMeaning } from '../shared/summary';
import { loadSettings } from '../shared/settings';
import type { TranslateResult } from '../shared/types';

const DEBOUNCE_MS = 250;

let debounceTimer: number | undefined;
let currentResult: TranslateResult | null = null;

function selectionRect(): DOMRect | null {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  return selection.getRangeAt(0).getBoundingClientRect();
}

function containerTextOf(selection: Selection): string {
  const node = selection.anchorNode;
  const element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element | null);
  return element?.textContent ?? '';
}

function speak(text: string, voiceName: string | null): void {
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = speechSynthesis.getVoices()
    .find((v) => (voiceName ? v.name === voiceName : v.lang.startsWith('en')));
  if (voice) utterance.voice = voice;
  speechSynthesis.speak(utterance);
}

async function translateCurrentSelection(): Promise<void> {
  const selection = window.getSelection();
  const rect = selectionRect();
  if (!selection || !rect) return;

  const check = validateSelection(selection.toString());
  if (!check.ok) {
    if (check.reason === 'TOO_LONG') {
      showErrorBubble(rect, 'Đoạn bôi đen quá dài, hãy chọn ít chữ hơn.', false, noopHandlers());
    }
    return;
  }

  const settings = await loadSettings();
  showLoadingBubble(rect);

  const response = await sendToBackground({
    type: 'TRANSLATE_SELECTION',
    text: check.text,
    contextSentence: extractContextSentence(containerTextOf(selection), check.text),
    sourceUrl: location.href,
    pageTitle: document.title,
  });

  if (!response.ok) {
    showErrorBubble(rect, response.error.message, response.error.retryable, {
      ...noopHandlers(),
      onRetry: () => void translateCurrentSelection(),
    });
    return;
  }

  currentResult = response.data;
  showResultBubble(rect, shortMeaning(response.data), {
    onSpeak: () => speak(spokenTextOf(response.data), settings.voiceName),
    onSave: () => void saveCurrent(rect),
    onExpand: () => void sendToBackground({ type: 'OPEN_PANEL_WITH_RESULT', result: response.data }),
    onRetry: () => void translateCurrentSelection(),
  });
}

/** Đọc phần tiếng Anh: text gốc nếu EN→VI, bản dịch nếu VI→EN. */
function spokenTextOf(result: TranslateResult): string {
  return result.direction === 'EN_VI' ? result.sourceText : shortMeaning(result);
}

async function saveCurrent(rect: DOMRect): Promise<void> {
  if (!currentResult) return;
  const response = await sendToBackground({ type: 'SAVE_WORD', result: currentResult, tags: [] });
  if (!response.ok) {
    showErrorBubble(rect, response.error.message, response.error.retryable, noopHandlers());
    return;
  }
  showResultBubble(
    rect,
    response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ',
    noopHandlers(),
  );
}

function noopHandlers() {
  return { onSpeak: () => {}, onSave: () => {}, onExpand: () => {}, onRetry: () => {} };
}

document.addEventListener('mouseup', () => {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(async () => {
    const settings = await loadSettings();
    if (settings.triggerMode !== 'auto') return;
    if ((window.getSelection()?.toString() ?? '').trim().length === 0) {
      hideBubble();
      return;
    }
    void translateCurrentSelection();
  }, DEBOUNCE_MS);
});

document.addEventListener('mousedown', (event) => {
  const host = document.getElementById(BUBBLE_HOST_ID);
  if (host && !event.composedPath().includes(host)) hideBubble();
});

chrome.runtime.onMessage.addListener((message: { type?: string }) => {
  if (message?.type === 'HOTKEY_TRANSLATE') void translateCurrentSelection();
});
```

- [ ] **Step 9: Nối phím tắt trong service worker**

Thêm vào cuối `extension/src/background/service-worker.ts`:

```ts
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== 'translate-selection') return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id !== undefined) {
    chrome.tabs.sendMessage(tab.id, { type: 'HOTKEY_TRANSLATE' });
  }
});
```

Thêm `"tabs"` vào mảng `permissions` trong `manifest.config.ts`.

- [ ] **Step 10: Chạy toàn bộ test và build**

Run: `cd extension && npm test && npm run build`
Expected: test PASS, build thành công.

- [ ] **Step 11: Commit**

```bash
git add extension/src/content extension/src/background/service-worker.ts extension/manifest.config.ts
git commit -m "feat: content script bắt selection và bubble Shadow DOM"
```

---

### Task 10: Side panel — tab Dịch chi tiết

**Files:**
- Create: `extension/src/sidepanel/{index.html,main.tsx,App.tsx,TranslateTab.tsx,PayloadViews.tsx,styles.css}`
- Test: `extension/src/sidepanel/TranslateTab.test.tsx`

**Interfaces:**
- Consumes: `sendToBackground`, types (Task 7)
- Produces: `<TranslateTab />` (tự lấy kết quả gần nhất qua `GET_LAST_RESULT`); `<App />` với 2 tab `Dịch` và `Sổ từ`

- [ ] **Step 1: Viết test thất bại `src/sidepanel/TranslateTab.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TranslateTab } from './TranslateTab';
import type { TranslateResult } from '../shared/types';

function mockLastResult(result: TranslateResult | null) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      if (request.type === 'GET_LAST_RESULT') return { ok: true, data: result };
      if (request.type === 'SAVE_WORD') return { ok: true, data: { id: 1, alreadyExists: false } };
      return { ok: true, data: null };
    },
  );
}

const enViWord: TranslateResult = {
  direction: 'EN_VI', mode: 'WORD', cached: false, sourceText: 'renewable',
  payload: {
    term: 'renewable', lemma: 'renewable', pos: 'adj', ipa: '/rɪˈnjuːəbl/',
    meaning_vi: 'tái tạo', definition_en: 'able to be renewed', cefr: 'B2',
    band_level: '6.5', register: 'academic',
    collocations: ['renewable energy', 'renewable resources'],
    examples: [{ en: 'We rely on renewable energy.', vi: 'Chúng ta dựa vào năng lượng tái tạo.' }],
    synonyms: [{ term: 'sustainable', band: '7.0' }],
  },
};

describe('TranslateTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hiện trạng thái rỗng khi chưa dịch gì', async () => {
    mockLastResult(null);
    render(<TranslateTab />);

    expect(await screen.findByText(/Bôi đen một đoạn text/i)).toBeInTheDocument();
  });

  it('hiện đầy đủ thông tin cho EN→VI tra từ', async () => {
    mockLastResult(enViWord);
    render(<TranslateTab />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('/rɪˈnjuːəbl/')).toBeInTheDocument();
    expect(screen.getByText('tái tạo')).toBeInTheDocument();
    expect(screen.getByText('able to be renewed')).toBeInTheDocument();
    expect(screen.getByText('renewable energy')).toBeInTheDocument();
    expect(screen.getByText('We rely on renewable energy.')).toBeInTheDocument();
    expect(screen.getByText('sustainable')).toBeInTheDocument();
  });

  it('hiện band kèm chú thích đây là ước lượng', async () => {
    mockLastResult(enViWord);
    render(<TranslateTab />);

    const band = await screen.findByTitle(/ước lượng/i);
    expect(band).toHaveTextContent('6.5');
  });

  it('hiện bản dịch và từ khoá cho EN→VI tra câu', async () => {
    mockLastResult({
      direction: 'EN_VI', mode: 'SENTENCE', cached: false, sourceText: 'a sentence',
      payload: {
        translation_vi: 'Chính phủ nên đầu tư nhiều hơn.',
        key_vocab: [{ term: 'allocate', meaning_vi: 'phân bổ', band_level: '7.0' }],
        structure_note: 'Câu dùng mệnh đề quan hệ.',
      },
    });
    render(<TranslateTab />);

    expect(await screen.findByText('Chính phủ nên đầu tư nhiều hơn.')).toBeInTheDocument();
    expect(screen.getByText('allocate')).toBeInTheDocument();
    expect(screen.getByText('Câu dùng mệnh đề quan hệ.')).toBeInTheDocument();
  });

  it('hiện lựa chọn thay thế cho VI→EN tra từ', async () => {
    mockLastResult({
      direction: 'VI_EN', mode: 'WORD', cached: false, sourceText: 'tái tạo',
      payload: {
        best_en: 'renewable',
        alternatives: [{ term: 'sustainable', band: '7.0', register: 'academic',
                        when_to_use: 'Khi nói về phát triển bền vững.' }],
        collocations: ['renewable energy'],
        examples: ['We need renewable energy.'],
      },
    });
    render(<TranslateTab />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('sustainable')).toBeInTheDocument();
    expect(screen.getByText('Khi nói về phát triển bền vững.')).toBeInTheDocument();
  });

  it('hiện bản band 6.5 kèm giải thích và mục nên tránh cho VI→EN tra câu', async () => {
    mockLastResult({
      direction: 'VI_EN', mode: 'SENTENCE', cached: false, sourceText: 'câu tiếng Việt',
      payload: {
        band65_version: 'The government should allocate more funding.',
        why_notes: ['Dùng allocate thay cho give để trang trọng hơn.'],
        key_phrases: ['allocate funding'],
        avoid: [{ phrase: 'give more money', reason: 'Quá thông tục cho văn viết học thuật.' }],
      },
    });
    render(<TranslateTab />);

    expect(await screen.findByText('The government should allocate more funding.')).toBeInTheDocument();
    expect(screen.getByText('Dùng allocate thay cho give để trang trọng hơn.')).toBeInTheDocument();
    expect(screen.getByText('give more money')).toBeInTheDocument();
    expect(screen.getByText('Quá thông tục cho văn viết học thuật.')).toBeInTheDocument();
  });

  it('bấm Lưu từ gửi SAVE_WORD và báo đã lưu', async () => {
    mockLastResult(enViWord);
    render(<TranslateTab />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText(/Đã lưu/i)).toBeInTheDocument());
    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SAVE_WORD' }),
    );
  });

  it('báo Đã có trong sổ khi backend trả alreadyExists', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
      async (request: { type: string }) => {
        if (request.type === 'GET_LAST_RESULT') return { ok: true, data: enViWord };
        return { ok: true, data: { id: 1, alreadyExists: true } };
      },
    );
    render(<TranslateTab />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText(/Đã có trong sổ/i)).toBeInTheDocument());
  });

  it('hiện thông báo lỗi khi lưu thất bại', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
      async (request: { type: string }) => {
        if (request.type === 'GET_LAST_RESULT') return { ok: true, data: enViWord };
        return { ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true } };
      },
    );
    render(<TranslateTab />);

    await userEvent.click(await screen.findByRole('button', { name: /Lưu từ/i }));

    await waitFor(() => expect(screen.getByText('Backend chưa chạy')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `cd extension && npm test -- TranslateTab`
Expected: FAIL — chưa có `TranslateTab.tsx`.

- [ ] **Step 3: Viết `src/sidepanel/PayloadViews.tsx`**

```tsx
import type { ReactNode } from 'react';
import type {
  EnViSentencePayload, EnViWordPayload, TranslateResult,
  ViEnSentencePayload, ViEnWordPayload,
} from '../shared/types';

const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

function Band({ value }: { value: string }) {
  return <span className="band" title={BAND_HINT}>{value}</span>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function EnViWordView({ p }: { p: EnViWordPayload }) {
  return (
    <>
      <header className="entry-head">
        <h2>{p.term}</h2>
        <div className="meta">
          <span className="ipa">{p.ipa}</span>
          <span>{p.pos}</span>
          <span>{p.cefr}</span>
          <Band value={p.band_level} />
          <span>{p.register}</span>
        </div>
        <p className="meaning">{p.meaning_vi}</p>
        <p className="definition">{p.definition_en}</p>
      </header>

      <Section title="Collocations">
        <ul>{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul>
          {p.examples.map((e) => (
            <li key={e.en}><span className="en">{e.en}</span><span className="vi">{e.vi}</span></li>
          ))}
        </ul>
      </Section>

      <Section title="Từ đồng nghĩa">
        <ul>
          {p.synonyms.map((s) => (
            <li key={s.term}>{s.term} <Band value={s.band} /></li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function EnViSentenceView({ p }: { p: EnViSentencePayload }) {
  return (
    <>
      <header className="entry-head">
        <p className="meaning">{p.translation_vi}</p>
      </header>

      <Section title="Từ đáng học">
        <ul>
          {p.key_vocab.map((v) => (
            <li key={v.term}>
              <strong>{v.term}</strong> — {v.meaning_vi} <Band value={v.band_level} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Ghi chú cấu trúc">
        <p>{p.structure_note}</p>
      </Section>
    </>
  );
}

export function ViEnWordView({ p }: { p: ViEnWordPayload }) {
  return (
    <>
      <header className="entry-head">
        <h2>{p.best_en}</h2>
      </header>

      <Section title="Lựa chọn khác">
        <ul>
          {p.alternatives.map((a) => (
            <li key={a.term}>
              <strong>{a.term}</strong> <Band value={a.band} /> <span>{a.register}</span>
              <span className="vi">{a.when_to_use}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Collocations">
        <ul>{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul>{p.examples.map((e) => <li key={e}>{e}</li>)}</ul>
      </Section>
    </>
  );
}

export function ViEnSentenceView({ p }: { p: ViEnSentencePayload }) {
  return (
    <>
      <header className="entry-head">
        <p className="meaning">{p.band65_version}</p>
      </header>

      <Section title="Vì sao viết như vậy">
        <ul>{p.why_notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </Section>

      <Section title="Cụm đáng học">
        <ul>{p.key_phrases.map((k) => <li key={k}>{k}</li>)}</ul>
      </Section>

      <Section title="Nên tránh">
        <ul>
          {p.avoid.map((a) => (
            <li key={a.phrase}>
              <strong>{a.phrase}</strong><span className="vi">{a.reason}</span>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function PayloadView({ result }: { result: TranslateResult }) {
  if (result.direction === 'EN_VI') {
    return result.mode === 'WORD'
      ? <EnViWordView p={result.payload as EnViWordPayload} />
      : <EnViSentenceView p={result.payload as EnViSentencePayload} />;
  }
  return result.mode === 'WORD'
    ? <ViEnWordView p={result.payload as ViEnWordPayload} />
    : <ViEnSentenceView p={result.payload as ViEnSentencePayload} />;
}
```

- [ ] **Step 4: Viết `src/sidepanel/TranslateTab.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { PayloadView } from './PayloadViews';

export function TranslateTab() {
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const response = await sendToBackground({ type: 'GET_LAST_RESULT' });
      if (response.ok) setResult(response.data);
      setLoaded(true);
    })();
  }, []);

  async function save() {
    if (!result) return;
    setStatus(null);
    const response = await sendToBackground({ type: 'SAVE_WORD', result, tags: [] });
    setStatus(response.ok
      ? (response.data.alreadyExists ? 'Đã có trong sổ' : 'Đã lưu vào sổ từ')
      : response.error.message);
  }

  if (!loaded) return <p className="empty">Đang tải…</p>;

  if (!result) {
    return <p className="empty">Bôi đen một đoạn text trên trang web để bắt đầu.</p>;
  }

  return (
    <div className="translate-tab">
      <PayloadView result={result} />
      <div className="actions">
        <button type="button" onClick={() => void save()}>Lưu từ</button>
        {result.cached && <span className="cached-hint">từ cache</span>}
      </div>
      {status && <p className="status">{status}</p>}
    </div>
  );
}
```

- [ ] **Step 5: Viết `src/sidepanel/App.tsx`, `main.tsx`, `index.html`, `styles.css`**

```tsx
// App.tsx — Task 11 sẽ thêm thanh tab và tab Sổ từ
import { TranslateTab } from './TranslateTab';

export function App() {
  return (
    <div className="app">
      <main className="content">
        <TranslateTab />
      </main>
    </div>
  );
}
```

```tsx
// main.tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
);
```

```html
<!-- index.html -->
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IELTS Translator</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./main.tsx"></script>
  </body>
</html>
```

```css
/* styles.css */
:root { color-scheme: light dark; }
body { margin: 0; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.app { display: flex; flex-direction: column; height: 100vh; }
.tabs { display: flex; border-bottom: 1px solid rgba(128,128,128,.35); }
.tabs button { flex: 1; padding: 10px; border: 0; background: none; cursor: pointer; font: inherit; }
.tabs button.active { border-bottom: 2px solid #4c8dff; font-weight: 600; }
.content { flex: 1; overflow-y: auto; padding: 12px; }
.empty { color: #888; text-align: center; margin-top: 40px; }
.entry-head h2 { margin: 0 0 4px; font-size: 20px; }
.meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: #888; }
.meaning { font-size: 16px; margin: 8px 0 4px; }
.definition { color: #888; margin: 0 0 8px; }
.band { padding: 0 5px; border-radius: 4px; background: rgba(76,141,255,.18); cursor: help; }
.section { margin-top: 14px; }
.section h3 { font-size: 12px; text-transform: uppercase; color: #888; margin: 0 0 6px; }
.section ul { margin: 0; padding-left: 18px; }
.section li { margin-bottom: 6px; }
.en, .vi { display: block; }
.vi { color: #888; }
.actions { display: flex; align-items: center; gap: 10px; margin-top: 18px; }
.actions button { padding: 7px 14px; border-radius: 6px; border: 0; background: #4c8dff; color: #fff; cursor: pointer; font: inherit; }
.cached-hint, .status { font-size: 12px; color: #888; }
.vocab-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.vocab-toolbar input { flex: 1; padding: 6px 8px; border-radius: 6px; border: 1px solid rgba(128,128,128,.4); font: inherit; }
.vocab-list { list-style: none; margin: 0; padding: 0; }
.vocab-item { padding: 8px 0; border-bottom: 1px solid rgba(128,128,128,.2); display: flex; justify-content: space-between; gap: 8px; }
```

- [ ] **Step 6: Chạy test để xác nhận pass**

Run: `cd extension && npm test -- TranslateTab`
Expected: PASS, 9 test.

- [ ] **Step 7: Commit**

```bash
git add extension/src/sidepanel
git commit -m "feat: side panel tab Dịch với 4 dạng hiển thị payload"
```

---

### Task 11: Side panel — tab Sổ từ

**Files:**
- Create: `extension/src/sidepanel/VocabTab.tsx`
- Modify: `extension/src/sidepanel/App.tsx` (thêm thanh tab Dịch / Sổ từ)
- Test: `extension/src/sidepanel/VocabTab.test.tsx`

**Interfaces:**
- Consumes: `sendToBackground`, `VocabEntryDto`, `PageResponse` (Task 7), `<TranslateTab />` (Task 10)
- Produces: `<VocabTab />`; `<App />` với 2 tab

- [ ] **Step 1: Viết test thất bại `src/sidepanel/VocabTab.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { VocabTab } from './VocabTab';
import type { VocabEntryDto } from '../shared/types';

function entry(id: number, term: string, meaningVi: string): VocabEntryDto {
  return {
    id, term, lemma: term, lang: 'en', pos: 'adj', ipa: '/test/', meaningVi,
    definitionEn: null, cefr: 'B2', bandLevel: '6.5', tags: ['environment'],
    sourceUrl: 'https://example.com', sourceSentence: null,
    collocations: [], examples: [], createdAt: '2026-08-03T10:00:00Z',
  };
}

function mockSearch(entries: VocabEntryDto[]) {
  (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockImplementation(
    async (request: { type: string }) => {
      if (request.type === 'SEARCH_VOCAB') {
        return { ok: true, data: {
          content: entries, totalElements: entries.length, totalPages: 1, number: 0 } };
      }
      return { ok: true, data: null };
    },
  );
}

describe('VocabTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('tải và hiện danh sách từ khi mở tab', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo'), entry(2, 'mitigate', 'giảm nhẹ')]);
    render(<VocabTab />);

    expect(await screen.findByText('renewable')).toBeInTheDocument();
    expect(screen.getByText('mitigate')).toBeInTheDocument();
  });

  it('hiện trạng thái rỗng khi sổ chưa có từ nào', async () => {
    mockSearch([]);
    render(<VocabTab />);

    expect(await screen.findByText(/Sổ từ đang trống/i)).toBeInTheDocument();
  });

  it('gõ vào ô tìm kiếm sẽ gửi SEARCH_VOCAB kèm từ khoá', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.type(screen.getByPlaceholderText(/Tìm từ/i), 'renew');

    await waitFor(() => expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'SEARCH_VOCAB', query: 'renew' }),
    ));
  });

  it('bấm xoá sẽ gửi DELETE_VOCAB rồi tải lại danh sách', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);
    await screen.findByText('renewable');

    await userEvent.click(screen.getByRole('button', { name: /Xoá renewable/i }));

    await waitFor(() => expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(
      { type: 'DELETE_VOCAB', id: 1 },
    ));
  });

  it('hiện lỗi khi backend chết', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<VocabTab />);

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('có nút Thử lại khi lỗi có thể retry', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<VocabTab />);

    expect(await screen.findByRole('button', { name: /Thử lại/i })).toBeInTheDocument();
  });

  it('hiện tổng số từ trong sổ', async () => {
    mockSearch([entry(1, 'renewable', 'tái tạo')]);
    render(<VocabTab />);

    expect(await screen.findByText(/1 từ/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `cd extension && npm test -- VocabTab`
Expected: FAIL — bản tạm không có ô tìm kiếm.

- [ ] **Step 3: Viết `src/sidepanel/VocabTab.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import { loadSettings } from '../shared/settings';
import type { ApiError, VocabEntryDto } from '../shared/types';

const SEARCH_DEBOUNCE_MS = 300;

export function VocabTab() {
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState<VocabEntryDto[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    const response = await sendToBackground({
      type: 'SEARCH_VOCAB', query: q || null, tag: null, page: 0,
    });
    if (response.ok) {
      setEntries(response.data.content);
      setTotal(response.data.totalElements);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query, load]);

  async function remove(id: number) {
    const response = await sendToBackground({ type: 'DELETE_VOCAB', id });
    if (!response.ok) {
      setError(response.error);
      return;
    }
    await load(query);
  }

  async function openExport() {
    const { backendUrl } = await loadSettings();
    window.open(`${backendUrl}/api/vocab/export.csv`, '_blank');
  }

  if (error) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && (
          <button type="button" onClick={() => void load(query)}>Thử lại</button>
        )}
      </div>
    );
  }

  return (
    <div className="vocab-tab">
      <div className="vocab-toolbar">
        <input
          type="search"
          placeholder="Tìm từ hoặc nghĩa…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="button" onClick={() => void openExport()}>CSV</button>
      </div>

      {loading && <p className="status">Đang tải…</p>}

      {!loading && entries.length === 0 && (
        <p className="empty">Sổ từ đang trống. Lưu từ đầu tiên từ bubble dịch.</p>
      )}

      {entries.length > 0 && (
        <>
          <p className="status">{total} từ</p>
          <ul className="vocab-list">
            {entries.map((e) => (
              <li key={e.id} className="vocab-item">
                <div>
                  <strong>{e.term}</strong>
                  {e.pos && <span className="meta"> · {e.pos}</span>}
                  {e.bandLevel && (
                    <span className="band" title="Band do AI ước lượng, chỉ mang tính tham khảo">
                      {e.bandLevel}
                    </span>
                  )}
                  <span className="vi">{e.meaningVi}</span>
                </div>
                <button type="button" aria-label={`Xoá ${e.term}`} onClick={() => void remove(e.id)}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `cd extension && npm test -- VocabTab`
Expected: PASS, 7 test.

- [ ] **Step 5: Thêm thanh tab vào `src/sidepanel/App.tsx`**

Thay toàn bộ nội dung `App.tsx` (bản Task 10 chỉ có một view) bằng:

```tsx
import { useState } from 'react';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';

type Tab = 'translate' | 'vocab';

export function App() {
  const [tab, setTab] = useState<Tab>('translate');

  return (
    <div className="app">
      <nav className="tabs">
        <button type="button" className={tab === 'translate' ? 'active' : ''}
                onClick={() => setTab('translate')}>Dịch</button>
        <button type="button" className={tab === 'vocab' ? 'active' : ''}
                onClick={() => setTab('vocab')}>Sổ từ</button>
      </nav>
      <main className="content">
        {tab === 'translate' ? <TranslateTab /> : <VocabTab />}
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Chạy toàn bộ test extension**

Run: `cd extension && npm test && npm run build`
Expected: PASS toàn bộ, build thành công.

- [ ] **Step 7: Commit**

```bash
git add extension/src/sidepanel
git commit -m "feat: side panel tab Sổ từ với tìm kiếm, xoá và export CSV"
```

---

### Task 12: Options page, README, kiểm chứng đầu-cuối

Task cuối: nối mọi thứ lại và chạy thật trên Chrome với Gemini thật.

**Files:**
- Create: `extension/src/options/{index.html,main.tsx,Options.tsx}`
- Create: `README.md`
- Test: `extension/src/options/Options.test.tsx`

**Interfaces:**
- Consumes: `Settings`, `loadSettings`, `saveSettings` (Task 7), `sendToBackground` (Task 7)
- Produces: `<Options />`

- [ ] **Step 1: Viết test thất bại `src/options/Options.test.tsx`**

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Options } from './Options';
import { DEFAULT_SETTINGS, loadSettings } from '../shared/settings';

describe('Options', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await chrome.storage.local.clear();
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, data: { status: 'UP', dbConnected: true, geminiConfigured: true },
    });
  });

  it('hiện giá trị mặc định khi chưa lưu gì', async () => {
    render(<Options />);

    expect(await screen.findByLabelText(/Địa chỉ backend/i))
      .toHaveValue(DEFAULT_SETTINGS.backendUrl);
  });

  it('lưu backend URL mới vào storage', async () => {
    render(<Options />);
    const input = await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.clear(input);
    await userEvent.type(input, 'http://127.0.0.1:9090');
    await userEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(async () =>
      expect((await loadSettings()).backendUrl).toBe('http://127.0.0.1:9090'));
  });

  it('đổi được chế độ kích hoạt sang phím tắt', async () => {
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByLabelText(/Chỉ khi bấm Alt\+T/i));
    await userEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(async () => expect((await loadSettings()).triggerMode).toBe('hotkey'));
  });

  it('nút kiểm tra kết nối báo thành công', async () => {
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText(/Backend đang chạy/i)).toBeInTheDocument();
  });

  it('nút kiểm tra kết nối báo lỗi khi backend chết', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('cảnh báo khi backend chạy nhưng chưa cấu hình Gemini API key', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, data: { status: 'UP', dbConnected: true, geminiConfigured: false },
    });
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText(/chưa cấu hình GEMINI_API_KEY/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Chạy test để xác nhận thất bại**

Run: `cd extension && npm test -- Options`
Expected: FAIL — chưa có `Options.tsx`.

- [ ] **Step 3: Viết `src/options/Options.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { DEFAULT_SETTINGS, loadSettings, saveSettings, type Settings } from '../shared/settings';
import { sendToBackground } from '../shared/messages';

export function Options() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      setSettings(await loadSettings());
      setLoaded(true);
    })();
  }, []);

  async function save() {
    setSettings(await saveSettings(settings));
    setSaveStatus('Đã lưu cài đặt');
  }

  async function checkHealth() {
    setHealthStatus('Đang kiểm tra…');
    const response = await sendToBackground({ type: 'CHECK_HEALTH' });
    if (!response.ok) {
      setHealthStatus(response.error.message);
      return;
    }
    setHealthStatus(response.data.geminiConfigured
      ? 'Backend đang chạy, Gemini đã cấu hình.'
      : 'Backend đang chạy nhưng chưa cấu hình GEMINI_API_KEY trong file .env.');
  }

  if (!loaded) return <p>Đang tải…</p>;

  return (
    <main className="options">
      <h1>IELTS Translator — Cài đặt</h1>

      <label htmlFor="backendUrl">Địa chỉ backend</label>
      <input
        id="backendUrl"
        type="url"
        value={settings.backendUrl}
        onChange={(e) => setSettings({ ...settings, backendUrl: e.target.value })}
      />

      <fieldset>
        <legend>Chế độ kích hoạt</legend>
        <label>
          <input
            type="radio"
            name="triggerMode"
            checked={settings.triggerMode === 'auto'}
            onChange={() => setSettings({ ...settings, triggerMode: 'auto' })}
          />
          Tự hiện bubble khi bôi đen
        </label>
        <label>
          <input
            type="radio"
            name="triggerMode"
            checked={settings.triggerMode === 'hotkey'}
            onChange={() => setSettings({ ...settings, triggerMode: 'hotkey' })}
          />
          Chỉ khi bấm Alt+T
        </label>
      </fieldset>

      <label htmlFor="voiceName">Giọng đọc (để trống dùng giọng en mặc định)</label>
      <input
        id="voiceName"
        type="text"
        value={settings.voiceName ?? ''}
        onChange={(e) => setSettings({ ...settings, voiceName: e.target.value || null })}
      />

      <div className="options-actions">
        <button type="button" onClick={() => void save()}>Lưu</button>
        <button type="button" onClick={() => void checkHealth()}>Kiểm tra kết nối</button>
      </div>

      {saveStatus && <p className="status">{saveStatus}</p>}
      {healthStatus && <p className="status">{healthStatus}</p>}
    </main>
  );
}
```

- [ ] **Step 4: Viết `src/options/main.tsx` và `index.html`**

```tsx
// main.tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Options } from './Options';
import '../sidepanel/styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode><Options /></StrictMode>,
);
```

```html
<!-- index.html -->
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>IELTS Translator — Cài đặt</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./main.tsx"></script>
  </body>
</html>
```

Thêm vào cuối `src/sidepanel/styles.css`:

```css
.options { max-width: 560px; margin: 32px auto; padding: 0 20px; }
.options label { display: block; margin-top: 14px; font-weight: 500; }
.options input[type="url"], .options input[type="text"] {
  width: 100%; padding: 7px 9px; margin-top: 4px;
  border: 1px solid rgba(128,128,128,.4); border-radius: 6px; font: inherit;
}
.options fieldset { margin-top: 18px; border: 1px solid rgba(128,128,128,.3); border-radius: 6px; }
.options fieldset label { font-weight: 400; }
.options-actions { display: flex; gap: 10px; margin-top: 22px; }
.options-actions button {
  padding: 8px 16px; border: 0; border-radius: 6px;
  background: #4c8dff; color: #fff; cursor: pointer; font: inherit;
}
```

- [ ] **Step 5: Chạy toàn bộ test extension để xác nhận pass**

Run: `cd extension && npm test && npm run build`
Expected: PASS toàn bộ, build thành công.

- [ ] **Step 6: Viết `README.md`**

````markdown
# IELTS Translator

Chrome extension dịch hai chiều Việt-Anh chuẩn IELTS band 6.5+, kèm sổ từ vựng.
Chạy hoàn toàn trên máy cá nhân: extension gọi Spring Boot ở `127.0.0.1:8080`,
backend gọi Gemini.

## Chạy lần đầu

1. Lấy Gemini API key tại https://aistudio.google.com/apikey

2. Tạo file `.env` ở thư mục gốc:
   ```bash
   cp .env.example .env
   ```
   Điền `GEMINI_API_KEY`. Để trống `EXTENSION_ID` ở bước này.

3. Build extension:
   ```bash
   cd extension && npm install && npm run build
   ```

4. Load vào Chrome: mở `chrome://extensions`, bật Developer mode,
   bấm "Load unpacked", chọn thư mục `extension/dist`.

5. Copy extension ID Chrome hiển thị, dán vào `EXTENSION_ID` trong `.env`.
   ID này cố định giữa các lần build nhờ field `key` trong manifest.

6. Khởi động backend:
   ```bash
   docker compose up -d --build
   ```

7. Mở trang Options của extension, bấm "Kiểm tra kết nối".
   Phải thấy "Backend đang chạy, Gemini đã cấu hình."

## Dùng hàng ngày

```bash
docker compose up -d      # bật backend
docker compose down       # tắt backend, dữ liệu từ vựng vẫn còn
```

Bôi đen text bất kỳ trên web để dịch. Bấm `+` để lưu vào sổ, `⤢` để mở side panel.

## Chạy test

```bash
cd backend && mvn test          # cần Docker cho Testcontainers
cd extension && npm test
```

## Chỉnh prompt

Prompt nằm ở `backend/src/main/resources/prompts/*.md`. Sửa xong nhớ tăng
`version:` ở đầu file — cache sẽ tự hết hiệu lực. Rồi `docker compose up -d --build`.
````

- [ ] **Step 7: Kiểm chứng đầu-cuối trên Chrome thật**

Chạy đủ 8 kịch bản sau với backend thật và Gemini thật. Ghi lại kịch bản nào hỏng.

```
1. Bôi đen một từ tiếng Anh trên trang báo bất kỳ
   → bubble hiện nghĩa tiếng Việt trong vài giây

2. Bấm 🔊 trên bubble
   → nghe được phát âm

3. Bấm ⤢
   → side panel mở, hiện IPA, band, collocation, ví dụ

4. Bấm "Lưu từ" trong panel
   → hiện "Đã lưu vào sổ từ"; bấm lần nữa hiện "Đã có trong sổ"

5. Sang tab "Sổ từ"
   → thấy từ vừa lưu; gõ vào ô tìm kiếm lọc đúng; bấm ✕ xoá được

6. Bôi đen một câu tiếng Việt
   → bubble hiện bản tiếng Anh; panel hiện why_notes và mục "Nên tránh"

7. Bôi đen lại đúng từ ở bước 1
   → trả về gần như tức thì (cache hit, không gọi Gemini)

8. Chạy `docker compose down` rồi bôi đen text
   → bubble hiện "Không kết nối được backend" kèm nút Thử lại
```

- [ ] **Step 8: Xác nhận cache thật sự hoạt động**

Run:
```bash
docker compose exec db psql -U ielts -d ielts \
  -c "SELECT source_text, direction, mode, hit_count FROM lookup_cache ORDER BY created_at DESC LIMIT 5;"
```
Expected: thấy các lượt tra vừa rồi, và `hit_count` > 0 ở dòng tương ứng bước 7.

- [ ] **Step 9: Chạy toàn bộ test lần cuối**

Run:
```bash
cd backend && mvn test
cd ../extension && npm test && npm run build
```
Expected: PASS toàn bộ cả hai phía.

- [ ] **Step 10: Commit**

```bash
git add extension/src/options extension/src/sidepanel/styles.css README.md
git commit -m "feat: trang Options và README; hoàn tất Phase 1"
```

---

## Sau Phase 1

Phase 1 xong là dùng được hàng ngày: dịch hai chiều, lưu từ, tra lại sổ từ.

Hai plan tiếp theo viết sau khi Phase 1 đã chạy thật vài ngày — dùng chính trải
nghiệm đó để chỉnh prompt trước khi xây tiếp:

- **Phase 2 — SRS:** migration `V3__srs_card.sql` (kèm backfill card cho từ đã lưu
  trong Phase 1), `SrsScheduler` theo SM-2 rút gọn ở mục 8 của spec, `GET /api/srs/due`,
  `POST /api/srs/review`, tab Ôn tập, badge trên icon qua `chrome.alarms`.
- **Phase 3 — Quiz:** `V4__quiz.sql`, sinh đề 3 loại, chấm `FREE_WRITE` bằng Gemini,
  tab Quiz.

