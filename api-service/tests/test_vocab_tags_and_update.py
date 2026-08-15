"""Hợp đồng HTTP của hai endpoint mới — `GET /api/vocab/tags` và `PATCH /api/vocab/{id}` —
cộng bộ lọc `untagged` của `GET /api/vocab` và ba field SRS gắn thêm vào `VocabEntryDto`.

Khoá JSON viết camelCase, cố ý: đó là thứ `packages/core/src/types.ts` thật sự đọc (ràng
buộc #3). Test bằng khoá snake_case vẫn xanh nhờ `populate_by_name` mà để lọt một backend
không nói chuyện được với client.

Không mock Gemini ở đây, giống `test_vocab_router.py`: lượt sinh mồi nhử chạy nền sau khi
lưu từ đâm vào `GEMINI_BASE_URL` trỏ cổng chết và bị nuốt lặng — đúng hành vi cần giữ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import NguoiDungTest


def _luu(client: Any, owner: NguoiDungTest, term: str, nghia: str, tags: list[str]) -> int:
    resp = client.post(
        "/api/vocab",
        headers=owner.headers,
        json={"term": term, "lang": "en", "pos": "n", "meaningVi": nghia, "tags": tags},
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["id"])


def _luu_khong_the(db: Session, user_id: int, term: str, nghia: str) -> int:
    """Một từ KHÔNG có `srs_card`.

    Chèn thẳng bằng SQL chứ không qua `POST /api/vocab`: đường HTTP luôn tạo kèm thẻ ôn
    (trừ `pos = 'phrase'`), nên không dựng được trạng thái "từ chưa có thẻ" mà vẫn giữ
    được từ ở dạng bình thường.
    """
    entry_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lang, pos, meaning_vi, tags, user_id) "
                "VALUES (:t, 'en', 'n', :m, '{}', :u) RETURNING id"
            ),
            {"t": term, "m": nghia, "u": user_id},
        ).scalar_one()
    )
    db.commit()
    return entry_id


# ── GET /api/vocab/tags ───────────────────────────────────────────────────────


def test_tags_so_tu_rong_tra_object_rong_chu_khong_404(
    client: Any, owner: NguoiDungTest
) -> None:
    """Sổ từ rỗng là trạng thái BÌNH THƯỜNG của người dùng mới, không phải lỗi."""
    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"total": 0, "untagged": 0, "tags": []}


def test_tags_dem_so_tu_va_sap_xep_count_giam_dan_roi_tag_tang_dan(
    client: Any, owner: NguoiDungTest
) -> None:
    """Thứ tự phải ỔN ĐỊNH: hàng chip trong tab Sổ từ nhảy loạn giữa hai lần tải là lỗi
    người dùng thấy ngay, còn `ORDER BY` thiếu tiêu chí phụ thì không có gì đỏ.

    Hai tag `alpha`/`beta` cùng count để chốt tiêu chí phụ; cả hai viết thường ASCII nên
    kết quả không phụ thuộc collation của Postgres đang chạy test.
    """
    _luu(client, owner, "renewable", "tái tạo", ["Giáo dục", "Môi trường"])
    _luu(client, owner, "mitigate", "giảm nhẹ", ["Giáo dục", "Môi trường"])
    _luu(client, owner, "curriculum", "chương trình học", ["Giáo dục"])
    _luu(client, owner, "alphabet", "bảng chữ cái", ["alpha"])
    _luu(client, owner, "betamax", "băng từ", ["beta"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == [
        {"tag": "Giáo dục", "count": 3},
        {"tag": "Môi trường", "count": 2},
        {"tag": "alpha", "count": 1},
        {"tag": "beta", "count": 1},
    ]


def test_tags_bo_qua_tu_khong_gan_the_nao(client: Any, owner: NguoiDungTest) -> None:
    _luu(client, owner, "renewable", "tái tạo", [])
    _luu(client, owner, "mitigate", "giảm nhẹ", ["Môi trường"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [{"tag": "Môi trường", "count": 1}]


def test_tags_mot_tu_gan_trung_mot_the_chi_dem_mot_lan(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`count` là SỐ TỪ, không phải số dòng sau khi bung mảng.

    `POST /api/vocab` không lọc trùng trong mảng `tags` client gửi lên, nên một hàng
    `{'dup','dup'}` là dựng được thật. Đếm dòng thì chip hiện "2 từ" trong khi bấm vào chỉ
    ra một — sai ở đúng chỗ người dùng đối chiếu được.
    """
    db.execute(
        text(
            "INSERT INTO vocab_entry (term, lang, pos, meaning_vi, tags, user_id) "
            "VALUES ('renewable', 'en', 'n', 'tái tạo', ARRAY['dup','dup'], :u)"
        ),
        {"u": owner.id},
    )
    db.commit()

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [{"tag": "dup", "count": 1}]


def test_tags_total_la_tong_KHONG_loc_con_untagged_dem_the_rong(
    client: Any, owner: NguoiDungTest
) -> None:
    """Ba con số của hàng chip đến từ MỘT lượt gọi.

    `total` là chip "Tất cả" — tổng bất biến của cả sổ, không phải số từ khớp bộ lọc đang
    bật. Lấy nó từ `GET /api/vocab` (request có mang `tag`) là lý do chip "Tất cả" từng đọc
    thành đúng con số của chủ đề vừa bấm.
    """
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _luu(client, owner, "mitigate", "giảm nhẹ", ["Môi trường", "Giáo dục"])
    _luu(client, owner, "curriculum", "chương trình học", [])
    _luu(client, owner, "alphabet", "bảng chữ cái", [])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "total": 4,
        "untagged": 2,
        "tags": [{"tag": "Môi trường", "count": 2}, {"tag": "Giáo dục", "count": 1}],
    }


def test_tags_untagged_bang_0_khi_tu_nao_cung_co_the(
    client: Any, owner: NguoiDungTest
) -> None:
    """Chip "Chưa gắn" chỉ được hiện khi con số này > 0 — chip đếm 0 là một ô bấm vào ra
    danh sách rỗng."""
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["total"] == 1
    assert resp.json()["untagged"] == 0


# ── GET /api/vocab?untagged=true — chip "Chưa gắn" ────────────────────────────


def test_untagged_chi_tra_tu_chua_gan_the_nao(client: Any, owner: NguoiDungTest) -> None:
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _luu(client, owner, "curriculum", "chương trình học", [])
    _luu(client, owner, "alphabet", "bảng chữ cái", [])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true"}
    ).json()

    assert sorted(tu["term"] for tu in body["content"]) == ["alphabet", "curriculum"]
    assert body["totalElements"] == 2


def test_untagged_mac_dinh_false_van_tra_ca_so_tu(client: Any, owner: NguoiDungTest) -> None:
    """Tham số MỚI không được đổi hành vi của request cũ — extension bản cũ không gửi nó."""
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _luu(client, owner, "curriculum", "chương trình học", [])

    body = client.get("/api/vocab", headers=owner.headers).json()

    assert body["totalElements"] == 2


def test_untagged_total_elements_dung_khi_trang_nho_hon_ket_qua(
    client: Any, owner: NguoiDungTest
) -> None:
    """Điều kiện lọc phải nằm trong `_search_conditions` — dùng chung cho câu LẤY và câu ĐẾM.

    Chỉ nhét vào câu lấy dữ liệu thì `content` đúng còn `totalElements` đếm cả sổ: side panel
    vẽ ra số trang không tồn tại, bấm sang là trang trắng.
    """
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _luu(client, owner, "curriculum", "chương trình học", [])
    _luu(client, owner, "alphabet", "bảng chữ cái", [])
    _luu(client, owner, "betamax", "băng từ", [])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true", "size": 1}
    ).json()

    assert body["totalElements"] == 3
    assert body["totalPages"] == 3
    assert len(body["content"]) == 1


def test_untagged_ket_hop_q_van_loc_ca_hai(client: Any, owner: NguoiDungTest) -> None:
    """`untagged` KHÔNG đi cùng `tag`, nhưng đi cùng ô tìm kiếm thì bình thường."""
    _luu(client, owner, "renewable", "tái tạo", [])
    _luu(client, owner, "curriculum", "chương trình học", [])
    _luu(client, owner, "renewal", "sự gia hạn", ["Môi trường"])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true", "q": "renew"}
    ).json()

    assert [tu["term"] for tu in body["content"]] == ["renewable"]
    assert body["totalElements"] == 1


def test_untagged_kem_tag_tra_400_vi_hai_dieu_kien_mau_thuan(
    client: Any, owner: NguoiDungTest
) -> None:
    """Chọn ngầm một trong hai là tệ hơn từ chối: người dùng thấy một danh sách không giải
    thích được, còn backend thì không nói ra nó đã bỏ điều kiện nào."""
    _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.get(
        "/api/vocab",
        headers=owner.headers,
        params={"untagged": "true", "tag": "Môi trường"},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["retryable"] is False
    assert "untagged" in resp.json()["message"]


# ── PATCH /api/vocab/{id} ─────────────────────────────────────────────────────


def test_patch_doi_nghia_va_giu_nguyen_tag_khi_tag_vang_mat(
    client: Any, owner: NguoiDungTest
) -> None:
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "có thể tái tạo"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "có thể tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_thay_the_toan_bo_tag_chu_khong_gop_them(
    client: Any, owner: NguoiDungTest
) -> None:
    """Ngữ nghĩa NGƯỢC với `POST /api/vocab` (`_merge_tags` gộp thêm).

    Trộn hai ngữ nghĩa vào một endpoint thì không còn cách nào gỡ một thẻ đã gắn nhầm.
    """
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường", "gắn nhầm"])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"tags": ["Giáo dục"]}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == ["Giáo dục"]
    # Và nghĩa KHÔNG bị đụng tới vì `meaningVi` vắng mặt trong body.
    assert resp.json()["meaningVi"] == "tái tạo"


def test_patch_mang_tag_rong_xoa_sach_the_khac_han_voi_vang_mat(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Đây là ca mà `None` làm "không đổi" sẽ phá: `[]` là một YÊU CẦU thật (gỡ hết thẻ),
    không phải "client không gửi gì"."""
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    vang_mat = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "tái tạo"}
    )
    assert vang_mat.json()["tags"] == ["Môi trường"]

    rong = client.patch(f"/api/vocab/{entry_id}", headers=owner.headers, json={"tags": []})

    assert rong.status_code == 200, rong.text
    assert rong.json()["tags"] == []
    db.expire_all()
    con_lai = db.execute(
        text("SELECT tags FROM vocab_entry WHERE id = :i"), {"i": entry_id}
    ).scalar_one()
    assert con_lai == []


def test_patch_null_la_khong_doi(client: Any, owner: NguoiDungTest) -> None:
    """Hợp đồng message của client (`UpdateVocabRequest`) dùng `null` cho "không đổi field
    này", nên body gửi lên có thể mang khoá với giá trị `null` — phải tương đương vắng mặt."""
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(
        f"/api/vocab/{entry_id}",
        headers=owner.headers,
        json={"meaningVi": None, "tags": None},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_body_rong_khong_doi_gi(client: Any, owner: NguoiDungTest) -> None:
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(f"/api/vocab/{entry_id}", headers=owner.headers, json={})

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_nghia_toan_khoang_trang_bi_tu_choi_va_khong_ghi_de(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Lỗi validate của cả dự án trả 400 kèm `{code, message, retryable}` — xem
    `main.py: handle_validation`. Kiểm cả dữ liệu: từ chối mà vẫn ghi là ca im lặng nhất."""
    entry_id = _luu(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "   "}
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["retryable"] is False
    db.expire_all()
    assert (
        db.execute(
            text("SELECT meaning_vi FROM vocab_entry WHERE id = :i"), {"i": entry_id}
        ).scalar_one()
        == "tái tạo"
    )


def test_patch_id_khong_ton_tai_tra_404_not_found(client: Any, owner: NguoiDungTest) -> None:
    resp = client.patch("/api/vocab/999999", headers=owner.headers, json={"meaningVi": "x"})

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False


def test_patch_chua_dang_nhap_tra_401(client: Any, owner: NguoiDungTest) -> None:
    entry_id = _luu(client, owner, "renewable", "tái tạo", [])

    resp = client.patch(f"/api/vocab/{entry_id}", json={"meaningVi": "x"})

    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_cors_cho_phep_method_patch(client: Any) -> None:
    """`allow_methods` của CORSMiddleware liệt kê TAY. Thiếu PATCH ở đó thì extension vấp
    preflight và request chết trước khi chạm backend — không log, không test router nào đỏ."""
    resp = client.options(
        "/api/vocab/1",
        headers={
            "Origin": "chrome-extension://testextensionid",
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert resp.status_code == 200, resp.text
    assert "PATCH" in resp.headers["access-control-allow-methods"]


# ── ba field SRS trong VocabEntryDto ──────────────────────────────────────────


def test_danh_sach_kem_trang_thai_the_on(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    entry_id = _luu(client, owner, "renewable", "tái tạo", [])
    db.execute(
        text(
            "UPDATE srs_card SET state = 'REVIEW', repetitions = 4, "
            "due_date = CURRENT_DATE + 6 WHERE vocab_entry_id = :v"
        ),
        {"v": entry_id},
    )
    db.commit()
    db.expire_all()

    tu = client.get("/api/vocab", headers=owner.headers).json()["content"][0]

    assert tu["srsState"] == "REVIEW"
    assert tu["srsRepetitions"] == 4
    assert tu["srsDueDate"] == (date.today() + timedelta(days=6)).isoformat()


def test_ba_field_srs_cung_null_khi_tu_chua_co_the(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """CẢ BA cùng null nghĩa là "chưa có thẻ ôn" — trạng thái thật, không phải "chưa tải
    xong". UI vẽ thanh thành thạo phải phân biệt được hai thứ đó."""
    _luu_khong_the(db, owner.id, "renewable", "tái tạo")

    tu = client.get("/api/vocab", headers=owner.headers).json()["content"][0]

    assert tu["srsState"] is None
    assert tu["srsDueDate"] is None
    assert tu["srsRepetitions"] is None


def test_doc_mot_tu_cung_kem_trang_thai_the_on(client: Any, owner: NguoiDungTest) -> None:
    entry_id = _luu(client, owner, "renewable", "tái tạo", [])

    tu = client.get(f"/api/vocab/{entry_id}", headers=owner.headers).json()

    assert tu["srsState"] == "NEW"
    assert tu["srsRepetitions"] == 0
    assert tu["srsDueDate"] == date.today().isoformat()


def test_patch_tra_ve_dto_day_du_kem_field_srs(client: Any, owner: NguoiDungTest) -> None:
    """Response của PATCH là `VocabEntryDto` nguyên vẹn — client thay thẳng dòng trong danh
    sách bằng nó, nên thiếu field SRS là thanh thành thạo biến mất sau khi bấm Lưu."""
    entry_id = _luu(client, owner, "renewable", "tái tạo", [])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "tái sinh"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["srsState"] == "NEW"
    assert resp.json()["srsRepetitions"] == 0
    assert resp.json()["srsDueDate"] == date.today().isoformat()


def test_join_the_on_khong_lam_lech_danh_sach_lan_total_elements(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Từ CHƯA có thẻ vẫn phải nằm trong danh sách.

    Câu đếm dùng chung `_search_conditions` và KHÔNG join, nên đổi nhầm sang INNER JOIN cho
    câu lấy dữ liệu sẽ ra `totalElements = 3` mà `content` chỉ có 2 — phân trang lệch mà
    không có gì đỏ.
    """
    _luu(client, owner, "renewable", "tái tạo", [])
    _luu(client, owner, "mitigate", "giảm nhẹ", [])
    _luu_khong_the(db, owner.id, "curriculum", "chương trình học")

    body = client.get("/api/vocab", headers=owner.headers).json()

    assert body["totalElements"] == 3
    assert body["numberOfElements"] == 3
    assert len(body["content"]) == 3
