package com.hiepnn.ieltstranslator.auth;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * Đổi authorization code lấy danh tính Google.
 *
 * <p>Việc đổi code nằm ở BACKEND chứ không ở extension, và đó là quyết định trung tâm của
 * cả tính năng: token đi thẳng từ token endpoint của Google về đây qua TLS, xác thực bằng
 * client_secret. Nếu extension tự đổi rồi gửi id_token lên thì backend buộc phải verify
 * chữ ký RS256 qua JWKS — code bảo mật không nên tự viết, và viết đúng thì phải kéo thêm
 * thư viện.
 */
@Component
public class GoogleTokenClient {

    private static final Logger log = LoggerFactory.getLogger(GoogleTokenClient.class);

    private final RestClient restClient;
    private final AuthProperties props;
    private final ObjectMapper mapper;

    public GoogleTokenClient(@Qualifier("googleRestClient") RestClient restClient,
                             AuthProperties props, ObjectMapper mapper) {
        this.restClient = restClient;
        this.props = props;
        this.mapper = mapper;
    }

    /**
     * @param redirectUri PHẢI là chuỗi backend tự dựng từ EXTENSION_ID, không phải chuỗi
     *                    client gửi lên. AuthService đã so trước khi gọi vào đây; bỏ bước
     *                    đó là cho một extension lạ mượn client_secret của mình.
     */
    public GoogleIdentity exchange(String code, String redirectUri) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("code", code);
        form.add("client_id", props.googleClientId());
        form.add("client_secret", props.googleClientSecret());
        form.add("redirect_uri", redirectUri);
        form.add("grant_type", "authorization_code");

        ResponseEntity<String> response;
        try {
            response = restClient.post()
                    .uri("/token")
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(form)
                    .retrieve()
                    .onStatus(status -> true, (req, res) -> { /* xử lý thủ công bên dưới */ })
                    .toEntity(String.class);
        } catch (RestClientException ex) {
            // KHÔNG đưa ex vào message: form body chứa client_secret và một số client HTTP
            // nhét nguyên request vào thông điệp lỗi.
            log.warn("Không gọi được Google token endpoint");
            throw AppException.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi");
        }

        int status = response.getStatusCode().value();
        if (status == 400 || status == 401) {
            // Code hết hạn, đã dùng, hoặc redirect_uri không khớp. Đây là lỗi của REQUEST,
            // không phải của Google — trả AUTH_UNAVAILABLE ở đây sẽ mời người dùng thử lại
            // một việc không bao giờ thành công.
            log.warn("Google từ chối authorization code (HTTP {})", status);
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Mã đăng nhập không hợp lệ hoặc đã hết hạn");
        }
        if (status >= 500 || status == 429) {
            throw AppException.of(ErrorCode.AUTH_UNAVAILABLE, "Google đang không phản hồi");
        }
        if (status != 200) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Google trả mã không mong đợi: " + status);
        }

        return parse(readIdToken(response.getBody()));
    }

    private String readIdToken(String body) {
        try {
            JsonNode json = mapper.readTree(body == null ? "" : body);
            String idToken = json.path("id_token").asText("");
            if (idToken.isBlank()) {
                throw AppException.of(ErrorCode.UNAUTHORIZED, "Google không trả id_token");
            }
            return idToken;
        } catch (AppException ex) {
            throw ex;
        } catch (Exception ex) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Không đọc được phản hồi từ Google");
        }
    }

    /**
     * Đọc payload của JWT mà KHÔNG verify chữ ký.
     *
     * <p>Hợp lệ ĐÚNG trong tình huống này và không nơi nào khác: token vừa đi thẳng từ token
     * endpoint của Google về đây qua TLS, và mình đã tự xác thực với Google bằng
     * client_secret. Tài liệu OpenID Connect của Google nói rõ chỗ này.
     *
     * <p>NẾU sau này token đến từ client thay vì từ token endpoint, PHẢI verify RS256 qua
     * JWKS. Sửa chỗ nhận token mà quên chỗ này là biến "đăng nhập" thành "khai mình là ai
     * cũng được".
     */
    private GoogleIdentity parse(String idToken) {
        String[] parts = idToken.split("\\.");
        if (parts.length != 3) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Google trả id_token không hợp lệ");
        }
        try {
            byte[] payload = Base64.getUrlDecoder().decode(parts[1]);
            JsonNode claims = mapper.readTree(new String(payload, StandardCharsets.UTF_8));
            String sub = claims.path("sub").asText("");
            String email = claims.path("email").asText("");
            if (sub.isBlank() || email.isBlank()) {
                throw AppException.of(ErrorCode.UNAUTHORIZED, "id_token thiếu sub hoặc email");
            }
            return new GoogleIdentity(sub, email.toLowerCase(java.util.Locale.ROOT),
                    claims.path("email_verified").asBoolean(false),
                    claims.path("name").asText(null),
                    claims.path("picture").asText(null));
        } catch (AppException ex) {
            throw ex;
        } catch (Exception ex) {
            throw AppException.of(ErrorCode.UNAUTHORIZED, "Không đọc được id_token của Google");
        }
    }
}
