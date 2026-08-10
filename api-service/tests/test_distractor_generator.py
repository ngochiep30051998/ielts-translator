"""Bản port của `DistractorGeneratorIT` — luồng sinh mồi nhử chạy nền sau khi lưu từ.

Bên Java, việc này là `@TransactionalEventListener(AFTER_COMMIT)` + `@Async`, nên test phải
`await()` tới 5 giây cho thread nền chạy xong. Ở FastAPI vai trò đó do `BackgroundTasks`
đảm nhiệm và `TestClient` chạy chúng ĐỒNG BỘ ngay sau khi response được gửi — nên không có
`await`, không có `sleep`: hễ `client.post(...)` trả về là tác vụ nền đã chạy xong. Đó là
lý do các khẳng định dưới đây đọc thẳng DB mà không cần vòng chờ nào.

Hai điều kiện then chốt của luồng này, cả hai đều được kiểm ở đây:

* tác vụ nền chạy SAU khi session của request đã commit — nếu không, nó mở session riêng và
  không thấy từ vừa lưu, `find_vocab_entry` trả None, không có mồi nhử nào được sinh mà cũng
  chẳng có gì đỏ;
* Gemini hỏng KHÔNG được kéo đổ việc lưu từ.

**Thứ tự fixture có ý nghĩa: `client` phải đứng TRƯỚC `gemini` trong chữ ký test.** Fixture
`gemini` vá `httpx.Client.__init__` cho toàn tiến trình, mà `TestClient` cũng chính là một
`httpx.Client` — dựng nó sau khi vá thì chính TestClient nhận transport giả, `client.post`
không bao giờ chạm tới ứng dụng và vẫn trả về 200. Đó là kiểu hỏng tệ nhất: test xanh mà
chẳng kiểm gì cả.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.srs.distractors import current_prompt_version, generate_distractors
from tests.conftest import GeminiGia, NguoiDungTest

BO_HOP_LE: dict[str, list[str]] = {
    "vi_options": ["làm trầm trọng thêm", "phóng đại", "trì hoãn"],
    "en_options": ["aggravate", "exaggerate", "postpone"],
}


def _luu_tu(client: Any, owner: NguoiDungTest, term: str, pos: str) -> int:
    """Lưu một từ qua API thật, đúng hình dạng `request(term, pos)` bên Java.

    `meaningVi` = "nghĩa của <term>" cũng lấy nguyên từ bản Java: test bộ hỏng dựa vào việc
    Gemini trả về đúng chuỗi này để mô phỏng "mồi nhử trùng đáp án đúng".
    """
    resp = client.post(
        "/api/vocab",
        headers=owner.headers,
        json={
            "term": term,
            "lemma": term,
            "lang": "en",
            "pos": pos,
            "meaningVi": f"nghĩa của {term}",
            "tags": [],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["alreadyExists"] is False
    return int(resp.json()["id"])


def _moi_nhu(db: Session, vocab_id: int) -> Any:
    db.rollback()  # kết thúc transaction đọc cũ để thấy commit của tác vụ nền
    return db.execute(
        text(
            "SELECT vi_options, en_options, prompt_version "
            "FROM srs_distractor WHERE vocab_entry_id = :v"
        ),
        {"v": vocab_id},
    ).one_or_none()


def _so_ban_ghi(db: Session) -> int:
    db.rollback()
    return int(db.execute(text("SELECT count(*) FROM srs_distractor")).scalar_one())


def test_luu_mot_tu_don_thi_moi_nhu_duoc_sinh_va_luu_kem_prompt_version(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Ca chính: lưu từ → tác vụ nền gọi Gemini → bộ mồi nhử nằm trong DB kèm version prompt.

    `prompt_version` là thứ duy nhất làm mồi nhử cũ hết hiệu lực khi sửa nội dung prompt
    (ràng buộc #5). Ghi thiếu hoặc ghi sai version thì `find_fresh_distractors` lọc trượt và
    hệ thống sinh lại mồi nhử ở MỌI lượt mở tab ôn — đốt quota mà không ai thấy.
    """
    gemini.tra_json(BO_HOP_LE)

    vocab_id = _luu_tu(client, owner, "mitigate", "verb")

    row = _moi_nhu(db, vocab_id)
    assert row is not None, "Tác vụ nền không ghi được mồi nhử nào"
    assert len(row.vi_options) == 3
    # So từng cột, đúng thứ tự — không chỉ đếm: thứ tự sai nghĩa là mồi nhử EN bị gán vào
    # chiều VI, câu hỏi hiện ra bốn từ tiếng Anh cho một đề tiếng Việt.
    assert row.en_options == ["aggravate", "exaggerate", "postpone"]
    assert row.vi_options == ["làm trầm trọng thêm", "phóng đại", "trì hoãn"]
    assert row.prompt_version == current_prompt_version()
    assert gemini.so_lan_goi == 1


def test_luu_ca_mot_cau_pos_phrase_thi_khong_goi_gemini(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Câu đầy đủ không làm trắc nghiệm được, nên không có gì để sinh mồi nhử.

    Khẳng định "KHÔNG gọi Gemini" quan trọng hơn khẳng định "không có bản ghi": một lượt gọi
    thừa cho mỗi câu người dùng bôi đen là quota bị đốt lặng lẽ, mà kết quả thì bị vứt đi.
    """
    # Xếp sẵn một phản hồi hợp lệ: nếu code lỡ gọi Gemini thì nó sẽ THÀNH CÔNG và ghi bản
    # ghi, tức là test đỏ ở đúng chỗ cần đỏ chứ không đỏ vì hàng đợi cạn.
    gemini.tra_json(BO_HOP_LE)

    _luu_tu(client, owner, "Governments must act on climate change.", "phrase")

    assert gemini.requests == []
    assert _so_ban_ghi(db) == 0


def test_gemini_loi_thi_tu_van_nam_trong_so_chi_la_chua_co_moi_nhu(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Gemini chết không được kéo đổ việc lưu từ.

    Đây chính là lý do luồng này chạy nền chứ không nằm trong transaction lưu từ: người dùng
    bôi đen một từ và bấm lưu thì từ phải vào sổ, bất kể Gemini có sống hay không. Lần mở tab
    ôn sau sẽ thử lại qua đường `_request_missing`.

    Xếp 503 hai lần vì `GeminiClient` retry đúng một lần với lỗi tạm thời — bản Java mock
    thẳng `generateJson` nên không lộ ra chi tiết đó; ở đây đi qua tầng vận chuyển thật nên
    số lượt gọi là một phần của hành vi được kiểm.
    """
    gemini.tra_status(503, '{"error":"unavailable"}', lap=2)

    vocab_id = _luu_tu(client, owner, "resilient", "adjective")

    assert vocab_id > 0
    db.rollback()
    con_tu = db.execute(
        text("SELECT count(*) FROM vocab_entry WHERE id = :v"), {"v": vocab_id}
    ).scalar_one()
    assert con_tu == 1, "Gemini lỗi đã kéo đổ luôn việc lưu từ"
    # Thẻ ôn cũng phải còn: nó được tạo ĐỒNG BỘ trong cùng transaction với từ.
    con_the = db.execute(
        text("SELECT count(*) FROM srs_card WHERE vocab_entry_id = :v"), {"v": vocab_id}
    ).scalar_one()
    assert con_the == 1
    assert _moi_nhu(db, vocab_id) is None
    assert gemini.so_lan_goi == 2


def test_gemini_tra_bo_hong_trung_dap_an_dung_thi_khong_luu_gi(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """Không lưu gì, để lần sau sinh lại.

    Lưu một bộ hỏng còn tệ hơn không lưu: `find_fresh_distractors` sẽ coi nó là hợp lệ, và
    người học gặp một câu có hai đáp án cùng đúng — chọn đúng vẫn bị chấm sai. Bộ hỏng cũng
    KHÔNG được retry: nó không phải lỗi tạm thời, gọi lại ngay chỉ tốn thêm một lượt quota.
    """
    gemini.tra_json(
        {
            "vi_options": ["nghĩa của mitigate", "phóng đại", "trì hoãn"],
            "en_options": ["aggravate", "exaggerate", "postpone"],
        }
    )

    vocab_id = _luu_tu(client, owner, "mitigate", "verb")

    assert _moi_nhu(db, vocab_id) is None
    assert _so_ban_ghi(db) == 0
    assert gemini.so_lan_goi == 1


def test_sinh_lai_cho_tu_da_co_moi_nhu_thi_ghi_de_khong_tao_ban_ghi_thu_hai(
    client: Any, db: Session, gemini: GeminiGia, owner: NguoiDungTest
) -> None:
    """`vocab_entry_id` là khoá duy nhất, nên sinh lại phải UPDATE chứ không INSERT.

    Nếu code quên tra bản ghi cũ, lượt thứ hai sẽ đâm vào ràng buộc unique và lỗi bị
    `except Exception` của tác vụ nền nuốt mất — mồi nhử đứng yên ở bản cũ vĩnh viễn, không
    có gì đỏ, và tăng version prompt cũng vô tác dụng.

    Lượt thứ hai gọi thẳng `generate_distractors` (vai của `generator.generateAsync` bên
    Java): đây đúng là đường mà `_request_missing` dùng để bù mồi nhử hết hiệu lực.
    """
    gemini.tra_json(BO_HOP_LE)
    vocab_id = _luu_tu(client, owner, "mitigate", "verb")
    assert _moi_nhu(db, vocab_id) is not None

    truoc = _moi_nhu(db, vocab_id)
    gemini.tra_json({"vi_options": ["một", "hai", "ba"], "en_options": ["one", "two", "three"]})
    generate_distractors(vocab_id)

    assert _so_ban_ghi(db) == 1
    sau = _moi_nhu(db, vocab_id)
    assert sau is not None
    assert sau.en_options == ["one", "two", "three"]
    assert sau.vi_options == ["một", "hai", "ba"]
    assert truoc is not None and truoc.en_options != sau.en_options
    assert gemini.so_lan_goi == 2
