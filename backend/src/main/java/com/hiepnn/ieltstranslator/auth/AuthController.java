package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.auth.dto.AuthSessionDto;
import com.hiepnn.ieltstranslator.auth.dto.AuthUserDto;
import com.hiepnn.ieltstranslator.auth.dto.GoogleLoginRequest;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private static final String BEARER = "Bearer ";

    private final AuthService authService;
    private final AuthContext auth;

    public AuthController(AuthService authService, AuthContext auth) {
        this.authService = authService;
        this.auth = auth;
    }

    /** Công khai — đây là đường DUY NHẤT để có token, nên nó không thể đòi token. */
    @PostMapping("/google")
    public AuthSessionDto google(@Valid @RequestBody GoogleLoginRequest request) {
        return authService.login(request.code(), request.redirectUri());
    }

    /**
     * Cách extension kiểm token còn sống sau khi Chrome khởi động lại, thay vì đợi một
     * request nghiệp vụ nào đó nhận 401 rồi mới biết.
     */
    @GetMapping("/me")
    public AuthUserDto me() {
        return authService.me(auth.requireUserId());
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        // requireUserId() trước: logout không token là một request vô nghĩa, và trả 204 cho
        // nó sẽ làm client tưởng đã thu hồi được gì đó.
        auth.requireUserId();
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header != null && header.startsWith(BEARER)) {
            authService.logout(header.substring(BEARER.length()).trim());
        }
        return ResponseEntity.noContent().build();
    }
}
