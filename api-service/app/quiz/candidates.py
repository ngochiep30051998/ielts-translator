"""Chọn từ đưa vào đề. Đây là chỗ DUY NHẤT module quiz chạm tới bảng `srs_card`, và nó chỉ
ĐỌC.

Vì sao SQL trần chứ không import `app.srs.repository`: giữ chiều phụ thuộc sạch. Quiz không
import gì từ package srs, nên không có đường nào để lỡ tay gọi một hàm ghi. Bất biến "quiz
không tác động tới lịch SRS" được test isolation kiểm chứng bằng cách so ảnh chụp
trước/sau, không bằng lời hứa — nhưng lời hứa dễ giữ hơn nhiều khi hàm ghi không nằm trong
tầm với.

Luật của file này, ngắn đủ để không quên: **chỉ `SELECT`**. Thêm một `UPDATE` vào đây là
làm màn quiz âm thầm đẩy lịch ôn của người dùng.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Từ đã ôn ít nhất một lượt, ưu tiên từ ít bị hỏi nhất, rồi tới từ hay quên nhất.
#: Từ chưa ôn lần nào (repetitions = 0) KHÔNG được đưa vào quiz — chưa gặp mặt thì hỏi là
#: phạt oan.
#:
#: `LEFT JOIN` hai bậc rồi `count(qa.id)`: từ chưa có đề nào, và từ có đề nhưng chưa ai làm,
#: đều ra 0 — cả hai đều là "chưa bị hỏi lần nào", đúng ý xếp ưu tiên. Đổi sang `INNER JOIN`
#: là loại sạch nhóm đáng được hỏi nhất.
_CANDIDATES = text(
    """
    SELECT v.id
    FROM vocab_entry v
    JOIN srs_card c ON c.vocab_entry_id = v.id
    LEFT JOIN quiz_item qi ON qi.vocab_entry_id = v.id
    LEFT JOIN quiz_attempt qa ON qa.quiz_item_id = qi.id
    WHERE v.user_id = :user_id AND c.repetitions >= 1
    GROUP BY v.id, c.lapses
    ORDER BY count(qa.id) ASC, c.lapses DESC, v.id ASC
    LIMIT :limit
    """
)


def find_candidates(db: Session, user_id: int, limit: int) -> list[int]:
    """Id các từ nên đưa vào đề, nhiều nhất `limit` từ.

    Rỗng là trạng thái BÌNH THƯỜNG ("chưa ôn từ nào đủ điều kiện"), không phải lỗi — người
    gọi phải trả mảng rỗng chứ đừng ném.
    """
    return [
        int(vocab_id)
        for vocab_id in db.execute(_CANDIDATES, {"user_id": user_id, "limit": limit}).scalars()
    ]
