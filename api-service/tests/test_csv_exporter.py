"""Bản port của `CsvExporterTest`.

CSV là đường thoát dữ liệu duy nhất của người dùng: nếu một ngày họ bỏ công cụ này, file
CSV là thứ họ mang đi. Nên header, THỨ TỰ CỘT, cách escape và cách nối tag phải giữ y hệt
bản Java — một file export hôm qua và một file export hôm nay phải nhập được vào cùng một
chỗ (Anki, Excel, Google Sheets).

Đây là test THUẦN, không chạm database: `to_csv` chỉ nhận entity và trả chuỗi.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta, timezone

from app.vocabulary.csv_export import HEADER, to_csv
from app.vocabulary.models import VocabEntry

#: Mốc thời gian trong `CsvExporterTest` bên Java: `Instant.parse("2026-08-03T10:15:30Z")`.
MOC = datetime(2026, 8, 3, 10, 15, 30, tzinfo=UTC)


def _entry(term: str, nghia: str, tags: list[str]) -> VocabEntry:
    """Đúng entity mà `CsvExporterTest.entry(...)` dựng — không lưu database, chỉ để xuất."""
    return VocabEntry(
        term=term,
        pos="adj",
        ipa="/test/",
        meaning_vi=nghia,
        definition_en="a definition",
        cefr="B2",
        band_level="6.5",
        tags=list(tags),
        source_url="https://example.com",
        created_at=MOC,
    )


def test_luon_ghi_hang_tieu_de() -> None:
    """Sổ từ RỖNG vẫn phải ra đúng một hàng tiêu đề, không phải chuỗi rỗng.

    Một file chỉ có header vẫn nhập được vào Excel/Anki và vẫn nói cho người dùng biết
    file hợp lệ; một file rỗng thì không phân biệt được với export hỏng.
    """
    csv_text = to_csv([])

    assert csv_text.splitlines()[0] == HEADER
    assert csv_text == (
        "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at"
    )


def test_moi_tu_mot_hang() -> None:
    """Header + 2 dòng = 3 dòng."""
    csv_text = to_csv(
        [
            _entry("renewable", "tái tạo", ["environment"]),
            _entry("mitigate", "giảm nhẹ", []),
        ]
    )

    assert len(csv_text.splitlines()) == 3


def test_boc_ngoac_kep_khi_field_chua_dau_phay() -> None:
    """Không bọc thì dấu phẩy trong nghĩa tự tách thành một cột mới và MỌI cột phía sau
    lệch đi một ô — hỏng im lặng, chỉ phát hiện khi người dùng mở file."""
    csv_text = to_csv([_entry("renewable", "tái tạo, phục hồi", [])])

    assert '"tái tạo, phục hồi"' in csv_text


def test_nhan_doi_dau_ngoac_kep_ben_trong() -> None:
    """RFC 4180: dấu `"` bên trong field được escape bằng cách viết hai lần, và cả field
    phải được bọc."""
    csv_text = to_csv([_entry("renewable", 'nghĩa "đặc biệt"', [])])

    assert '"nghĩa ""đặc biệt"""' in csv_text


def test_boc_ngoac_kep_khi_field_chua_xuong_dong() -> None:
    """Xuống dòng bên trong field là hợp lệ nếu field được bọc — không bọc thì một từ biến
    thành hai hàng dữ liệu rác."""
    csv_text = to_csv([_entry("renewable", "dòng một\ndòng hai", [])])

    assert '"dòng một\ndòng hai"' in csv_text


def test_noi_tag_bang_dau_cham_phay() -> None:
    """Dấu `;` chứ không phải `,` — nối bằng dấu phẩy thì tag tự tách thành cột."""
    csv_text = to_csv([_entry("renewable", "tái tạo", ["a", "b"])])

    assert "a;b" in csv_text


# ── phần thêm: hợp đồng cột, không có trong bản Java nhưng CSV là đường thoát dữ liệu ──


def test_thu_tu_cot_khop_tung_ky_tu() -> None:
    """Chốt cả hàng dữ liệu, không chỉ vài mẩu.

    Bản Java chỉ kiểm từng mẩu (`contains`), nên hai cột bị hoán vị — ví dụ `cefr` và
    `band_level`, cả hai đều là chuỗi ngắn — vẫn qua được mọi khẳng định của nó. File CSV
    thì hỏng thật với người dùng đã có script nhập liệu.
    """
    csv_text = to_csv([_entry("renewable", "tái tạo", ["environment", "writing"])])

    assert csv_text.splitlines()[1] == (
        "renewable,adj,/test/,tái tạo,a definition,B2,6.5,"
        "environment;writing,https://example.com,2026-08-03T10:15:30Z"
    )


def test_field_rong_thanh_o_trong_khong_phai_chu_None() -> None:
    """Cột không có giá trị phải là ô trống. In `None` ra file là đưa chuỗi "None" vào sổ
    từ của người dùng."""
    entry = VocabEntry(term="renewable", pos="", meaning_vi="tái tạo", tags=[])

    assert to_csv([entry]).splitlines()[1] == "renewable,,,tái tạo,,,,,,"


def test_created_at_in_dung_dinh_dang_instant_cua_java() -> None:
    """`Instant.toString()` in 0, 3 hoặc 6 chữ số phần lẻ giây và kết thúc bằng `Z`.

    `isoformat()` của Python thì luôn in 0 hoặc 6 chữ số và dùng hậu tố `+00:00`. Không san
    khác biệt này thì cùng một hàng dữ liệu xuất ra hai chuỗi khác nhau tuỳ backend nào
    đang chạy — đúng thứ làm hỏng script nhập liệu mà không ai báo lỗi.
    """

    def cot_thoi_gian(moment: datetime) -> str:
        entry = _entry("x", "y", [])
        entry.created_at = moment
        return to_csv([entry]).splitlines()[1].split(",")[-1]

    assert cot_thoi_gian(MOC) == "2026-08-03T10:15:30Z"
    assert cot_thoi_gian(MOC.replace(microsecond=500_000)) == "2026-08-03T10:15:30.500Z"
    assert cot_thoi_gian(MOC.replace(microsecond=123_456)) == "2026-08-03T10:15:30.123456Z"
    # Múi giờ khác UTC phải được quy về UTC, không in nguyên offset của máy chủ.
    gio_vn = timezone(timedelta(hours=7))
    assert cot_thoi_gian(MOC.astimezone(gio_vn)) == "2026-08-03T10:15:30Z"


def test_file_xuat_ra_doc_lai_duoc_bang_trinh_doc_csv_chuan() -> None:
    """Bằng chứng cuối cùng: một hàng chứa CẢ dấu phẩy, ngoặc kép lẫn xuống dòng phải quay
    về nguyên vẹn qua một trình đọc CSV chuẩn (RFC 4180)."""
    nghia = 'tái tạo, "phục hồi"\nnghĩa hai'
    csv_text = to_csv([_entry("renewable", nghia, ["a", "b"])])

    hang = list(csv.reader(io.StringIO(csv_text)))

    assert hang[0] == HEADER.split(",")
    assert hang[1] == [
        "renewable",
        "adj",
        "/test/",
        nghia,
        "a definition",
        "B2",
        "6.5",
        "a;b",
        "https://example.com",
        "2026-08-03T10:15:30Z",
    ]
