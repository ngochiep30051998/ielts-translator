"""Tạo thẻ ôn tập khi một từ mới vào sổ.

Chạy ĐỒNG BỘ trong cùng transaction với lệnh lưu, nên từ và thẻ hoặc cùng có hoặc cùng
không — không có trạng thái từ đã lưu mà thiếu thẻ.

Bên Java đây là `@EventListener` (đồng bộ) của `VocabEntrySavedEvent`. Ở đây không có
event bus: context vocabulary gọi thẳng `create_card_on_vocab_saved(db, entry)` ngay sau khi tạo
từ mới. Gọi thẳng đúng hơn với ngữ nghĩa cần có ở đây — cùng transaction, cùng luồng.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.srs import repository as repo
from app.vocabulary.models import VocabEntry

#: pos của một câu đầy đủ, do service worker đặt khi mode = SENTENCE.
PHRASE_POS = "phrase"


def create_card_on_vocab_saved(db: Session, entry: VocabEntry) -> None:
    """Bỏ qua câu (`pos == "phrase"` — câu không làm flashcard được) và từ đã có thẻ."""
    if entry.pos == PHRASE_POS:
        return

    # `entry` thường vẫn đang chờ ghi khi hàm này được gọi: id chỉ có sau khi flush, mà
    # không có id thì cả câu kiểm trùng lẫn khoá ngoại của thẻ đều vô nghĩa. Bên Java
    # `repository.save()` đã trả về entity có id nên chỗ này không lộ ra.
    db.flush()

    if repo.card_exists_for_vocab(db, entry.id):
        return

    repo.insert_card(db, vocab_entry_id=entry.id, due_date=date.today())
