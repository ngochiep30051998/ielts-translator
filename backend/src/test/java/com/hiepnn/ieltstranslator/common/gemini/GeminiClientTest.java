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
        stubGemini(200, candidateWrapping("{\"meaning_vi\":\"tái tạo\"}"));

        JsonNode result = client.generateJson("prompt bất kỳ", SCHEMA);

        assertThat(result.get("meaning_vi").asText()).isEqualTo("tái tạo");
    }

    @Test
    void sendsApiKeyAndResponseSchema() {
        stubGemini(200, candidateWrapping("{\"meaning_vi\":\"x\"}"));

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
                        .withBody(candidateWrapping("{\"meaning_vi\":\"ổn\"}"))));

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
