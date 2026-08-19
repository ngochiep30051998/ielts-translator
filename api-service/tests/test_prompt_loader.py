"""Bản port của `PromptLoaderTest`.

Bản Java phải gọi `readTemplate` qua reflection để test các nhánh lỗi parser. Ở đây
`PromptLoader` nhận thẳng tham số `directory`, nên test trỏ vào thư mục prompt hỏng một
cách bình thường.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.translation.models import Direction, Mode
from app.translation.prompts import PromptError, PromptLoader, PromptTemplate

TEST_DIR = Path(__file__).resolve().parent
INVALID = PromptLoader(TEST_DIR / "prompts-invalid")
EDGE = PromptLoader(TEST_DIR / "prompts-edge")


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader()


@pytest.mark.parametrize("direction", list(Direction))
@pytest.mark.parametrize("mode", list(Mode))
def test_loads_all_four_templates(
    loader: PromptLoader, direction: Direction, mode: Mode
) -> None:
    template = loader.load(direction, mode)

    assert template.version >= 1
    assert template.body.strip()
    assert not template.body.startswith("version:")


def test_header_is_stripped_but_field_names_containing_version_are_kept(
    loader: PromptLoader,
) -> None:
    template = loader.load(Direction.VI_EN, Mode.SENTENCE)

    assert template.version == 1
    assert not template.body.startswith("version:")
    # `band65_version` là tên trường trong schema, KHÔNG phải header sót lại.
    assert "band65_version" in template.body


def test_render_substitutes_text_and_context() -> None:
    template = PromptTemplate("Tra từ: {{TEXT}}\nNgữ cảnh: {{CONTEXT}}", 1)

    assert (
        template.render_text("renewable", "We need renewable energy.")
        == "Tra từ: renewable\nNgữ cảnh: We need renewable energy."
    )


def test_render_handles_empty_context() -> None:
    """Để `{{CONTEXT}}` thành chuỗi trắng sẽ làm model tưởng ngữ cảnh bị cắt mất."""
    template = PromptTemplate("{{TEXT}}|{{CONTEXT}}", 1)

    assert template.render_text("x", None) == "x|(không có ngữ cảnh)"
    assert template.render_text("x", "   ") == "x|(không có ngữ cảnh)"


def test_missing_delimiter_line_raises_error_with_file_name() -> None:
    with pytest.raises(PromptError) as ex:
        INVALID.load_file("no-delimiter.md")

    assert "no-delimiter.md" in str(ex.value)


def test_non_numeric_version_raises_error_with_file_name() -> None:
    with pytest.raises(PromptError) as ex:
        INVALID.load_file("bad-version.md")

    assert "bad-version.md" in str(ex.value)
    assert isinstance(ex.value.__cause__, ValueError)


def test_decoy_delimiter_line_is_rejected_instead_of_splitting_body_wrong() -> None:
    """File có dòng `--- ghi chú ...` bắt đầu bằng `---` nhưng KHÔNG đúng bằng `---` sau khi
    strip, nằm TRƯỚC dòng phân cách thật.

    Nếu parser khớp theo tiền tố, dòng này bị nhầm là delimiter: nội dung của nó bị nuốt mất
    và body bị cắt sai, còn sót `---` thừa ở đầu — sai lặng lẽ, không ai biết. Với luật "chỉ
    nhận dòng khớp ĐÚNG `---`", dòng giả gộp vào header, header không parse được thành số,
    và parser từ chối RÕ RÀNG kèm đường dẫn file.
    """
    with pytest.raises(PromptError) as ex:
        INVALID.load_file("decoy-delimiter.md")

    assert "decoy-delimiter.md" in str(ex.value)


def test_body_may_contain_its_own_horizontal_rule() -> None:
    """Prompt dùng đường kẻ ngang markdown `---` bên TRONG thân bài, sau dòng phân cách
    thật. Parser chỉ được dừng ở dòng `---` ĐẦU TIÊN."""
    template = EDGE.load_file("body-with-horizontal-rule.md")

    assert template.version == 1
    assert template.body.startswith("Phần 1: giới thiệu {{TEXT}}.")
    assert "\n---\n" in template.body
    assert template.body.endswith("Phần 2: kết luận.")


def test_every_translation_template_has_text_placeholder(loader: PromptLoader) -> None:
    for d in Direction:
        for m in Mode:
            assert "{{TEXT}}" in loader.load(d, m).body, f"{d}/{m} phải có {{{{TEXT}}}}"


def test_loads_distractor_prompt_by_file_name(loader: PromptLoader) -> None:
    template = loader.load_file("srs-distractors.md")

    assert template.version == 1
    assert "{{TERM}}" in template.body
    assert "{{MEANING_VI}}" in template.body


def test_three_quiz_prompts_load_and_have_all_placeholders(loader: PromptLoader) -> None:
    for file_name in ("quiz-fill-blank.md", "quiz-collocation.md", "quiz-grade-free-write.md"):
        template = loader.load_file(file_name)
        assert template.version > 0, f"{file_name} phải có version dương"
        assert template.body.strip(), f"{file_name} không được rỗng"

    assert "{{TERMS}}" in loader.load_file("quiz-fill-blank.md").body
    assert "{{TERMS}}" in loader.load_file("quiz-collocation.md").body
    body = loader.load_file("quiz-grade-free-write.md").body
    for ph in ("{{TERM}}", "{{ANSWER}}", "{{MEANING_VI}}"):
        assert ph in body


def test_three_explanation_prompts_load_and_have_all_placeholders(loader: PromptLoader) -> None:
    for file_name in (
        "quiz-explain-fill-blank.md",
        "quiz-explain-collocation.md",
        "quiz-explain-free-write.md",
    ):
        template = loader.load_file(file_name)
        assert template.version > 0, f"{file_name} phải có version dương"
        assert template.body.strip(), f"{file_name} không được rỗng"
        # {{USER_ANSWER}} là điều kiện để giải thích BÁM THEO câu trả lời của người học.
        # Thiếu nó thì prompt lặng lẽ tụt về giải thích chung chung và không có gì trong hệ
        # thống phát hiện ra.
        assert "{{USER_ANSWER}}" in template.body, f"{file_name} phải có {{{{USER_ANSWER}}}}"

    fill = loader.load_file("quiz-explain-fill-blank.md").body
    assert "{{SENTENCE}}" in fill and "{{ANSWER}}" in fill
    colloc = loader.load_file("quiz-explain-collocation.md").body
    assert "{{OPTIONS}}" in colloc and "{{ANSWER}}" in colloc
    free = loader.load_file("quiz-explain-free-write.md").body
    assert "{{TERM}}" in free and "{{SENTENCE_EN}}" in free


def test_render_substitutes_every_key_correctly(loader: PromptLoader) -> None:
    rendered = loader.load_file("srs-distractors.md").render(
        {
            "TERM": "mitigate",
            "MEANING_VI": "giảm nhẹ",
            "POS": "verb",
            "DEFINITION_EN": "to make less severe",
        }
    )

    for expected_fragment in ("mitigate", "giảm nhẹ", "verb", "to make less severe"):
        assert expected_fragment in rendered
    assert "{{" not in rendered


def test_version_goes_into_cache_key_so_every_prompt_must_declare_version(
    loader: PromptLoader,
) -> None:
    """Ràng buộc #5: sửa nội dung prompt PHẢI tăng `version:`.

    Test này không kiểm được người ta có tăng hay không, nhưng nó chặn ca tệ hơn: một file
    prompt mới thêm vào mà QUÊN HẲN header version. Không có nó thì file đó chết lúc chạy
    thật, ở một endpoint ngẫu nhiên, chứ không phải ở đây.
    """
    from app.translation.prompts import PROMPTS_DIR

    for path in sorted(PROMPTS_DIR.glob("*.md")):
        template = loader.load_file(path.name)
        assert template.version > 0, f"{path.name} thiếu header version hợp lệ"
