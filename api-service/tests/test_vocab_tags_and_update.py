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

from app.srs.models import MASTERED_REPETITIONS
from tests.conftest import UserFixture


def _save(client: Any, owner: UserFixture, term: str, meaning: str, tags: list[str]) -> int:
    resp = client.post(
        "/api/vocab",
        headers=owner.headers,
        json={"term": term, "lang": "en", "pos": "n", "meaningVi": meaning, "tags": tags},
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["id"])


def _save_without_card(db: Session, user_id: int, term: str, meaning: str) -> int:
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
            {"t": term, "m": meaning, "u": user_id},
        ).scalar_one()
    )
    db.commit()
    return entry_id


def _set_repetitions(db: Session, entry_id: int, repetitions: int) -> None:
    """Đặt thẳng `repetitions` của thẻ ôn gắn với từ.

    Không đi qua `POST /api/srs/review`: cần đúng MỘT con số, còn đường thật phải chạy đủ
    `repetitions` lượt ôn và mỗi lượt lại đẩy `due_date` ra xa — dài dòng mà không kiểm thêm gì.
    """
    db.execute(
        text(
            "UPDATE srs_card SET state = 'REVIEW', repetitions = :r WHERE vocab_entry_id = :v"
        ),
        {"r": repetitions, "v": entry_id},
    )
    db.commit()


# ── GET /api/vocab/tags ───────────────────────────────────────────────────────


def test_tags_empty_vocab_book_returns_empty_object_not_404(
    client: Any, owner: UserFixture
) -> None:
    """Sổ từ rỗng là trạng thái BÌNH THƯỜNG của người dùng mới, không phải lỗi."""
    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"total": 0, "untagged": 0, "tags": []}


def test_tags_counts_words_and_sorts_by_count_desc_then_tag_asc(
    client: Any, owner: UserFixture
) -> None:
    """Thứ tự phải ỔN ĐỊNH: hàng chip trong tab Sổ từ nhảy loạn giữa hai lần tải là lỗi
    người dùng thấy ngay, còn `ORDER BY` thiếu tiêu chí phụ thì không có gì đỏ.

    Hai tag `alpha`/`beta` cùng count để chốt tiêu chí phụ; cả hai viết thường ASCII nên
    kết quả không phụ thuộc collation của Postgres đang chạy test.
    """
    _save(client, owner, "renewable", "tái tạo", ["Giáo dục", "Môi trường"])
    _save(client, owner, "mitigate", "giảm nhẹ", ["Giáo dục", "Môi trường"])
    _save(client, owner, "curriculum", "chương trình học", ["Giáo dục"])
    _save(client, owner, "alphabet", "bảng chữ cái", ["alpha"])
    _save(client, owner, "betamax", "băng từ", ["beta"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == [
        {"tag": "Giáo dục", "count": 3, "mastered": 0},
        {"tag": "Môi trường", "count": 2, "mastered": 0},
        {"tag": "alpha", "count": 1, "mastered": 0},
        {"tag": "beta", "count": 1, "mastered": 0},
    ]


def test_tags_skips_words_with_no_tags(client: Any, owner: UserFixture) -> None:
    _save(client, owner, "renewable", "tái tạo", [])
    _save(client, owner, "mitigate", "giảm nhẹ", ["Môi trường"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [{"tag": "Môi trường", "count": 1, "mastered": 0}]


def test_tags_word_with_duplicate_tag_is_counted_once(
    client: Any, db: Session, owner: UserFixture
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

    assert resp.json()["tags"] == [{"tag": "dup", "count": 1, "mastered": 0}]


def test_tags_total_is_unfiltered_sum_while_untagged_counts_empty_tags(
    client: Any, owner: UserFixture
) -> None:
    """Ba con số của hàng chip đến từ MỘT lượt gọi.

    `total` là chip "Tất cả" — tổng bất biến của cả sổ, không phải số từ khớp bộ lọc đang
    bật. Lấy nó từ `GET /api/vocab` (request có mang `tag`) là lý do chip "Tất cả" từng đọc
    thành đúng con số của chủ đề vừa bấm.
    """
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _save(client, owner, "mitigate", "giảm nhẹ", ["Môi trường", "Giáo dục"])
    _save(client, owner, "curriculum", "chương trình học", [])
    _save(client, owner, "alphabet", "bảng chữ cái", [])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "total": 4,
        "untagged": 2,
        "tags": [
            {"tag": "Môi trường", "count": 2, "mastered": 0},
            {"tag": "Giáo dục", "count": 1, "mastered": 0},
        ],
    }


def test_tags_untagged_is_zero_when_every_word_has_a_tag(
    client: Any, owner: UserFixture
) -> None:
    """Chip "Chưa gắn" chỉ được hiện khi con số này > 0 — chip đếm 0 là một ô bấm vào ra
    danh sách rỗng."""
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["total"] == 1
    assert resp.json()["untagged"] == 0


# ── GET /api/vocab/tags — `mastered` (thanh thành thạo của chip chủ đề) ───────


def test_tags_mastered_counts_words_at_threshold_and_stops_just_below_it(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """`mastered` = số từ mang tag đó có thẻ ôn `repetitions >= MASTERED_REPETITIONS`.

    Ngưỡng lấy từ hằng số chứ không gõ 5 vào test: hằng số backend phải bằng
    `MASTERED_REPETITIONS` bên `packages/core/src/vocab-progress.ts` (thanh thành thạo vẽ
    đúng bấy nhiêu vạch), và test gõ số cứng vẫn xanh khi hai bên lệch nhau.

    Ba từ cùng một tag phủ cả ba trạng thái: đúng ngưỡng, ngay dưới ngưỡng, chưa ôn lần nào.
    """
    at_threshold_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])
    below_threshold_id = _save(client, owner, "mitigate", "giảm nhẹ", ["Môi trường"])
    _save(client, owner, "curriculum", "chương trình học", ["Môi trường"])
    _set_repetitions(db, at_threshold_id, MASTERED_REPETITIONS)
    _set_repetitions(db, below_threshold_id, MASTERED_REPETITIONS - 1)

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == [{"tag": "Môi trường", "count": 3, "mastered": 1}]


def test_tags_mastered_counts_separately_for_each_tag_of_the_same_word(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Một từ đã thuộc mang hai tag thì cộng vào `mastered` của CẢ HAI — cùng cách `count`
    đang làm. Ô chủ đề ở tab Sổ từ tính % bằng `mastered / count`, nên hai con số phải đếm
    trên cùng một tập từ."""
    entry_with_both_tags_id = _save(
        client, owner, "renewable", "tái tạo", ["Môi trường", "Giáo dục"]
    )
    _save(client, owner, "mitigate", "giảm nhẹ", ["Môi trường"])
    _set_repetitions(db, entry_with_both_tags_id, MASTERED_REPETITIONS)

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [
        {"tag": "Môi trường", "count": 2, "mastered": 1},
        {"tag": "Giáo dục", "count": 1, "mastered": 1},
    ]


def test_tags_mastered_word_without_review_card_still_in_count(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Từ chưa có thẻ ôn (`pos = 'phrase'`, hoặc từ lưu trước khi có tính năng SRS) phải rơi
    ra ngoài `mastered` mà VẪN nằm trong `count`.

    LEFT JOIN cho `srs_card.repetitions` là NULL, và `NULL >= 5` ra NULL chứ không TRUE nên
    nó tự rơi ra. Đổi sang INNER JOIN cho "gọn" thì `count` tụt theo — chip chủ đề đếm thiếu
    đúng những từ người dùng không thấy lý do vì sao.
    """
    entry_id = _save_without_card(db, owner.id, "renewable", "tái tạo")
    attach_tag_resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"tags": ["Môi trường"]}
    )
    assert attach_tag_resp.status_code == 200, attach_tag_resp.text

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [{"tag": "Môi trường", "count": 1, "mastered": 0}]


def test_tags_mastered_does_not_count_twice_when_tag_is_duplicated_in_array(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """`mastered` cũng phải đếm SỐ TỪ, không phải số dòng sau khi bung mảng — y như `count`.

    Thiếu `DISTINCT` ở đây thì một hàng `tags = {'dup','dup'}` cho `mastered = 2` trong khi
    `count = 1`, tức tỉ lệ thành thạo 200%.
    """
    entry_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lang, pos, meaning_vi, tags, user_id) "
                "VALUES ('renewable', 'en', 'n', 'tái tạo', ARRAY['dup','dup'], :u) "
                "RETURNING id"
            ),
            {"u": owner.id},
        ).scalar_one()
    )
    db.execute(
        text(
            "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions) "
            "VALUES (:v, CURRENT_DATE, 'REVIEW', :r)"
        ),
        {"v": entry_id, "r": MASTERED_REPETITIONS},
    )
    db.commit()

    resp = client.get("/api/vocab/tags", headers=owner.headers)

    assert resp.json()["tags"] == [{"tag": "dup", "count": 1, "mastered": 1}]


# ── GET /api/vocab?untagged=true — chip "Chưa gắn" ────────────────────────────


def test_untagged_returns_only_words_with_no_tags(client: Any, owner: UserFixture) -> None:
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _save(client, owner, "curriculum", "chương trình học", [])
    _save(client, owner, "alphabet", "bảng chữ cái", [])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true"}
    ).json()

    assert sorted(word["term"] for word in body["content"]) == ["alphabet", "curriculum"]
    assert body["totalElements"] == 2


def test_untagged_defaults_to_false_and_still_returns_whole_vocab_book(
    client: Any, owner: UserFixture
) -> None:
    """Tham số MỚI không được đổi hành vi của request cũ — extension bản cũ không gửi nó."""
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _save(client, owner, "curriculum", "chương trình học", [])

    body = client.get("/api/vocab", headers=owner.headers).json()

    assert body["totalElements"] == 2


def test_untagged_total_elements_correct_when_page_smaller_than_result_set(
    client: Any, owner: UserFixture
) -> None:
    """Điều kiện lọc phải nằm trong `_search_conditions` — dùng chung cho câu LẤY và câu ĐẾM.

    Chỉ nhét vào câu lấy dữ liệu thì `content` đúng còn `totalElements` đếm cả sổ: side panel
    vẽ ra số trang không tồn tại, bấm sang là trang trắng.
    """
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])
    _save(client, owner, "curriculum", "chương trình học", [])
    _save(client, owner, "alphabet", "bảng chữ cái", [])
    _save(client, owner, "betamax", "băng từ", [])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true", "size": 1}
    ).json()

    assert body["totalElements"] == 3
    assert body["totalPages"] == 3
    assert len(body["content"]) == 1


def test_untagged_combined_with_q_still_filters_by_both(client: Any, owner: UserFixture) -> None:
    """`untagged` KHÔNG đi cùng `tag`, nhưng đi cùng ô tìm kiếm thì bình thường."""
    _save(client, owner, "renewable", "tái tạo", [])
    _save(client, owner, "curriculum", "chương trình học", [])
    _save(client, owner, "renewal", "sự gia hạn", ["Môi trường"])

    body = client.get(
        "/api/vocab", headers=owner.headers, params={"untagged": "true", "q": "renew"}
    ).json()

    assert [word["term"] for word in body["content"]] == ["renewable"]
    assert body["totalElements"] == 1


def test_untagged_with_tag_returns_400_because_conditions_conflict(
    client: Any, owner: UserFixture
) -> None:
    """Chọn ngầm một trong hai là tệ hơn từ chối: người dùng thấy một danh sách không giải
    thích được, còn backend thì không nói ra nó đã bỏ điều kiện nào."""
    _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.get(
        "/api/vocab",
        headers=owner.headers,
        params={"untagged": "true", "tag": "Môi trường"},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["retryable"] is False
    assert "untagged" in resp.json()["message"]


# ── PATCH /api/vocab/{id} ─────────────────────────────────────────────────────


def test_patch_changes_meaning_and_keeps_tags_when_tags_absent(
    client: Any, owner: UserFixture
) -> None:
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "có thể tái tạo"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "có thể tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_replaces_all_tags_instead_of_merging(
    client: Any, owner: UserFixture
) -> None:
    """Ngữ nghĩa NGƯỢC với `POST /api/vocab` (`_merge_tags` gộp thêm).

    Trộn hai ngữ nghĩa vào một endpoint thì không còn cách nào gỡ một thẻ đã gắn nhầm.
    """
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường", "gắn nhầm"])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"tags": ["Giáo dục"]}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == ["Giáo dục"]
    # Và nghĩa KHÔNG bị đụng tới vì `meaningVi` vắng mặt trong body.
    assert resp.json()["meaningVi"] == "tái tạo"


def test_patch_empty_tag_array_clears_all_tags_unlike_absent_field(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Đây là ca mà `None` làm "không đổi" sẽ phá: `[]` là một YÊU CẦU thật (gỡ hết thẻ),
    không phải "client không gửi gì"."""
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    absent_tags_resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "tái tạo"}
    )
    assert absent_tags_resp.json()["tags"] == ["Môi trường"]

    empty_tags_resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"tags": []}
    )

    assert empty_tags_resp.status_code == 200, empty_tags_resp.text
    assert empty_tags_resp.json()["tags"] == []
    db.expire_all()
    remaining_tags = db.execute(
        text("SELECT tags FROM vocab_entry WHERE id = :i"), {"i": entry_id}
    ).scalar_one()
    assert remaining_tags == []


def test_patch_null_means_no_change(client: Any, owner: UserFixture) -> None:
    """Hợp đồng message của client (`UpdateVocabRequest`) dùng `null` cho "không đổi field
    này", nên body gửi lên có thể mang khoá với giá trị `null` — phải tương đương vắng mặt."""
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(
        f"/api/vocab/{entry_id}",
        headers=owner.headers,
        json={"meaningVi": None, "tags": None},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_empty_body_changes_nothing(client: Any, owner: UserFixture) -> None:
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

    resp = client.patch(f"/api/vocab/{entry_id}", headers=owner.headers, json={})

    assert resp.status_code == 200, resp.text
    assert resp.json()["meaningVi"] == "tái tạo"
    assert resp.json()["tags"] == ["Môi trường"]


def test_patch_whitespace_only_meaning_is_rejected_and_does_not_overwrite(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Lỗi validate của cả dự án trả 400 kèm `{code, message, retryable}` — xem
    `main.py: handle_validation`. Kiểm cả dữ liệu: từ chối mà vẫn ghi là ca im lặng nhất."""
    entry_id = _save(client, owner, "renewable", "tái tạo", ["Môi trường"])

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


def test_patch_nonexistent_id_returns_404_not_found(client: Any, owner: UserFixture) -> None:
    resp = client.patch("/api/vocab/999999", headers=owner.headers, json={"meaningVi": "x"})

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"
    assert resp.json()["retryable"] is False


def test_patch_without_login_returns_401(client: Any, owner: UserFixture) -> None:
    entry_id = _save(client, owner, "renewable", "tái tạo", [])

    resp = client.patch(f"/api/vocab/{entry_id}", json={"meaningVi": "x"})

    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_cors_allows_patch_method(client: Any) -> None:
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


def test_list_includes_review_card_state(
    client: Any, db: Session, owner: UserFixture
) -> None:
    entry_id = _save(client, owner, "renewable", "tái tạo", [])
    db.execute(
        text(
            "UPDATE srs_card SET state = 'REVIEW', repetitions = 4, "
            "due_date = CURRENT_DATE + 6 WHERE vocab_entry_id = :v"
        ),
        {"v": entry_id},
    )
    db.commit()
    db.expire_all()

    word = client.get("/api/vocab", headers=owner.headers).json()["content"][0]

    assert word["srsState"] == "REVIEW"
    assert word["srsRepetitions"] == 4
    assert word["srsDueDate"] == (date.today() + timedelta(days=6)).isoformat()


def test_three_srs_fields_all_null_when_word_has_no_card(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """CẢ BA cùng null nghĩa là "chưa có thẻ ôn" — trạng thái thật, không phải "chưa tải
    xong". UI vẽ thanh thành thạo phải phân biệt được hai thứ đó."""
    _save_without_card(db, owner.id, "renewable", "tái tạo")

    word = client.get("/api/vocab", headers=owner.headers).json()["content"][0]

    assert word["srsState"] is None
    assert word["srsDueDate"] is None
    assert word["srsRepetitions"] is None


def test_reading_one_word_also_includes_review_card_state(
    client: Any, owner: UserFixture
) -> None:
    entry_id = _save(client, owner, "renewable", "tái tạo", [])

    word = client.get(f"/api/vocab/{entry_id}", headers=owner.headers).json()

    assert word["srsState"] == "NEW"
    assert word["srsRepetitions"] == 0
    assert word["srsDueDate"] == date.today().isoformat()


def test_patch_returns_full_dto_including_srs_fields(client: Any, owner: UserFixture) -> None:
    """Response của PATCH là `VocabEntryDto` nguyên vẹn — client thay thẳng dòng trong danh
    sách bằng nó, nên thiếu field SRS là thanh thành thạo biến mất sau khi bấm Lưu."""
    entry_id = _save(client, owner, "renewable", "tái tạo", [])

    resp = client.patch(
        f"/api/vocab/{entry_id}", headers=owner.headers, json={"meaningVi": "tái sinh"}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["srsState"] == "NEW"
    assert resp.json()["srsRepetitions"] == 0
    assert resp.json()["srsDueDate"] == date.today().isoformat()


def test_review_card_join_does_not_skew_list_or_total_elements(
    client: Any, db: Session, owner: UserFixture
) -> None:
    """Từ CHƯA có thẻ vẫn phải nằm trong danh sách.

    Câu đếm dùng chung `_search_conditions` và KHÔNG join, nên đổi nhầm sang INNER JOIN cho
    câu lấy dữ liệu sẽ ra `totalElements = 3` mà `content` chỉ có 2 — phân trang lệch mà
    không có gì đỏ.
    """
    _save(client, owner, "renewable", "tái tạo", [])
    _save(client, owner, "mitigate", "giảm nhẹ", [])
    _save_without_card(db, owner.id, "curriculum", "chương trình học")

    body = client.get("/api/vocab", headers=owner.headers).json()

    assert body["totalElements"] == 3
    assert body["numberOfElements"] == 3
    assert len(body["content"]) == 3
