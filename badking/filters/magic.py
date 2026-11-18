"""Magic Filter F — الگوبرداری از aiogram ولی قویتر.

مثال:
    F.text == "/start"
    F.text.contains("سلام")
    F.callback_data.startswith("buy:")
    F.from_user.id == 123
    F.photo & F.caption.contains("تخفیف")
"""

from __future__ import annotations

import operator
from typing import Any, Callable


class _Magic:
    """فیلتر با مقایسهها و عملگرهای منطقی زنجیرهای."""

    def __init__(self, path: tuple[str, ...] = (), name: str | None = None):
        self._path = path
        self._name = name

    def __getattr__(self, item: str) -> "_Magic":
        if item.startswith("__"):
            raise AttributeError(item)
        return _Magic(self._path + (item,), item)

    def _resolve(self, obj: Any) -> Any:
        val = obj
        for part in self._path:
            if val is None:
                return None
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = getattr(val, part, None)
        return val

    def __call__(self, obj: Any) -> bool:
        return bool(self._resolve(obj))

    def __eq__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: self._resolve(o) == other)

    def __ne__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: self._resolve(o) != other)

    def __gt__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: _gt(self._resolve(o), other))

    def __ge__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: _ge(self._resolve(o), other))

    def __lt__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: _lt(self._resolve(o), other))

    def __le__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: _le(self._resolve(o), other))

    def __and__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: bool(self(o)) and bool(_as_pred(other)(o)))

    def __or__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: bool(self(o)) or bool(_as_pred(other)(o)))

    def __invert__(self) -> "_Predicate":
        return _Predicate(lambda o: not bool(self(o)))

    def contains(self, value: Any) -> "_Predicate":
        # فقط روی رشتهها معنای «زیررشته» دارد؛ روی سایر انواع(False) برگردان
        # تا استثنا بلعیده نشده و هندلر بیسروصدا رد نشود.
        return _Predicate(lambda o: isinstance(self._resolve(o), str) and value in self._resolve(o))

    def startswith(self, value: str) -> "_Predicate":
        return _Predicate(lambda o: str(self._resolve(o) or "").startswith(value))

    def endswith(self, value: str) -> "_Predicate":
        return _Predicate(lambda o: str(self._resolve(o) or "").endswith(value))

    def is_in(self, values: Any) -> "_Predicate":
        return _Predicate(lambda o: self._resolve(o) in values)

    def __repr__(self) -> str:
        return f"F.{'.'.join(self._path)}" if self._path else "F"


def _gt(a: Any, b: Any) -> bool:
    try:
        return a is not None and a > b
    except TypeError:
        return False


def _ge(a: Any, b: Any) -> bool:
    try:
        return a is not None and a >= b
    except TypeError:
        return False


def _lt(a: Any, b: Any) -> bool:
    try:
        return a is not None and a < b
    except TypeError:
        return False


def _le(a: Any, b: Any) -> bool:
    try:
        return a is not None and a <= b
    except TypeError:
        return False


class _Predicate:
    def __init__(self, fn: Callable[[Any], bool]):
        self.fn = fn

    def __call__(self, obj: Any) -> bool:
        return bool(self.fn(obj))

    def __and__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: self(o) and _as_pred(other)(o))

    def __or__(self, other: Any) -> "_Predicate":
        return _Predicate(lambda o: self(o) or _as_pred(other)(o))

    def __invert__(self) -> "_Predicate":
        return _Predicate(lambda o: not self(o))


def _as_pred(x: Any) -> Callable[[Any], bool]:
    if callable(x):
        return x
    return lambda o: bool(x)


F = _Magic()
