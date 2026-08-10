"""Bản port của `QuizItemValidatorTest`.

Bộ kiểm từng item Gemini trả về, chạy TRƯỚC khi item được lưu xuống `quiz_item`. Hàm thuần
— không DB, không mạng.

Vì sao nó khắt khe tới mức này: một item lọt lưới không làm gì đỏ cả, nó chỉ hiện ra trước
mặt người học dưới dạng một câu hỏi vô nghĩa (đáp án nằm sẵn trong đề, hai ô cùng nội dung,
chỗ trống không tồn tại) và sống mãi trong DB cho tới khi ai đó tăng `prompt_version`.
"""

from __future__ import annotations

from app.quiz.validator import is_valid_collocation, is_valid_fill_blank

# ── FILL_BLANK ────────────────────────────────────────────────────────────────


def test_cau_co_cho_trong_va_dap_an_khong_lo_thi_hop_le() -> None:
    """Ca chuẩn: có `___`, đáp án không lộ ở đâu cả, gợi ý có nội dung."""
    assert (
        is_valid_fill_blank(
            "Governments must ___ the effects of climate change.",
            "mitigate",
            "động từ, làm cho nhẹ bớt",
        )
        is True
    )


def test_cau_thieu_cho_trong_thi_loai() -> None:
    """Không có chỗ trống thì không phải câu điền từ.

    Đề kiểu này lọt xuống panel là một câu hoàn chỉnh kèm ô nhập không biết điền vào đâu.
    """
    cau = "Governments must mitigate the effects."
    assert is_valid_fill_blank(cau, "mitigate", "gợi ý") is False


def test_dap_an_lo_nguyen_van_o_cho_khac_thi_loai() -> None:
    """Đáp án xuất hiện ở phần còn lại của câu là lộ đáp án ngay trên đề."""
    cau = "To mitigate risk, we must ___ the impact."
    assert is_valid_fill_blank(cau, "mitigate", "gợi ý") is False


def test_dap_an_lo_khac_hoa_thuong_van_la_lo() -> None:
    """Người học vẫn đọc thấy — phép so lộ đáp án phải bỏ phân biệt hoa thường."""
    assert (
        is_valid_fill_blank("Mitigate is the key: we must ___ the impact.", "mitigate", "gợi ý")
        is False
    )


def test_dap_an_rong_hoac_chi_khoang_trang_thi_loai() -> None:
    """Đáp án rỗng thì không có gì để chấm — câu đó vĩnh viễn sai."""
    assert is_valid_fill_blank("We must ___ it.", "   ", "gợi ý") is False
    assert is_valid_fill_blank("We must ___ it.", "", "gợi ý") is False


def test_hint_rong_thi_loai() -> None:
    """`question` của FILL_BLANK dựng thành "…Gợi ý: " + hint, nên hint rỗng là đề cụt."""
    assert is_valid_fill_blank("We must ___ it.", "mitigate", "") is False
    assert is_valid_fill_blank("We must ___ it.", "mitigate", "   ") is False
    assert is_valid_fill_blank("We must ___ it.", "mitigate", None) is False


def test_hint_chua_dap_an_thi_loai() -> None:
    """Gợi ý mà lộ đáp án thì câu hỏi vô nghĩa — và hint là thứ DUY NHẤT luôn hiện trên đề."""
    assert is_valid_fill_blank("We must ___ it.", "mitigate", "dùng từ mitigate") is False
    assert is_valid_fill_blank("We must ___ it.", "mitigate", "dùng từ MITIGATE") is False


def test_none_o_dau_cung_loai_khong_no_fill_blank() -> None:
    """Gemini trả thiếu field là chuyện thường; nó phải làm item bị loại, không làm sập lô."""
    assert is_valid_fill_blank(None, "mitigate", "gợi ý") is False
    assert is_valid_fill_blank("We must ___ it.", None, "gợi ý") is False


# ── COLLOCATION_CHOICE ────────────────────────────────────────────────────────


def test_bon_lua_chon_khac_nhau_va_index_trong_khoang_thi_hop_le() -> None:
    """Ca chuẩn: đúng 4 lựa chọn phân biệt, `correct_index` nằm trong 0..3."""
    assert (
        is_valid_collocation(
            ["mitigate risk", "mitigate a cake", "mitigate loudly", "mitigate blue"], 0
        )
        is True
    )


def test_ba_hoac_nam_lua_chon_thi_loai() -> None:
    """UI dựng đúng 4 ô — thừa hay thiếu đều là câu hỏi không render được đúng."""
    assert is_valid_collocation(["a", "b", "c"], 0) is False
    assert is_valid_collocation(["a", "b", "c", "d", "e"], 0) is False


def test_hai_lua_chon_trung_nhau_thi_loai() -> None:
    """Hai ô cùng nội dung là câu hỏi hỏng — kể cả khi chỉ khác hoa thường.

    Người học chọn ô "sai" mang đúng nội dung ô đúng sẽ bị chấm sai mà không hiểu vì sao.
    """
    assert is_valid_collocation(["mitigate risk", "Mitigate Risk", "c", "d"], 0) is False


def test_lua_chon_rong_thi_loai() -> None:
    """Một ô trắng giữa bốn ô là đề hỏng, không phải mồi nhử khó."""
    assert is_valid_collocation(["a", "  ", "c", "d"], 0) is False


def test_correct_index_ngoai_khoang_thi_loai() -> None:
    """Ngoài 0..3 là không có đáp án đúng nào trong bốn ô — mọi câu trả lời đều sai."""
    assert is_valid_collocation(["a", "b", "c", "d"], -1) is False
    assert is_valid_collocation(["a", "b", "c", "d"], 4) is False


def test_none_o_dau_cung_loai_khong_no_collocation() -> None:
    """Thiếu `options`, thiếu `correct_index`, hay một phần tử sai kiểu đều làm item bị loại."""
    assert is_valid_collocation(None, 0) is False
    assert is_valid_collocation(["a", "b", "c", "d"], None) is False
    assert is_valid_collocation(["a", None, "c", "d"], 0) is False
