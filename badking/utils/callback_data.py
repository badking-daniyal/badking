"""CallbackData — داده دکمه شیشه‌ای با تایپ امن.

رشته `"product:view:10"` را دستی پارس نکن. یک کلاس تعریف می‌کنی، بسته
می‌شود، و با تایپ درست برمی‌گردد:

    from badking.utils.callback_data import CallbackData

    class ProductCB(CallbackData, prefix="product"):
        action: str
        product_id: int

    # ساخت دکمه
    data = ProductCB(action="view", product_id=10).pack()   # "product:view:10"

    # در هندلر
    @dp.callback_query(ProductCB.filter(action="view"))
    async def on_view(cq, cb: ProductCB):
        print(cb.product_id)   # 10

اگر بله فرمت را عوض کند، فقط `pack`/`unpack` تغییر می‌کند، نه هندلرها.
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

T = TypeVar("T", bound="CallbackData")


class CallbackData:
    """پایه داده دکمه، با تایپ امن و فرمت قابل تغییر.

    زیرکلاس با `prefix` می‌سازد. فیلدها از `__annotations__` خوانده می‌شوند،
    پس نیازی به pydantic نیست.
    """

    __prefix__: ClassVar[str] = "cb"
    __separator__: ClassVar[str] = ":"

    def __init_subclass__(
        cls, prefix: str = "cb", sep: str = ":", **kwargs: Any
    ) -> None:
        super().__init_subclass__(**kwargs)
        cls.__prefix__ = prefix
        cls.__separator__ = sep

    def __init__(self, **kwargs: Any) -> None:
        annotations = _all_annotations(type(self))
        for name in annotations:
            if name.startswith("_"):
                continue
            if name not in kwargs:
                raise TypeError(f"فیلد لازم نیست: {name}")
            setattr(self, name, kwargs[name])
        extra = set(kwargs) - set(annotations)
        if extra:
            raise TypeError(f"فیلد ناشناخته: {sorted(extra)}")

    # ---------- بسته‌بندی ----------

    def pack(self) -> str:
        """به رشته فشرده تبدیل می‌کند: `prefix:v1:v2:...`"""
        parts = [self.__prefix__]
        for name in _all_annotations(type(self)):
            if name.startswith("_"):
                continue
            parts.append(str(getattr(self, name)))
        return self.__separator__.join(parts)

    @classmethod
    def unpack(cls: type[T], value: str) -> T:
        """از رشته به نمونه تایپ‌دار. خطا می‌دهد اگر فرمت نخواند."""
        parts = value.split(cls.__separator__)
        if not parts or parts[0] != cls.__prefix__:
            raise ValueError(
                f"پیشوند نامنطبق: {parts[0] if parts else ''!r} != {cls.__prefix__!r}"
            )

        names = [n for n in _all_annotations(cls) if not n.startswith("_")]
        values = parts[1:]
        if len(values) != len(names):
            raise ValueError(
                f"تعداد فیلد نامنطبق: {len(values)} مقدار برای {len(names)} فیلد"
            )

        kwargs: dict[str, Any] = {}
        for name, raw in zip(names, values):
            kwargs[name] = _coerce(_all_annotations(cls)[name], raw)
        return cls(**kwargs)

    @classmethod
    def filter(cls, **expected: Any) -> "CallbackFilter":
        """فیلتر آماده برای هندلرها."""
        return CallbackFilter(cls, expected)

    # ---------- نمایش ----------

    def __repr__(self) -> str:
        fields = ", ".join(
            f"{n}={getattr(self, n)!r}"
            for n in _all_annotations(type(self))
            if not n.startswith("_")
        )
        return f"{type(self).__name__}({fields})"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.pack() == other.pack()

    def __hash__(self) -> int:
        return hash(self.pack())


class CallbackFilter:
    """فیلتر داده دکمه، سازگار با Dispatcher و Magic Filter."""

    def __init__(self, data_type: type[CallbackData], expected: dict[str, Any]):
        self.data_type = data_type
        self.expected = expected

    def __call__(self, event: Any) -> bool | dict[str, Any]:
        raw = getattr(event, "data", None)
        if raw is None:
            raw = getattr(event, "callback_data", None)
        if not raw:
            return False

        try:
            parsed = self.data_type.unpack(str(raw))
        except (ValueError, TypeError):
            return False

        for name, want in self.expected.items():
            if getattr(parsed, name, None) != want:
                return False

        # به هندلر پاس داده می‌شود
        return {"callback_data": parsed}

    def __repr__(self) -> str:
        return f"CallbackFilter({self.data_type.__name__}, {self.expected})"


# ---------- کمکی ----------

def _all_annotations(cls: type) -> dict[str, Any]:
    """همه annotation ها، شامل والدها."""
    out: dict[str, Any] = {}
    for base in reversed(cls.__mro__):
        out.update(getattr(base, "__annotations__", {}) or {})
    return out


_TYPE_MAP = {
    "int": int,
    "float": float,
    "bool": bool,
    "str": str,
    "builtins.int": int,
    "builtins.float": float,
    "builtins.bool": bool,
    "builtins.str": str,
}


def _coerce(annotation: Any, raw: str) -> Any:
    """رشته را به تایپ اعلام‌شده تبدیل می‌کند.

    با rom __future__ import annotations تایپ‌ها رشته می‌شوند،
    پس هم شیء تایپ و هم نام رشته‌ای پذیرفته می‌شود.
    """
    target = _TYPE_MAP.get(annotation) if isinstance(annotation, str) else annotation

    if target is int:
        return int(raw)
    if target is float:
        return float(raw)
    if target is bool:
        return raw.lower() in ("1", "true", "yes", "on")
    return raw


__all__ = ["CallbackData", "CallbackFilter"]
