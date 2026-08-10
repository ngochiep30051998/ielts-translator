package com.hiepnn.ieltstranslator.auth;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Migration V6 đụng vào bảng chứa sổ từ THẬT của người dùng. Đây là test duy nhất chứng
 * minh dữ liệu cũ không bốc hơi và không đổi chủ.
 */
class AuthMigrationIT extends AbstractPostgresIT {

    @Autowired JdbcTemplate jdbc;

    private boolean constraintExists(String name) {
        Integer n = jdbc.queryForObject(
                "SELECT count(*) FROM pg_constraint WHERE conname = ?", Integer.class, name);
        return n != null && n > 0;
    }

    @Test
    @DisplayName("Ràng buộc UNIQUE cũ (toàn cục) đã bị thay bằng UNIQUE theo user")
    void uniqueConstraintIsNowPerUser() {
        // uq_vocab_term_pos toàn cục nghĩa là hai người không cùng lưu được từ "mitigate".
        assertThat(constraintExists("uq_vocab_term_pos")).isFalse();
        assertThat(constraintExists("uq_vocab_user_term_pos")).isTrue();
    }

    @Test
    @DisplayName("Tài khoản gốc được tạo từ placeholder bootstrap_email")
    void bootstrapUserExists() {
        assertThat(authUsers.findByEmailIgnoreCase(OWNER_EMAIL)).isPresent();
    }

    @Test
    @DisplayName("vocab_entry.user_id là NOT NULL — không hàng nào vô chủ lọt qua")
    void vocabUserIdIsNotNullable() {
        String nullable = jdbc.queryForObject("""
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name = 'vocab_entry' AND column_name = 'user_id'""", String.class);
        assertThat(nullable).isEqualTo("NO");
    }

    @Test
    @DisplayName("Xoá user thì sổ từ của user đó đi theo, không để lại hàng mồ côi")
    void deletingUserCascadesToVocab() {
        Long userId = jdbc.queryForObject("""
                INSERT INTO app_user (email, display_name) VALUES ('cascade@test.local', 'x')
                RETURNING id""", Long.class);
        jdbc.update("""
                INSERT INTO vocab_entry (term, lang, pos, meaning_vi, user_id)
                VALUES ('cascadeword', 'en', 'noun', 'x', ?)""", userId);

        jdbc.update("DELETE FROM app_user WHERE id = ?", userId);

        Integer left = jdbc.queryForObject(
                "SELECT count(*) FROM vocab_entry WHERE term = 'cascadeword'", Integer.class);
        assertThat(left).isZero();
    }

    @Test
    @DisplayName("lookup_cache CỐ Ý không có user_id — cache bản dịch dùng chung")
    void lookupCacheHasNoOwner() {
        // Bất biến ngược chiều mọi test cách ly còn lại, nên phải viết ra: ai đó "sửa cho
        // nhất quán" bằng cách thêm user_id vào đây là bỏ đi phần tiết kiệm quota Gemini
        // lớn nhất của hệ thống.
        Integer n = jdbc.queryForObject("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_name = 'lookup_cache' AND column_name = 'user_id'""", Integer.class);
        assertThat(n).isZero();
    }
}
