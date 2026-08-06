package com.hiepnn.ieltstranslator.common.gemini;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Kiểm chứng bằng LỆNH, không bằng suy luận: bean {@code Map<GeminiTimeout, RestClient>}
 * inject được mà KHÔNG cần {@code @Qualifier}.
 *
 * <p>Vì sao phải có test riêng: Spring có một nhánh đặc biệt coi tham số kiểu {@code Map}
 * là "gom mọi bean cùng type theo TÊN bean" — nhánh đó chỉ áp dụng khi khoá là
 * {@code String}. Khoá của ta là enum nên map được phân giải như một bean thường. Kết
 * luận đó trước đây đọc từ source spring-beans chứ chưa từng chạy thử; nếu sai thì cả
 * ứng dụng chết lúc khởi động với NoSuchBeanDefinitionException. Đổi khoá sang String
 * là chỗ hỏng — test này sẽ đỏ ngay.
 */
class GeminiWiringIT extends AbstractPostgresIT {

    @Autowired Map<GeminiTimeout, RestClient> geminiRestClients;
    @Autowired GeminiClient geminiClient;

    @Test
    @DisplayName("Map khoá enum inject được, đủ ba mức, và GeminiClient thật dựng được từ nó")
    void enumKeyedMapIsInjectedWithoutQualifier() {
        assertThat(geminiRestClients).hasSize(3)
                .containsKeys(GeminiTimeout.TRANSLATE, GeminiTimeout.QUIZ_GENERATE,
                              GeminiTimeout.QUIZ_GRADE);
        // Ba client PHẢI là ba instance khác nhau: read-timeout được nướng vào request
        // factory lúc dựng, dùng chung một instance là ba mức cùng chạy một ngưỡng.
        assertThat(geminiRestClients.values()).doesNotHaveDuplicates();
        assertThat(geminiClient).isNotNull();
    }
}
