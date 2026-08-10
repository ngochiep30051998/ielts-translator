package com.hiepnn.ieltstranslator.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Đọc {@code Authorization: Bearer <token>} và đặt user vào AuthContext.
 *
 * <p>Filter này CỐ Ý không từ chối request nào. Nó chỉ nhận diện; việc bắt buộc đăng nhập
 * nằm ở {@code AuthContext.requireUserId()} trong controller. Lý do: exception ném từ filter
 * chạy ngoài phạm vi @RestControllerAdvice nên không giữ được hình dạng lỗi chuẩn — người
 * dùng sẽ nhận một trang lỗi HTML thay vì {code, message, retryable}.
 */
@Component
public class SessionFilter extends OncePerRequestFilter {

    private static final String BEARER = "Bearer ";

    private final AuthService authService;
    private final AuthContext context;

    public SessionFilter(AuthService authService, AuthContext context) {
        this.authService = authService;
        this.context = context;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header != null && header.startsWith(BEARER)) {
            String token = header.substring(BEARER.length()).trim();
            // Token rác không ném: nó chỉ đơn giản là không nhận diện được ai, và
            // requireUserId() sẽ trả UNAUTHORIZED đúng hình dạng ở tầng trên.
            authService.resolveUserId(token).ifPresent(context::set);
        }
        chain.doFilter(request, response);
    }
}
