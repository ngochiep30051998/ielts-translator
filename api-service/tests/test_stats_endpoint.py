"""Hợp đồng JSON của `GET /api/stats`.

Bốn điều kiểm ở đây là HỢP ĐỒNG, không phải chi tiết cài đặt: `daily` đủ 91 phần tử, ngày
trống được bơm 0, `avgScore` null với hai loại không có khái niệm điểm, và `quiz` luôn đủ 3
hàng đúng thứ tự. Phá một trong bốn là làm hỏng UI mà không test nào bên extension đỏ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.srs.models import MASTERED_REPETITIONS
from tests.conftest import NguoiDungTest


def _seed_the(db: Session, user_id: int, term: str) -> tuple[int, int]:
    """Trả `(vocab_entry_id, srs_card_id)`."""
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    card_id = int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions) "
                "VALUES (:v, CURRENT_DATE, 'REVIEW', 2) RETURNING id"
            ),
            {"v": vocab_id},
        ).scalar_one()
    )
    return vocab_id, card_id


def _seed_the_voi_repetitions(db: Session, user_id: int, term: str, repetitions: int) -> int:
    """Một từ + thẻ ôn có ĐÚNG số lần ôn đúng liên tiếp truyền vào. Trả `srs_card_id`.

    `repetitions` là cột duy nhất phân biệt "đã thuộc" với "đang học", nên nó phải đặt được
    tự do ở test chứ không cố định 2 như `_seed_the`.
    """
    vocab_id = int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, user_id) "
                "VALUES (:t, :t, 'en', 'verb', 'nghĩa', :u) RETURNING id"
            ),
            {"t": term, "u": user_id},
        ).scalar_one()
    )
    return int(
        db.execute(
            text(
                "INSERT INTO srs_card (vocab_entry_id, due_date, state, repetitions) "
                "VALUES (:v, CURRENT_DATE, :s, :r) RETURNING id"
            ),
            {"v": vocab_id, "s": "NEW" if repetitions == 0 else "REVIEW", "r": repetitions},
        ).scalar_one()
    )


def _seed_luot_on_hom_nay(db: Session, card_id: int, so_luot: int) -> None:
    """`now()` chạy qua đúng đường quy đổi múi giờ như dữ liệu thật."""
    for _ in range(so_luot):
        db.execute(
            text(
                "INSERT INTO review_log (card_id, rating, prev_interval, new_interval) "
                "VALUES (:c, 'GOOD', 0, 1)"
            ),
            {"c": card_id},
        )


def _seed_quiz(db: Session, vocab_id: int, loai: str, ket_qua: list[tuple[bool, int]]) -> None:
    item_id = int(
        db.execute(
            text(
                "INSERT INTO quiz_item (vocab_entry_id, type, payload, prompt_version) "
                "VALUES (:v, :l, '{}'::jsonb, 1) RETURNING id"
            ),
            {"v": vocab_id, "l": loai},
        ).scalar_one()
    )
    for dung, diem in ket_qua:
        db.execute(
            text(
                "INSERT INTO quiz_attempt (quiz_item_id, user_answer, correct, score) "
                "VALUES (:i, 'trả lời', :c, :s)"
            ),
            {"i": item_id, "c": dung, "s": diem},
        )


def test_nguoi_dung_moi_toanh_tra_toan_so_khong_chu_khong_phai_404(
    client: Any, owner: NguoiDungTest
) -> None:
    """Chưa học gì KHÔNG phải là lỗi. Endpoint này không bao giờ trả 404."""
    resp = client.get("/api/stats", headers=owner.headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["streak"] == {"current": 0, "longest": 0, "lastActiveDate": None}
    assert body["totals"] == {
        "reviews": 0,
        "learnedWords": 0,
        "masteredWords": 0,
        "learningWords": 0,
        "activeDays": 0,
        # Sổ từ rỗng: `avgBand` là null chứ KHÔNG phải 0.0 — "chưa có band nào" khác hẳn
        # "trung bình bằng 0", và UI hiện "—" cho ca đầu.
        "avgBand": None,
        "introducedLast7": 0,
    }
    assert body["recall"] == {"again": 0, "hard": 0, "good": 0, "easy": 0}
    assert len(body["daily"]) == 91
    assert all(diem["reviews"] == 0 for diem in body["daily"])


def test_daily_luon_du_91_phan_tu_lien_tuc_va_ket_thuc_hom_nay(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Ngày không ôn được bơm `reviews: 0`. Trả mảng thưa rồi bắt client tự dựng lịch là đẩy
    phép tính ngày tháng sang chỗ không có `settings.tz`."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot_on_hom_nay(db, card_id, 3)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()
    daily = body["daily"]

    assert len(daily) == 91
    ngay = [date.fromisoformat(diem["date"]) for diem in daily]
    assert ngay == sorted(ngay)
    assert ngay[-1] - ngay[0] == timedelta(days=90)
    assert daily[-1]["reviews"] == 3
    assert daily[-2]["reviews"] == 0


def test_quiz_luon_du_ba_hang_dung_thu_tu_ke_ca_khi_chua_lam(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    body = client.get("/api/stats", headers=owner.headers).json()

    assert [hang["type"] for hang in body["quiz"]] == [
        "FILL_BLANK",
        "COLLOCATION_CHOICE",
        "FREE_WRITE",
    ]
    assert all(hang["attempts"] == 0 and hang["correct"] == 0 for hang in body["quiz"])
    assert all(hang["avgScore"] is None for hang in body["quiz"])


def test_avg_score_chi_co_voi_free_write(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`FILL_BLANK` và `COLLOCATION_CHOICE` chấm 100 hoặc 0, nên điểm trung bình chỉ là
    `correct/attempts` viết lại bằng đơn vị khác. `null` ở đây nghĩa là "loại này không có
    khái niệm điểm", không phải "chưa có dữ liệu"."""
    vocab_id, _ = _seed_the(db, owner.id, "mitigate")
    _seed_quiz(db, vocab_id, "FILL_BLANK", [(True, 100), (False, 0)])
    _seed_quiz(db, vocab_id, "FREE_WRITE", [(True, 80), (False, 50)])
    db.commit()

    theo_loai = {hang["type"]: hang for hang in client.get(
        "/api/stats", headers=owner.headers
    ).json()["quiz"]}

    assert theo_loai["FILL_BLANK"]["attempts"] == 2
    assert theo_loai["FILL_BLANK"]["correct"] == 1
    assert theo_loai["FILL_BLANK"]["avgScore"] is None

    assert theo_loai["FREE_WRITE"]["attempts"] == 2
    assert theo_loai["FREE_WRITE"]["avgScore"] == 65


def test_totals_va_recall_tinh_tren_toan_bo_lich_su(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Chỉ `daily` bị giới hạn 91 ngày. Lượt ôn 200 ngày trước vẫn phải vào `totals.reviews`
    và `recall` — nếu không, con số lớn sẽ tụt xuống mỗi ngày trôi qua."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, reviewed_at) "
            "VALUES (:c, 'AGAIN', 0, 1, now() - interval '200 days')"
        ),
        {"c": card_id},
    )
    _seed_luot_on_hom_nay(db, card_id, 2)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["reviews"] == 3
    assert body["totals"]["activeDays"] == 2
    assert body["totals"]["learnedWords"] == 1
    assert body["recall"] == {"again": 1, "hard": 0, "good": 2, "easy": 0}
    # Nhưng ngày 200 hôm trước nằm NGOÀI cửa sổ, nên daily chỉ thấy 2 lượt của hôm nay.
    assert sum(diem["reviews"] for diem in body["daily"]) == 2


def test_chua_dang_nhap_tra_401(client: Any) -> None:
    assert client.get("/api/stats").status_code == 401


def _seed_luot(db: Session, card_id: int, mode: str, so_luot: int) -> None:
    for _ in range(so_luot):
        db.execute(
            text(
                "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
                "VALUES (:c, 'GOOD', 1, 6, :m)"
            ),
            {"c": card_id, "m": mode},
        )


def test_luot_practice_vao_daily_practice_khong_vao_reviews(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot(db, card_id, "SCHEDULED", 2)
    _seed_luot(db, card_id, "PRACTICE", 5)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()
    hom_nay = body["daily"][-1]

    assert hom_nay["reviews"] == 2
    assert hom_nay["practice"] == 5


def test_luot_practice_khong_vao_totals_va_recall(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`totals` và `recall` giữ nguyên nghĩa cũ: chỉ đếm lượt ôn theo lịch. Trộn hai loại
    hoạt động vào tỉ lệ nhớ thì con số không so sánh được với chính nó tháng trước."""
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot(db, card_id, "SCHEDULED", 2)
    _seed_luot(db, card_id, "PRACTICE", 5)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["reviews"] == 2
    assert body["recall"] == {"again": 0, "hard": 0, "good": 2, "easy": 0}


def _seed_tu_co_band(db: Session, user_id: int, term: str, band: str | None) -> int:
    """Một từ có `band_level`. Cột này là CHUỖI (`varchar(8)`) chứ không phải số — Gemini
    trả "7.0", và cũng trả cả những thứ không phải số."""
    return int(
        db.execute(
            text(
                "INSERT INTO vocab_entry (term, lemma, lang, pos, meaning_vi, band_level, "
                "user_id) VALUES (:t, :t, 'en', 'verb', 'nghĩa', :b, :u) RETURNING id"
            ),
            {"t": term, "b": band, "u": user_id},
        ).scalar_one()
    )


def _seed_luot_dau_doi(db: Session, card_id: int, lui: str) -> None:
    """Lượt ôn ĐẦU ĐỜI của một thẻ, lùi về quá khứ `lui`.

    `prev_interval = 0` là dấu hiệu nhận biết lượt đầu đời (xem `count_introduced_since`):
    thẻ mới có `interval_days = 0`, còn mọi lượt sau đó đều có `prev_interval >= 1`.
    """
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, reviewed_at) "
            "VALUES (:c, 'GOOD', 0, 1, now() - CAST(:lui AS interval))"
        ),
        {"c": card_id, "lui": lui},
    )


def test_avg_band_bo_qua_hang_khong_parse_duoc_chu_khong_coi_la_0(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`band_level` là chuỗi tự do do Gemini sinh, nên "chưa rõ" là dữ liệu có thật.

    Coi hàng không đọc được là 0 thì trung bình tụt thẳng xuống 5.0 ở ví dụ này — một con số
    trông vẫn hợp lý, và không có gì đỏ.
    """
    _seed_tu_co_band(db, owner.id, "mitigate", "7.0")
    _seed_tu_co_band(db, owner.id, "scrutiny", "8.0")
    _seed_tu_co_band(db, owner.id, "unknown", "chưa rõ")
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["avgBand"] == 7.5


def test_avg_band_bo_qua_chuoi_nan_vi_float_khong_nem_loi_voi_no(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """`float("nan")` KHÔNG ném lỗi — nên bắt `ValueError` một mình là chưa đủ.

    Một NaN lọt vào trung bình thì response mang literal `NaN`, thứ `JSON.parse` của trình
    duyệt từ chối: cả màn Hôm nay trắng vì đúng một hàng dữ liệu rác.
    """
    _seed_tu_co_band(db, owner.id, "mitigate", "7.0")
    _seed_tu_co_band(db, owner.id, "rac", "nan")
    _seed_tu_co_band(db, owner.id, "rac2", "inf")
    db.commit()

    resp = client.get("/api/stats", headers=owner.headers)

    assert resp.json()["totals"]["avgBand"] == 7.0
    assert "NaN" not in resp.text and "Infinity" not in resp.text


def test_avg_band_null_khi_khong_hang_nao_doc_duoc_khac_han_0(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """null ≠ 0.0. Sổ từ có 2 từ mà chưa từ nào có band là trạng thái BÌNH THƯỜNG; trả 0.0
    ở đây là nói với người học rằng band trung bình của họ bằng 0."""
    _seed_tu_co_band(db, owner.id, "mitigate", None)
    _seed_tu_co_band(db, owner.id, "unknown", "chưa rõ")
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["avgBand"] is None


def test_avg_band_tinh_tren_ca_so_tu_ke_ca_tu_chua_co_the_on(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Trung bình của CẢ SỔ, không phải của riêng những từ đang trong lịch ôn — ô "band trung
    bình" đứng cạnh dòng "N từ trong sổ"."""
    _seed_tu_co_band(db, owner.id, "mitigate", "6.0")
    _seed_tu_co_band(db, owner.id, "scrutiny", "9.0")
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["avgBand"] == 7.5


def test_mastered_words_dung_nguong_thuoc_chu_khong_phai_da_on_mot_lan(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """"Đã thuộc" chỉ được mang MỘT nghĩa trên toàn hệ thống: `repetitions >=
    MASTERED_REPETITIONS`.

    Ca ép buộc là từ có `repetitions = 1`. Nếu ô "đã thuộc" ở màn Hôm nay đếm nó, màn hình tự
    mâu thuẫn với chính mình: card "Chủ đề đang yếu" ngay bên dưới vẽ 0% cho đúng từ đó (nó
    đếm theo ngưỡng 5), và dòng từ ở Sổ từ vẫn ghi "ôn sau N ngày".
    """
    _seed_the_voi_repetitions(db, owner.id, "chua_on", 0)
    _seed_the_voi_repetitions(db, owner.id, "mitigate", 1)
    _seed_the_voi_repetitions(db, owner.id, "scrutiny", MASTERED_REPETITIONS - 1)
    _seed_the_voi_repetitions(db, owner.id, "curriculum", MASTERED_REPETITIONS)
    db.commit()

    totals = client.get("/api/stats", headers=owner.headers).json()["totals"]

    assert totals["masteredWords"] == 1
    assert totals["learningWords"] == 2
    # `learnedWords` GIỮ NGUYÊN nghĩa cũ (`repetitions >= 1`): StatsTab hiện nó dưới nhãn
    # "từ đã học", khác hẳn nhãn "đã thuộc" nên hai con số không mâu thuẫn nhau.
    assert totals["learnedWords"] == 3


def test_mastered_va_learning_khong_giao_nhau_va_cong_lai_bang_learned(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Bất biến: `masteredWords + learningWords == learnedWords`, với mọi giá trị repetitions.

    Ba con số đứng trên cùng một màn hình. Chúng lệch bất biến này là có từ bị đếm hai lần
    hoặc rơi mất khỏi cả hai nhóm — và không con số nào trông sai đủ để ai đó nhận ra.
    """
    for i in range(MASTERED_REPETITIONS + 3):
        _seed_the_voi_repetitions(db, owner.id, f"word{i}", i)
    db.commit()

    totals = client.get("/api/stats", headers=owner.headers).json()["totals"]

    assert totals["masteredWords"] == 3  # repetitions 5, 6, 7
    assert totals["learningWords"] == 4  # repetitions 1, 2, 3, 4
    assert totals["masteredWords"] + totals["learningWords"] == totals["learnedWords"]


def test_introduced_last7_chi_dem_luot_dau_doi_trong_7_ngay_gan_nhat(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Cửa sổ là 7 ngày TÍNH CẢ HÔM NAY, tức [hôm nay − 6 ; hôm nay] theo múi giờ server.

    Ba mốc phủ đúng hai biên: hôm nay (trong), 6 ngày trước (biên trong), 7 ngày trước
    (ngay ngoài). Lệch một ngày ở đây làm con số "+N từ mới tuần này" nhảy lung tung mỗi lần
    đổi giờ trong ngày.
    """
    _, hom_nay = _seed_the(db, owner.id, "mitigate")
    _, sau_ngay = _seed_the(db, owner.id, "scrutiny")
    _, bay_ngay = _seed_the(db, owner.id, "curriculum")
    _seed_luot_dau_doi(db, hom_nay, "0 days")
    _seed_luot_dau_doi(db, sau_ngay, "6 days")
    _seed_luot_dau_doi(db, bay_ngay, "7 days")
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["introducedLast7"] == 2
    # `learnedWords` vẫn đếm toàn bộ lịch sử. Hai con số này KHÔNG còn là "tổng và phần tăng
    # của nhau" như bản trước — chúng đo hai thứ khác nhau và hiển thị ở hai ô khác nhau.
    assert body["totals"]["learnedWords"] == 3


def test_introduced_last7_dem_the_phan_biet_chu_khong_dem_dong_log(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Đơn vị của con số này là TỪ, không phải lượt ôn.

    Lịch SM-2 thật chỉ sinh tối đa một dòng `prev_interval = 0` cho mỗi thẻ (bấm Lại đặt
    interval về 1), nhưng bất biến đó nằm ở `scheduler.py` chứ không ở schema: không có ràng
    buộc nào trong DB cấm dòng thứ hai. Đếm DÒNG là để một lần nhập tay, một lần chạy lại
    migration hay một lần sửa scheduler làm "+N từ mới tuần này" đếm bội mà không có gì đỏ.
    """
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot_dau_doi(db, card_id, "0 days")
    _seed_luot_dau_doi(db, card_id, "1 days")
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["introducedLast7"] == 1


def test_introduced_last7_dem_ca_the_bam_lai_vi_no_van_da_duoc_dua_vao_on(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Thẻ mới bấm "Lại" VẪN được tính — và đó là hành vi đúng của con số này.

    `review_log` không lưu `repetitions`, nên "vượt ngưỡng thuộc trong 7 ngày" là thứ KHÔNG
    tính được từ dữ liệu đang có. Con số này vì thế đo cái mà log trả lời được chính xác:
    từ lần đầu bước vào vòng ôn. Thẻ bị bấm Lại đã thực sự bước vào vòng đó (`repetitions`
    về 0, nhưng nó không còn là thẻ NEW), nên đếm nó là đúng — miễn là nhãn hiển thị nói
    "từ mới", không phải "đã thuộc".
    """
    card_id = _seed_the_voi_repetitions(db, owner.id, "mitigate", 0)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
            "VALUES (:c, 'AGAIN', 0, 1, 'SCHEDULED')"
        ),
        {"c": card_id},
    )
    db.commit()

    totals = client.get("/api/stats", headers=owner.headers).json()["totals"]

    assert totals["introducedLast7"] == 1
    # Và nó KHÔNG lẫn sang ô "đã thuộc" — đây chính là chỗ hai con số từng nói ngược nhau.
    assert totals["masteredWords"] == 0
    assert totals["learnedWords"] == 0


def test_introduced_last7_khong_dem_luot_on_lai_lan_luot_luyen_them(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """Lượt ôn lại (`prev_interval >= 1`) không phải lượt đưa thẻ vào vòng ôn.

    Đếm cả chúng thì "+N từ mới tuần này" biến thành số lượt ôn trong tuần — một con số khác
    hẳn. Lượt luyện thêm càng không được tính: nó không đụng gì tới lịch.
    """
    _, card_id = _seed_the(db, owner.id, "mitigate")
    _seed_luot(db, card_id, "SCHEDULED", 3)
    db.execute(
        text(
            "INSERT INTO review_log (card_id, rating, prev_interval, new_interval, mode) "
            "VALUES (:c, 'GOOD', 0, 1, 'PRACTICE')"
        ),
        {"c": card_id},
    )
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["totals"]["introducedLast7"] == 0


def test_ngay_chi_co_practice_khong_giu_streak_va_khong_tinh_active_day(
    client: Any, db: Session, owner: NguoiDungTest
) -> None:
    """BẪY §7.1 — ca quan trọng nhất của task này.

    `dem_luot_on_theo_ngay` một mình nuôi bốn con số. Thêm cột đếm PRACTICE vào câu đó làm
    GROUP BY bắt đầu trả về cả những ngày CHỈ có lượt luyện; nếu streak và activeDays lấy
    danh sách ngày từ đó, chúng bắt đầu tính cả ngày chỉ luyện — mà không ai chạm vào
    `streak.py`. Đã xác minh bằng SQL thật: ngày chỉ có PRACTICE CÓ lọt vào GROUP BY.
    """
    _, card_id = _seed_the(db, owner.id, "mitigate")
    # Hôm nay: chỉ luyện thêm, không ôn theo lịch.
    _seed_luot(db, card_id, "PRACTICE", 4)
    db.commit()

    body = client.get("/api/stats", headers=owner.headers).json()

    assert body["streak"]["current"] == 0
    assert body["streak"]["lastActiveDate"] is None
    assert body["totals"]["activeDays"] == 0
    assert body["totals"]["reviews"] == 0
    # Nhưng công sức vẫn hiện ở biểu đồ.
    assert body["daily"][-1]["practice"] == 4
