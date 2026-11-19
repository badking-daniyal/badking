"""Enum های پروتکل بله.

هر عددی که در RPC ها معنا دارد اینجاست، نه پراکنده در کد. اگر بله معنای
عددی را عوض کرد، فقط همین فایل تغییر می‌کند.

    from badking.enums import PeerType, ChatType, TypingMode

    await bot.send_typing(peer, mode=TypingMode.SENDINGPHOTO)
"""

from __future__ import annotations

from enum import IntEnum


class PeerType(IntEnum):
    """نوع peer در پروتکل. فیلد ۱ هر Peer."""

    UNKNOWN = 0
    PRIVATE = 1
    """کاربر یا ربات."""
    GROUP = 2
    """گروه یا کانال."""


class ChatType(IntEnum):
    """نوع چت. فیلد ۱ هر Chat."""

    UNKNOWN = 0
    PRIVATE = 1
    GROUP = 2
    CHANNEL = 3
    BOT = 4
    SUPER_GROUP = 5


class GroupType(IntEnum):
    """نوع گروه در CreateGroup."""

    GROUP = 0
    CHANNEL = 1
    SUPERGROUP = 2


class ListLoadMode(IntEnum):
    """جهت بارگذاری تاریخچه. فیلد ۴ LoadHistory."""

    UNKNOWN = 0
    FORWARD = 1
    BACKWARD = 2
    BOTH = 3


class TypingMode(IntEnum):
    """نوع تایپ. فیلد ۳ presence.Typing."""

    UNKNOWN = 0
    TEXT = 1
    VOICERECORDING = 2
    SENDINGVOICE = 3
    SENDINGFILE = 4
    SENDINGPHOTO = 5
    SENDINGVIDEO = 6
    SENDINGMUSIC = 7
    CHOOSINGSTICKER = 8
    CHOOSINGGIF = 9
    CREATINGGIFTPACKET = 10
    SENDINGALBUM = 11
    CHOOSINGEMOJI = 12

    # نام‌های جایگزین که در کلاینت رسمی هم دیده می‌شوند
    VOICERECODRING = 2
    CHOSINGGIF = 9
    CHOSINGEMOJI = 12


class SendType(IntEnum):
    """نوع فایل در GetNasimFileUploadUrl."""

    UNKNOWN = 0
    PHOTO = 1
    VIDEO = 2
    VOICE = 3
    GIF = 4
    AUDIO = 5
    DOCUMENT = 6
    STICKER = 7
    CROWDFUNDING = 8


class PrivacyMode(IntEnum):
    """حالت حریم خصوصی."""

    UNKNOWN = 0
    NONE = 1
    SPAM = 2


class Restriction(IntEnum):
    """دسترسی گروه: خصوصی یا عمومی."""

    PRIVATE = 0
    PUBLIC = 1


class ReportKind(IntEnum):
    """دلیل گزارش محتوا."""

    UNKNOWN = 0
    SCAM = 1
    INAPPROPRIATE_CONTENT = 2
    OTHER = 3
    VIOLENCE = 4
    SPAM = 5
    FALSE_INFORMATION = 6


class GivingType(IntEnum):
    """نحوه تقسیم بسته هدیه."""

    SAME = 0
    RANDOM = 1


class GiftOpenning(IntEnum):
    """نتیجه باز کردن بسته هدیه."""

    ALREADY_RECEIVED = 0
    SOLD_OUT = 1
    GIFT_CREATOR = 2
    SUCCESSFUL = 3
    PENDING = 4


# نام جایگزین، همان‌طور که در کلاینت رسمی نوشته شده
GiftOpening = GiftOpenning


class PeerSource(IntEnum):
    """منبع پیدا شدن peer."""

    UNKNOWN = 0
    DIALOGS = 1
    VITRINE = 2
    MARKET = 3
    PRIVACY_BAR = 4


class SendCodeType(IntEnum):
    """روش ارسال کد ورود."""

    UNKNOWN = 0
    DEFAULT = 1
    BALEONLY = 2
    SMS = 3
    CALL = 4
    EMAIL = 5
    MISSCALL = 6
    SETUP_EMAIL_REQUIRED = 7
    WHATSAPP = 8
    TELEGRAM = 9
    USSD = 10
    FUTURE_AUTH_TOKEN = 11
    TELEGRAM_GATEWAY = 12


class AuthErrors(IntEnum):
    """خطاهای احراز هویت. سرور این عدد را برمی‌گرداند."""

    UNKNOWN = 0
    NUMBER_BANNED = 1
    AUTH_LIMIT = 2
    WRONG_CODE = 3
    PASSWORD_NEEDED = 4
    SIGN_UP_NEEDED = 5
    WRONG_PASSWORD = 6
    RATE_LIMIT = 7
    INVALID = 8


__all__ = [
    "AuthErrors",
    "ChatType",
    "GiftOpenning",
    "GiftOpening",
    "GivingType",
    "GroupType",
    "ListLoadMode",
    "PeerSource",
    "PeerType",
    "PrivacyMode",
    "ReportKind",
    "Restriction",
    "SendCodeType",
    "SendType",
    "TypingMode",
]
