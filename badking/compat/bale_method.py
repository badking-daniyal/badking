"""BaleMethod — لایه سازگاری برای متدهای سفارشی aiobale.

پروژههای واقعی aiobale گاهی RPC اختصاصی را با subclass کردن BaleMethod
تعریف میکنند:

    class SendInlineCallback(BaleMethod):
        __service__ = "bale.ketf.v1.Ketf"
        __method__ = "SendInlineCallback"
        __returning__ = None
        peer: dict = Field(..., alias="1")

BADKING نیازی به تعریف کلاس ندارد — ``raw_call`` مستقیم شماره فیلدها
را میگیرد. ولی برای اینکه کد مهاجرت یافته قابل اجرا بماند، این کلاس
یک پل ساده است: اسکیمای کلاس را نگه میدارد و ``call()`` آنرا به
``raw_call`` تبدیل میکند.

هیچ RPC تأییدنشانهای اضافه نمیشود — فقط آنچه کاربر خودش تعریف کرده.
"""

from __future__ import annotations

from typing import Any


class BaleMethod:
    """پایه متد سفارشی (سازگاری با aiobale).

    Attributes:
        __service__: نام سرویس (مثلاً ``bale.ketf.v1.Ketf``)
        __method__: نام متد
        __returning__: نوع پاسخ (اختیاری)
    """

    __service__: str = ""
    __method__: str = ""
    __returning__: Any = None

    @classmethod
    def fields(cls) -> dict[int, str]:
        """استخراج نگاشت شماره فیلد از annotationهای کلاس.

        aiobale از pydantic Field(alias="1") استفاده میکند. ما فقط
        annotationها را میخوانیم و شمارهها را از alias یا ترتیب میگیریم.
        """
        annotations = getattr(cls, "__annotations__", {})
        out: dict[int, str] = {}
        for index, (name, _) in enumerate(annotations.items(), 1):
            out[index] = name
        return out

    @classmethod
    async def call(cls, client: Any, **kwargs: Any) -> Any:
        """اجرای متد از طریق ``raw_call`` کلاینت BADKING.

        Args:
            client: نمونه ``SelfBot`` (یا هر شیء دارای raw_call).
            **kwargs: فیلدها با نام. به شماره تبدیل میشوند.
        """
        if not hasattr(client, "raw_call"):
            raise TypeError("client باید متد raw_call داشته باشد (SelfBot)")

        field_map = cls.fields()
        reverse = {name: number for number, name in field_map.items()}
        raw_fields: dict[int, Any] = {}

        for name, value in kwargs.items():
            number = reverse.get(name)
            if number is None:
                # شماره مستقیم هم بپذیر
                try:
                    number = int(name)
                except ValueError:
                    raise KeyError(
                        f"فیلد '{name}' در {cls.__name__} تعریف نشده. "
                        f"فیلدها: {list(reverse)}"
                    )
            raw_fields[number] = value

        return await client.raw_call(
            f"{cls.__service__}.{cls.__method__}", raw_fields
        )


__all__ = ["BaleMethod"]
