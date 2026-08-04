package com.hiepnn.ieltstranslator.translation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PromptLoaderTest {

    private final PromptLoader loader = new PromptLoader();

    /**
     * Gọi thẳng PromptLoader.readTemplate (private) qua reflection để test các
     * nhánh lỗi parser bằng file giả trong test/resources, mà không phải đổi
     * chữ ký public của PromptLoader chỉ để phục vụ test.
     */
    private PromptTemplate readTemplateViaReflection(String path) throws Exception {
        Method method = PromptLoader.class.getDeclaredMethod("readTemplate", String.class);
        method.setAccessible(true);
        try {
            return (PromptTemplate) method.invoke(loader, path);
        } catch (InvocationTargetException e) {
            if (e.getCause() instanceof RuntimeException re) {
                throw re;
            }
            throw e;
        }
    }

    @ParameterizedTest
    @CsvSource({
        "EN_VI, WORD", "EN_VI, SENTENCE", "VI_EN, WORD", "VI_EN, SENTENCE"
    })
    void loadsAllFourTemplates(Direction direction, Mode mode) {
        PromptTemplate template = loader.load(direction, mode);

        assertThat(template.version()).isGreaterThanOrEqualTo(1);
        assertThat(template.body()).isNotBlank();
        assertThat(template.body()).doesNotStartWith("version:");
    }

    @Test
    void headerIsStrippedButBodyKeepsFieldNamesContainingVersion() {
        PromptTemplate template = loader.load(Direction.VI_EN, Mode.SENTENCE);

        assertThat(template.version()).isEqualTo(1);
        assertThat(template.body()).doesNotStartWith("version:");
        // band65_version là tên trường trong schema, KHÔNG phải header sót lại
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
    void throwsWithFileNameWhenDelimiterMissing() {
        assertThatThrownBy(() -> readTemplateViaReflection("prompts-invalid/no-delimiter.md"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("prompts-invalid/no-delimiter.md");
    }

    @Test
    void throwsWithFileNameWhenVersionIsNotANumber() {
        assertThatThrownBy(() -> readTemplateViaReflection("prompts-invalid/bad-version.md"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("prompts-invalid/bad-version.md")
                .hasCauseInstanceOf(NumberFormatException.class);
    }

    @Test
    void decoyDashLineBeforeRealDelimiterIsRejectedInsteadOfSilentlyCorruptingBody() {
        // File có dòng "--- ghi chú ..." bắt đầu bằng "---" nhưng KHÔNG đúng bằng
        // "---" sau khi strip, nằm trước dòng phân cách thật. Với cách cũ
        // (indexOf("\n---") khớp theo tiền tố), dòng này bị nhầm là delimiter:
        // nội dung của nó bị nuốt mất và body sẽ bị cắt sai, còn sót "---" thừa ở
        // đầu — sai lặng lẽ, không ai biết. Với cách mới (chỉ nhận dòng khớp
        // đúng "---"), dòng giả bị bỏ qua nên nó gộp vào header cùng "version: 1",
        // khiến header không còn parse được thành số — parser từ chối RÕ RÀNG
        // (loud, kèm đường dẫn file) thay vì đoán bừa và cắt sai trong im lặng.
        assertThatThrownBy(() -> readTemplateViaReflection("prompts-invalid/decoy-delimiter.md"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("prompts-invalid/decoy-delimiter.md");
    }

    @Test
    void bodyMayContainItsOwnStandaloneDashLineAfterTheRealDelimiter() throws Exception {
        // Kịch bản reviewer nêu: prompt tương lai dùng đường kẻ ngang markdown
        // "---" bên TRONG thân bài, sau dòng phân cách thật. Parser chỉ được
        // dừng ở dòng "---" ĐẦU TIÊN (dòng phân cách thật); dòng "---" thứ hai
        // nằm trong body phải được giữ nguyên, không bị cắt mất.
        PromptTemplate template = readTemplateViaReflection("prompts-edge/body-with-horizontal-rule.md");

        assertThat(template.version()).isEqualTo(1);
        assertThat(template.body())
                .startsWith("Phần 1: giới thiệu {{TEXT}}.")
                .contains("\n---\n")
                .endsWith("Phần 2: kết luận.");
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
