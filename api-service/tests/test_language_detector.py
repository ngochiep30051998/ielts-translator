"""Bản port của `LanguageDetectorTest`.

Đoán sai chiều là dùng sai prompt VÀ ghi cache dưới khoá sai — người dùng thấy một bản dịch
vô nghĩa, còn hệ thống thì không thấy gì bất thường.
"""

from __future__ import annotations

import pytest

from app.translation.detector import detect
from app.translation.models import Direction


@pytest.mark.parametrize(
    ("text", "mong_doi"),
    [
        # Tiếng Việt có dấu → nhận ra ngay bằng ký tự.
        ("Chính phủ nên đầu tư nhiều hơn vào năng lượng tái tạo", Direction.VI_EN),
        ("tái tạo", Direction.VI_EN),
        ("Tôi thích renewable energy", Direction.VI_EN),
        # Tiếng Việt không dấu → nhận ra bằng stopword.
        ("toi khong biet cai nay la cua ai", Direction.VI_EN),
        ("chung ta can phai lam viec nay cho tot", Direction.VI_EN),
        # Tiếng Anh.
        ("renewable", Direction.EN_VI),
        ("The government should allocate more funding", Direction.EN_VI),
        ("this is a test of the system", Direction.EN_VI),
        # Không quyết được → mặc định EN_VI.
        ("12345", Direction.EN_VI),
        ("  ", Direction.EN_VI),
        # Tiếng Việt TOÀN CHỮ HOA — regex phải bỏ qua hoa thường theo Unicode.
        ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", Direction.VI_EN),
        ("ĐIỀU NÀY RẤT QUAN TRỌNG", Direction.VI_EN),
        ("Á", Direction.VI_EN),
    ],
)
def test_doan_chieu_dich(text: str, mong_doi: Direction) -> None:
    assert detect(text) == mong_doi


def test_text_rong_mac_dinh_en_vi() -> None:
    assert detect("") is Direction.EN_VI


def test_text_none_mac_dinh_en_vi() -> None:
    """Không được nổ lỗi: `detect` nằm trên đường nóng của mọi lượt dịch."""
    assert detect(None) is Direction.EN_VI


def test_hoa_thi_ve_en_vi() -> None:
    """Java so `viHits > enHits`, KHÔNG phải `>=`.

    Đổi thành `>=` làm mọi chuỗi không có stopword nào (cả hai đếm bằng 0) nhảy sang VI_EN —
    tức là mọi từ tiếng Anh đơn lẻ, đúng ca dùng phổ biến nhất của cả hệ thống.
    """
    # "and" (chỉ EN) và "cua" (chỉ VI): mỗi bên một điểm → hoà → EN_VI.
    assert detect("and cua") is Direction.EN_VI
    # Không token nào khớp: 0 = 0 → hoà → EN_VI.
    assert detect("xyz qwerty") is Direction.EN_VI


def test_stopword_nam_trong_ca_hai_danh_sach_duoc_dem_cho_ca_hai() -> None:
    """`the` có mặt ở CẢ HAI danh sách — "the" tiếng Anh và "thế" tiếng Việt không dấu.

    Đây là hành vi của bản Java chứ không phải sơ suất khi port, nên viết ra để lần sau ai
    đó thấy nó "trùng" thì biết là đã có người nhìn: mỗi lần xuất hiện cộng một điểm cho cả
    hai bên, nên `the` một mình không nghiêng cán cân. Bỏ nó khỏi danh sách tiếng Việt sẽ
    làm mọi câu Việt không dấu có chữ "the" tụt một điểm.
    """
    from app.translation.detector import _EN_STOPWORDS, _VI_STOPWORDS

    assert "the" in _EN_STOPWORDS
    assert "the" in _VI_STOPWORDS
    # Một mình "the": 1 = 1 → hoà → EN_VI.
    assert detect("the") is Direction.EN_VI
    # Thêm một stopword Việt thuần là nghiêng hẳn.
    assert detect("the cua") is Direction.VI_EN


def test_chu_hoa_khong_lam_hong_viec_dem_stopword() -> None:
    """Token được hạ chữ thường TRƯỚC khi tách bằng `[^a-z]+`.

    Tách trước rồi mới hạ chữ thường thì `KHONG` bị `[^a-z]+` xé thành chuỗi rỗng và không
    stopword nào khớp — mọi câu tiếng Việt không dấu viết hoa sẽ bị nhận là tiếng Anh.
    """
    assert detect("TOI KHONG BIET CAI NAY LA CUA AI") is Direction.VI_EN


def test_dau_cau_khong_dinh_vao_token() -> None:
    assert detect("toi khong biet, cai nay la cua ai!") is Direction.VI_EN
