"""Base Pydantic cho mọi DTO ra/vào HTTP.

Java dùng `record` với tên field camelCase, và Jackson phát ra đúng tên đó. Python đặt tên
snake_case. Cầu nối là alias tự sinh: field `display_name` phát ra `displayName`.

Đây không phải chuyện thẩm mỹ — `shared/types.ts` bên extension là bản gương của những DTO
này (ràng buộc #3). Phát ra `display_name` thay vì `displayName` là làm hỏng extension mà
không có test nào bên backend đỏ.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        # Nhận được cả tên snake_case lẫn camelCase khi đọc request; luôn PHÁT ra camelCase.
        populate_by_name=True,
        from_attributes=True,
    )
