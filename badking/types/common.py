"""پایه مشترک تمام مدلها: Pydantic v2، tolerant در برابر فیلدهای ناشناخته بله."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BaleModel(BaseModel):
    """مدل پایه.

    بله گاهی فیلدهای اضافه میفرستد یا فیلدهای اختیاری را حذف میکند.
    بنابراین extra=allow و populate_by_name=True.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    def raw(self) -> dict[str, Any]:
        """برگرداندن تمام فیلدها (شامل فیلدهای اضافی) به صورت dict."""
        return self.model_dump(mode="python")
