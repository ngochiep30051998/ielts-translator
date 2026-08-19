"""Bản port của `VocabControllerIT` — hợp đồng HTTP của sổ từ.

`client` (TestClient) thay `MockMvc`; `_clean_database` của `conftest.py` thay
`@BeforeEach repository.deleteAll()`.

Không mock Gemini ở đây, ĐÚNG như bản Java: `VocabControllerIT` cũng không `@MockitoBean`
gì cả, nên lượt sinh mồi nhử chạy nền sau khi lưu từ sẽ đâm vào `GEMINI_BASE_URL` trỏ cổng
chết (127.0.0.1:1), bị từ chối kết nối và nuốt lặng trong log. Đó chính là hành vi cần
kiểm: lưu từ KHÔNG được phụ thuộc vào việc Gemini còn sống.

Khoá JSON trong file này cố ý viết camelCase — đó là thứ extension thật sự gửi và đọc
(`shared/types.ts`, ràng buộc #3). Test bằng khoá snake_case sẽ xanh nhờ `populate_by_name`
mà vẫn để lọt một backend không nói chuyện được với extension.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import UserFixture

#: Đúng body của `VocabControllerIT.BODY`.
BODY: dict[str, Any] = {
    "term": "renewable",
    "lemma": "renewable",
    "lang": "en",
    "pos": "adj",
    "ipa": "/rɪˈnjuːəbl/",
    "meaningVi": "tái tạo",
    "definitionEn": "able to be renewed",
    "cefr": "B2",
    "bandLevel": "6.5",
    "tags": ["environment"],
    "sourceUrl": "https://example.com",
    "sourceSentence": "We need renewable energy.",
    "collocations": ["renewable energy"],
    "examples": [],
}


# ── lưu ───────────────────────────────────────────────────────────────────────


def test_saving_returns_id_and_reports_not_already_exists(
    client: Any, owner: UserFixture
) -> None:
    resp = client.post("/api/vocab", headers=owner.headers, json=BODY)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["id"], int)
    assert body["alreadyExists"] is False


def test_saving_second_time_reports_already_exists_instead_of_erroring(
    client: Any, owner: UserFixture
) -> None:
    """Lưu trùng là chuyện BÌNH THƯỜNG: người dùng bôi lại đúng từ đó ở một trang khác.

    Ràng buộc UNIQUE `(user_id, term, pos)` phải được service đón trước, nếu không database
    từ chối và người dùng nhận 500 cho một thao tác chẳng có gì sai.
    """
    first_save = client.post("/api/vocab", headers=owner.headers, json=BODY)
    assert first_save.status_code == 200, first_save.text

    second_save = client.post("/api/vocab", headers=owner.headers, json=BODY)

    assert second_save.status_code == 200, second_save.text
    assert second_save.json()["alreadyExists"] is True
    assert second_save.json()["id"] == first_save.json()["id"]


# ── tìm kiếm ──────────────────────────────────────────────────────────────────


def test_search_returns_page_of_results(client: Any, owner: UserFixture) -> None:
    client.post("/api/vocab", headers=owner.headers, json=BODY)

    resp = client.get("/api/vocab", headers=owner.headers, params={"q": "renew"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"][0]["term"] == "renewable"
    assert body["totalElements"] == 1
    # Tên field phát ra phải là camelCase — `shared/types.ts` đọc thẳng chuỗi này.
    assert body["content"][0]["meaningVi"] == "tái tạo"
    assert "meaning_vi" not in body["content"][0]


# ── đọc một từ · xoá ──────────────────────────────────────────────────────────


def test_delete_returns_204_then_get_returns_404(client: Any, owner: UserFixture) -> None:
    """Và lỗi 404 phải đúng hình dạng `{code, message, retryable}` (ràng buộc #4): UI phân
    biệt lỗi vĩnh viễn với lỗi thử lại được nhờ chính hai field đó."""
    entry_id = client.post("/api/vocab", headers=owner.headers, json=BODY).json()["id"]

    delete_resp = client.delete(f"/api/vocab/{entry_id}", headers=owner.headers)
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    reread = client.get(f"/api/vocab/{entry_id}", headers=owner.headers)
    assert reread.status_code == 404
    assert reread.json()["code"] == "NOT_FOUND"
    assert reread.json()["retryable"] is False


# ── export CSV — đường thoát dữ liệu của người dùng ───────────────────────────


def test_export_csv_has_header_row_and_download_headers(
    client: Any, owner: UserFixture
) -> None:
    """Content-Disposition và Content-Type là thứ quyết định trình duyệt TẢI file hay hiện
    chữ ra tab — sai một trong hai là người dùng không lấy được sổ từ của mình."""
    client.post("/api/vocab", headers=owner.headers, json=BODY)

    resp = client.get("/api/vocab/export.csv", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-disposition"] == 'attachment; filename="vocabulary.csv"'
    assert resp.headers["content-type"] == "text/csv; charset=UTF-8"
    assert resp.text.startswith("term,pos,ipa")
    assert "renewable" in resp.text


def test_export_csv_empty_vocab_still_has_header_row(
    client: Any, owner: UserFixture
) -> None:
    """Sổ từ rỗng vẫn ra một file CSV hợp lệ, không phải body rỗng."""
    resp = client.get("/api/vocab/export.csv", headers=owner.headers)

    assert resp.status_code == 200
    assert resp.text == (
        "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at"
    )


def test_export_csv_preserves_data_with_commas_quotes_and_newlines(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Bằng chứng đầu-cuối cho đường thoát dữ liệu: từ POST tới file tải về, một nghĩa chứa
    CẢ dấu phẩy, ngoặc kép lẫn xuống dòng phải quay về NGUYÊN VẸN qua trình đọc CSV chuẩn.

    Escape sai ở đây không làm gì đỏ trên màn hình: file vẫn tải được, chỉ là các cột lệch
    ô và sổ từ nhập vào Anki thành rác — phát hiện được thì đã muộn.
    """
    meaning = 'tái tạo, "phục hồi"\ndòng hai'
    body = {**BODY, "meaningVi": meaning, "tags": ["environment", "writing"]}
    assert client.post("/api/vocab", headers=owner.headers, json=body).status_code == 200

    resp = client.get("/api/vocab/export.csv", headers=owner.headers)
    assert resp.status_code == 200

    rows = list(csv.reader(io.StringIO(resp.text)))
    assert len(rows) == 2, f"Phải đúng 1 hàng dữ liệu, đọc được {len(rows) - 1}"

    header_row = rows[0]
    data_row = dict(zip(header_row, rows[1], strict=True))
    assert data_row["term"] == "renewable"
    assert data_row["meaning_vi"] == meaning
    assert data_row["tags"] == "environment;writing"
    assert data_row["pos"] == "adj"
    assert data_row["ipa"] == "/rɪˈnjuːəbl/"
    assert data_row["source_url"] == "https://example.com"

    # Và mốc thời gian trong file khớp đúng hàng trong bảng — không phải giờ máy chủ, không
    # phải một chuỗi được định dạng lại ở đường khác.
    #
    # So sau khi ĐỔI VỀ UTC. Cột là TIMESTAMPTZ nên driver trả về theo múi giờ phiên
    # (Asia/Ho_Chi_Minh trong container), còn CSV in theo `Instant.toString()` của Java —
    # luôn UTC, luôn hậu tố `Z`. Quên đổi múi giờ ở đây thì test đỏ vì lệch đúng 7 tiếng
    # trong khi file xuất ra hoàn toàn đúng.
    created_at = db.execute(text("SELECT created_at FROM vocab_entry")).scalar_one()
    assert data_row["created_at"].startswith(
        created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    )
    assert data_row["created_at"].endswith("Z")
