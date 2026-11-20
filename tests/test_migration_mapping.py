"""تست migration/mappings.json — نگاشت باید با کد واقعی هماهنگ باشد.

سند مأموریت میگوید: «هیچ برتری ساختگی یا ادعای تأییدنشده ثبت نکن.»
این تست آن را عملی میکند: هر هدفی که در فایل نگاشت هست باید واقعاً
در BADKING وجود داشته باشد.
"""

from __future__ import annotations

import json
from pathlib import Path

import badking
from badking.compat import IMPORT_MAP, METHOD_MAP, UNSUPPORTED
from badking.hybrid import SelfBot

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "migration" / "mappings.json"


def load():
    return json.loads(MAPPING.read_text(encoding="utf-8"))


def test_mapping_file_exists():
    assert MAPPING.is_file()


def test_valid_statuses():
    data = load()
    valid = set(data["statuses"])
    for section in ("imports", "methods", "self_bot", "unsupported"):
        for item in data[section]:
            assert item["status"] in valid, f"{item['source']}: {item['status']}"


def test_every_target_exists():
    """هر هدف نگاشت باید در کد واقعی باشد."""
    data = load()

    for item in data["imports"]:
        target = item["target"].split(".")[-1]
        assert hasattr(badking, target), f"{item['source']} → badking.{target} وجود ندارد"

    for item in data["methods"]:
        target = item["target"].split(".")[-1]
        # متدهای message روی Message، متدهای bot روی Bot
        if item["source"].startswith("message.answer"):
            if target == "reply":
                from badking import Message
                assert hasattr(Message, target)
            else:
                from badking import Bot
                assert hasattr(Bot, target), f"Bot.{target} وجود ندارد"
        elif item["source"] == "message.delete":
            from badking import Message
            assert hasattr(Message, "delete")


def test_self_bot_targets_exist():
    data = load()
    from badking.hybrid import SessionManager

    for item in data["self_bot"]:
        target = item["target"]
        if "SelfBot(" in target:
            continue  # کلاس است
        # هدف ممکن است چند متد باشد: "leave_by_id / leave_group"
        methods = [m.strip().rstrip("()") for m in target.split("/")]
        for method in methods:
            if "." in method:  # هدف کلاس دیگری را مشخص میکند
                cls_name, method = method.split(".")[-2:]
                cls = {"SessionManager": SessionManager, "SelfBot": SelfBot}[cls_name]
                assert hasattr(cls, method), f"{cls_name}.{method} وجود ندارد"
            elif method in {"request_code", "submit_code"}:
                assert hasattr(SessionManager, method), f"SessionManager.{method} وجود ندارد"
            else:
                assert hasattr(SelfBot, method), f"SelfBot.{method} وجود ندارد"


def test_unsupported_match_code():
    """لیست UNSUPPORTED در فایل باید با کد compat هماهنگ باشد."""
    data = load()
    file_names = {item["source"].split(".")[-1] for item in data["unsupported"]}
    assert file_names == set(UNSUPPORTED)


def test_import_map_matches_code():
    data = load()
    file_map = {
        item["source"].split(".")[-1]: item["target"].split(".")[-1]
        for item in data["imports"]
    }
    for source, target in IMPORT_MAP.items():
        assert file_map.get(source) == target, f"نگاشت {source} ناهماهنگ است"


def test_method_map_matches_code():
    data = load()
    file_map = {
        item["source"].replace("message.", ""): item["target"].split(".")[-1]
        for item in data["methods"]
    }
    for source, target in METHOD_MAP.items():
        if source in file_map:
            assert file_map[source] == target, f"نگاشت متد {source} ناهماهنگ است"


def test_all_entries_have_test_reference():
    data = load()
    for section in ("imports", "methods", "self_bot", "unsupported"):
        for item in data[section]:
            assert item.get("test"), f"{item['source']} تست ندارد"


def test_no_fake_claims():
    """هیچ ورودی نباید هدف خالی با وضعیت سازگار داشته باشد."""
    data = load()
    for section in ("imports", "methods", "self_bot"):
        for item in data[section]:
            assert item["target"], f"{item['source']} هدف ندارد"
            assert item["status"] != "UNSUPPORTED"
