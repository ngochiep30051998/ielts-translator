"""Bản port của `QuizGraderTest`.

Chấm hai loại quiz chấm được tại chỗ. Hàm thuần — không DB, không mạng, không Gemini, nên
test ở đây cũng không cần fixture nào.

Hai bất biến đắt nhất của file này, cả hai đều sai lặng lẽ nếu ai đó "cải tiến":

1. **KHÔNG lemmatize.** Đề che dạng "mitigated" thì người học phải viết "mitigated". Nhận
   "mitigate" là dạy sai — chia động từ đúng chính là thứ đang luyện.
2. **Chuỗi rác là TRẢ LỜI SAI, không phải lỗi hệ thống.** Ném ở tầng chấm sẽ biến một cú gõ
   bậy của người dùng thành HTTP 500.
"""

from __future__ import annotations

from app.quiz.grader import grade_collocation, grade_fill_blank

# ── FILL_BLANK ────────────────────────────────────────────────────────────────


def test_khop_chinh_xac_thi_dung() -> None:
    """Ca cơ bản nhất: gõ đúng nguyên văn đáp án thì đúng."""
    assert grade_fill_blank("mitigate", "mitigate") is True


def test_thua_khoang_trang_hai_dau_van_dung() -> None:
    """Khoảng trắng thừa hai đầu là lỗi gõ, không phải lỗi kiến thức.

    Ô nhập của panel không tự trim, nên không cắt ở đây là chấm sai người gõ đúng.
    """
    assert grade_fill_blank("  mitigate  ", "mitigate") is True


def test_khac_hoa_thuong_van_dung() -> None:
    """Viết hoa không phải thứ đang luyện ở loại câu này."""
    assert grade_fill_blank("MITIGATE", "mitigate") is True
    assert grade_fill_blank("Mitigate", "mitigate") is True


def test_khong_lemmatize_sai_dang_tu_la_sai() -> None:
    """CỐ Ý không lemmatize — sai dạng từ là sai.

    Chấp nhận "mitigate" khi đáp án là "mitigated" là dạy sai: chia động từ đúng chính là
    thứ câu điền từ đang luyện.
    """
    assert grade_fill_blank("mitigate", "mitigated") is False
    assert grade_fill_blank("mitigating", "mitigate") is False
    assert grade_fill_blank("mitigates", "mitigate") is False


def test_rong_chi_khoang_trang_hoac_none_deu_sai_khong_no() -> None:
    """Rỗng, chỉ khoảng trắng, hoặc None đều là SAI và không được ném.

    Chuỗi rỗng là giá trị hợp lệ trên đường truyền — nó nghĩa là "bỏ qua câu này". Ném ở đây
    biến một thao tác học tập bình thường thành HTTP 500.
    """
    assert grade_fill_blank("", "mitigate") is False
    assert grade_fill_blank("   ", "mitigate") is False
    assert grade_fill_blank(None, "mitigate") is False
    assert grade_fill_blank("mitigate", None) is False


def test_lower_chu_khong_casefold() -> None:
    """So bằng `lower()` chứ KHÔNG `casefold()` — bằng đúng `equalsIgnoreCase` bên Java.

    Không có trong bản Java vì Java không có `casefold` để mà chọn nhầm. Ở Python thì có, và
    nó gấp "ß" thành "ss": đổi một chữ sẽ âm thầm nhận đúng những cặp mà bản gốc coi là khác
    nhau. Đây là chỗ chấm bài — nới lỏng âm thầm là chấm sai.
    """
    assert grade_fill_blank("straße", "strasse") is False


# ── COLLOCATION_CHOICE ────────────────────────────────────────────────────────


def test_chon_dung_index_thi_dung() -> None:
    """Answer đi trên đường truyền LUÔN là chuỗi, kể cả với câu trắc nghiệm."""
    assert grade_collocation("2", 2) is True
    assert grade_collocation(" 2 ", 2) is True


def test_chon_sai_index_thi_sai() -> None:
    """Chọn nhầm ô thì sai — không có phần thưởng cho việc chọn gần đúng."""
    assert grade_collocation("1", 2) is False


def test_answer_khong_parse_duoc_la_sai_khong_phai_loi() -> None:
    """Chuỗi không parse được thành index tính là SAI, không phải lỗi.

    Người dùng gõ bậy không phải sự cố hệ thống. `"2.0"` nằm trong danh sách một cách có chủ
    ý: nó là ca dễ bị "sửa cho tiện" nhất bằng cách parse số thực, mà làm vậy là nhận một
    hình dạng answer thứ hai chưa ai khai trong hợp đồng API.
    """
    assert grade_collocation("hai", 2) is False
    assert grade_collocation("", 2) is False
    assert grade_collocation(None, 2) is False
    assert grade_collocation("2.0", 2) is False
    assert grade_collocation("99999999999999999999", 2) is False
