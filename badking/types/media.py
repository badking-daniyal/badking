"""انواع رسانه — منبع: docs.bale.ai (PhotoSize, Animation, Audio, Document, Video, Voice, Contact, Location, File)"""

from __future__ import annotations

from .common import BaleModel


class PhotoSize(BaleModel):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: int | None = None


class Animation(BaleModel):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumb: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class Audio(BaleModel):
    file_id: str
    file_unique_id: str
    duration: int
    performer: str | None = None
    title: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class Document(BaleModel):
    file_id: str
    file_unique_id: str
    thumb: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class Video(BaleModel):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumb: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class Voice(BaleModel):
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


class Contact(BaleModel):
    phone_number: str
    first_name: str
    last_name: str | None = None
    user_id: int | None = None
    vcard: str | None = None


class Location(BaleModel):
    longitude: float
    latitude: float
    horizontal_accuracy: float | None = None
    live_period: int | None = None
    heading: int | None = None
    proximity_alert_radius: int | None = None


class File(BaleModel):
    file_id: str
    file_unique_id: str
    file_size: int | None = None
    file_path: str | None = None

    def download_url(self, token: str, base_url: str = "https://tapi.bale.ai") -> str:
        """آدرس دانلود فایل: <base_url>/file/bot<token>/<file_path>"""
        if not self.file_path:
            raise ValueError("file_path موجود نیست")
        return f"{base_url.rstrip('/')}/file/bot{token}/{self.file_path}"
