package com.hiepnn.ieltstranslator.auth;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AppUserRepository extends JpaRepository<AppUser, Long> {

    Optional<AppUser> findByGoogleSub(String googleSub);

    /**
     * IgnoreCase là BẮT BUỘC, không phải chiều lòng.
     *
     * <p>Google trả email chữ thường, nhưng AUTH_BOOTSTRAP_EMAIL do người gõ tay vào .env
     * thì không chắc. Lệch hoa thường = tạo tài khoản thứ hai, và toàn bộ sổ từ cũ nằm ở
     * tài khoản không ai đăng nhập được.
     */
    Optional<AppUser> findByEmailIgnoreCase(String email);
}
