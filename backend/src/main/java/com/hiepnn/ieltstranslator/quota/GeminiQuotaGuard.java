package com.hiepnn.ieltstranslator.quota;

import com.hiepnn.ieltstranslator.auth.AuthProperties;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

/**
 * Hạn mức gọi Gemini theo từng người, mỗi ngày.
 *
 * <p>Gọi NGAY TRƯỚC mỗi {@code gemini.generateJson} và SAU khi đã tra cache — cache hit
 * không chạm Gemini nên tính vào hạn mức là phạt oan.
 */
@Component
public class GeminiQuotaGuard {

    private final GeminiUsageRepository usage;
    private final AuthProperties props;

    public GeminiQuotaGuard(GeminiUsageRepository usage, AuthProperties props) {
        this.usage = usage;
        this.props = props;
    }

    @Transactional
    public void consume(Long userId) {
        if (props.dailyGeminiCalls() <= 0) {
            return;   // 0 hoặc âm = tắt hạn mức, dùng cho môi trường dev
        }
        int used = usage.incrementAndGet(userId, LocalDate.now());
        if (used > props.dailyGeminiCalls()) {
            // GEMINI_QUOTA chứ không đẻ mã mới: UI đã biết hiển thị mã này, và với người
            // dùng thì "hết lượt hôm nay" đúng là hết quota.
            throw AppException.of(ErrorCode.GEMINI_QUOTA,
                    "Đã dùng hết " + props.dailyGeminiCalls() + " lượt AI của hôm nay");
        }
    }
}
