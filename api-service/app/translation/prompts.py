"""Đọc prompt từ thư mục `prompts/` — bản port của `PromptLoader` + `PromptTemplate`.

Mỗi file có header `version: N`, một dòng `---`, rồi tới nội dung. Version đi vào cache key
nên sửa nội dung prompt PHẢI tăng version — đó là cách duy nhất làm cache cũ hết hiệu lực
(ràng buộc #5).

Luật tách, đúng ba câu và cả ba đều có test bên Java chống lưng:

1. Dòng phân cách là dòng **strip xong bằng đúng `---`**, không phải dòng *bắt đầu bằng*
   `---`. Một dòng ghi chú kiểu `--- chưa phải phân cách` mà bị nhận nhầm sẽ nuốt mất nội
   dung của nó và cắt body sai — sai lặng lẽ. Nay nó gộp vào header, header không parse
   được thành số, và parser từ chối RÕ RÀNG kèm đường dẫn file.
2. Chỉ dừng ở dòng `---` ĐẦU TIÊN. Đường kẻ ngang markdown `---` nằm trong thân bài là hợp
   lệ và phải được giữ nguyên.
3. Thiếu phân cách, thiếu `version:`, hoặc version không phải số đều là ném lỗi, không phải
   đoán bừa: prompt là tài nguyên đóng gói cùng ứng dụng, hỏng ở đây là hỏng lúc deploy chứ
   không phải lỗi của người dùng.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.translation.models import Direction, Mode

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

_HEADER_PREFIX = "version:"
_DELIMITER = "---"
_NO_CONTEXT = "(không có ngữ cảnh)"


class PromptError(RuntimeError):
    """Prompt sai định dạng. Tương đương `IllegalStateException` bên Java: catch-all ở
    `main.py` biến nó thành 500/INTERNAL, đúng như `handleOther`."""


@dataclass(frozen=True)
class PromptTemplate:
    body: str
    version: int

    def render(self, vars: Mapping[str, str | None]) -> str:
        """Thay mọi {{KHOÁ}} bằng giá trị tương ứng. Giá trị None coi như chuỗi rỗng."""
        out = self.body
        for key, value in vars.items():
            out = out.replace("{{" + key + "}}", "" if value is None else value)
        return out

    def render_text(self, text: str | None, context: str | None) -> str:
        """Đường dùng của bốn prompt dịch. Ngữ cảnh rỗng vẫn phải điền một câu có nghĩa —
        để `{{CONTEXT}}` thành chuỗi trắng sẽ làm model tưởng ngữ cảnh bị cắt mất."""
        safe_context = _NO_CONTEXT if context is None or not context.strip() else context
        return self.render({"TEXT": text or "", "CONTEXT": safe_context})


def parse_template(raw: str, mo_ta: str) -> PromptTemplate:
    """Tách header/body từ nội dung thô. `mo_ta` chỉ để nhét vào thông điệp lỗi — không có
    nó thì "Prompt thiếu dòng phân cách" là một câu vô dụng khi có mười file prompt."""
    lines = raw.split("\n")
    delimiter_index = -1
    for i, line in enumerate(lines):
        if line.strip() == _DELIMITER:
            delimiter_index = i
            break
    if delimiter_index < 0:
        raise PromptError(f"Prompt thiếu dòng phân cách '---': {mo_ta}")

    header = "\n".join(lines[:delimiter_index]).strip()
    body = "\n".join(lines[delimiter_index + 1 :]).strip()

    if not header.startswith(_HEADER_PREFIX):
        raise PromptError(f"Prompt thiếu header 'version:': {mo_ta}")
    try:
        version = int(header[len(_HEADER_PREFIX) :].strip())
    except ValueError as e:
        raise PromptError(f"Prompt có version không phải số: {mo_ta}") from e
    return PromptTemplate(body, version)


class PromptLoader:
    """Đọc và nhớ kết quả parse. Một tiến trình chỉ đọc mỗi file đúng một lần.

    `directory` tham số hoá để test trỏ được vào thư mục prompt hỏng — bản Java phải gọi
    `readTemplate` qua reflection cho việc này.
    """

    def __init__(self, directory: Path = PROMPTS_DIR) -> None:
        self._directory = directory
        self._cache: dict[str, PromptTemplate] = {}

    def load(self, direction: Direction, mode: Mode) -> PromptTemplate:
        return self.load_file(_file_name_for(direction, mode))

    def load_file(self, file_name: str) -> PromptTemplate:
        """`file_name` là tên file TRẦN trong thư mục prompt, ví dụ "srs-distractors.md"."""
        cached = self._cache.get(file_name)
        if cached is not None:
            return cached
        template = self._read(file_name)
        self._cache[file_name] = template
        return template

    def _read(self, file_name: str) -> PromptTemplate:
        path = self._directory / file_name
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            raise PromptError(f"Không đọc được prompt: {path}") from e
        return parse_template(raw, str(path))


def _file_name_for(direction: Direction, mode: Mode) -> str:
    dir_part = "en-vi" if direction is Direction.EN_VI else "vi-en"
    mode_part = "word" if mode is Mode.WORD else "sentence"
    return f"{dir_part}-{mode_part}.md"


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptLoader:
    """Dùng chung một loader cho cả tiến trình để bộ nhớ đệm parse còn tác dụng. Context
    quiz và srs cũng lấy prompt qua đây (`load_file`), y như bên Java."""
    return PromptLoader()
