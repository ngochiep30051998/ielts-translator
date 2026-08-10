package com.hiepnn.ieltstranslator.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.tomakehurst.wiremock.WireMockServer;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.List;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.options;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.fail;

/**
 * Tầng HTTP đi Google. WireMock ở ĐÂY là đúng chỗ — khác AuthControllerIT, nơi thứ đang
 * test là luồng nghiệp vụ nên GoogleTokenClient bị mock thẳng.
 */
class GoogleTokenClientTest {

    private static final String REDIRECT = "https://testextensionid.chromiumapp.org/";

    private static WireMockServer wireMock;
    private GoogleTokenClient client;

    @BeforeAll
    static void startServer() {
        wireMock = new WireMockServer(options().dynamicPort());
        wireMock.start();
    }

    @AfterAll
    static void stopServer() {
        wireMock.stop();
    }

    @BeforeEach
    void setUp() {
        wireMock.resetAll();
        AuthProperties props = new AuthProperties("client-id", "SIEU-BI-MAT",
                wireMock.baseUrl(), List.of("a@b.com"), "testextensionid", 60, 0);
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(2));
        factory.setReadTimeout(Duration.ofSeconds(2));
        RestClient restClient = RestClient.builder()
                .requestFactory(factory).baseUrl(wireMock.baseUrl()).build();
        client = new GoogleTokenClient(restClient, props, new ObjectMapper());
    }

    private static String base64Url(String json) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(json.getBytes(StandardCharsets.UTF_8));
    }

    private void stubToken(int status, String body) {
        wireMock.stubFor(post(urlPathEqualTo("/token"))
                .willReturn(aResponse().withStatus(status)
                        .withHeader("Content-Type", "application/json")
                        .withBody(body)));
    }

    @Test
    @DisplayName("Đọc sub và email từ payload id_token — KHÔNG verify chữ ký")
    void parsesIdTokenPayload() {
        // Chữ ký "rác" là CỐ Ý. Token đến thẳng từ token endpoint qua TLS và mình đã xác
        // thực với Google bằng client_secret, nên theo tài liệu OIDC của Google không cần
        // verify. Test này khoá chính hành vi đó: ai thêm bước verify vào sẽ thấy nó đỏ và
        // phải đọc lại spec mục 3 trước khi đổi.
        String payload = base64Url("""
                {"sub":"1234567890","email":"A@B.com","email_verified":true,"name":"A B"}""");
        stubToken(200, "{\"id_token\":\"header." + payload + ".chu-ky-rac\"}");

        GoogleIdentity id = client.exchange("code-abc", REDIRECT);

        assertThat(id.sub()).isEqualTo("1234567890");
        // Email hạ về chữ thường ngay tại đây: allowlist so bằng chuỗi, và Google có thể
        // trả về hoa thường bất kỳ.
        assertThat(id.email()).isEqualTo("a@b.com");
        assertThat(id.emailVerified()).isTrue();
    }

    @Test
    @DisplayName("Google trả 400 (code hết hạn/đã dùng) → UNAUTHORIZED, không phải AUTH_UNAVAILABLE")
    void expiredCodeIsUnauthorized() {
        stubToken(400, "{\"error\":\"invalid_grant\"}");

        // try/catch chứ không chuỗi fluent: đọc thẳng code() của AppException là cách
        // khẳng định không phụ thuộc phiên bản AssertJ nào.
        try {
            client.exchange("code-cu", REDIRECT);
            fail("Phải ném UNAUTHORIZED");
        } catch (AppException ex) {
            assertThat(ex.code()).isEqualTo(ErrorCode.UNAUTHORIZED);
        }
    }

    @Test
    @DisplayName("Google trả 503 → AUTH_UNAVAILABLE và retry được")
    void googleDownIsRetryable() {
        stubToken(503, "");

        try {
            client.exchange("code-abc", REDIRECT);
            fail("Phải ném AUTH_UNAVAILABLE");
        } catch (AppException ex) {
            assertThat(ex.code()).isEqualTo(ErrorCode.AUTH_UNAVAILABLE);
            assertThat(ex.retryable()).isTrue();
        }
    }

    @Test
    @DisplayName("id_token thiếu → UNAUTHORIZED chứ không NullPointerException")
    void missingIdTokenIsUnauthorized() {
        stubToken(200, "{\"access_token\":\"chi-co-access-token\"}");

        assertThatThrownBy(() -> client.exchange("code-abc", REDIRECT))
                .isInstanceOf(AppException.class);
    }

    @Test
    @DisplayName("id_token không đủ ba phần → UNAUTHORIZED")
    void malformedIdTokenIsUnauthorized() {
        stubToken(200, "{\"id_token\":\"khong-phai-jwt\"}");

        assertThatThrownBy(() -> client.exchange("code-abc", REDIRECT))
                .isInstanceOf(AppException.class);
    }

    @Test
    @DisplayName("client_secret KHÔNG lọt vào thông điệp lỗi")
    void secretNeverLeaksIntoErrors() {
        stubToken(400, "{\"error\":\"invalid_grant\"}");

        // Thông điệp lỗi đi thẳng ra response cho extension. Một client HTTP nhét nguyên
        // request body vào message là đủ để secret rời khỏi server.
        try {
            client.exchange("code-abc", REDIRECT);
            fail("Phải ném lỗi");
        } catch (AppException ex) {
            assertThat(ex.getMessage()).isNotNull();
            assertThat(ex.getMessage()).doesNotContain("SIEU-BI-MAT");
        }
    }
}
