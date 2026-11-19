"""مهاجرت از aiobale به BADKING.

هدف: پروژه‌ای که با aiobale نوشته شده، بدون بازنویسی از صفر.

    # اول ببین چه چیزی عوض می‌شود — چیزی نوشته نمی‌شود
    python 24_migrate.py --dry-run

    # بعد واقعاً تبدیل کن
    python 24_migrate.py

    # یا از CLI:
    badking migrate . --dry-run

قاعده صادقانه: هر چیزی که خودکار تبدیل نشود، در گزارش می‌آید. هیچ
تبدیلی حدس زده نمی‌شود.
"""

import argparse
import asyncio
import json
from pathlib import Path

from badking.compat import migrate_directory, migrate_file, migration_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="مهاجرت از aiobale")
    parser.add_argument("path", nargs="?", default=".", help="فایل یا پوشه")
    parser.add_argument("--dry-run", action="store_true", help="فقط گزارش")
    parser.add_argument("--no-backup", action="store_true", help="بدون نسخه پشتیبان")
    parser.add_argument("--json", action="store_true", help="خروجی JSON")
    args = parser.parse_args()

    path = Path(args.path)
    backup = not args.no_backup

    if path.is_file():
        reports = [migrate_file(path, dry_run=args.dry_run, backup=backup)]
    elif path.is_dir():
        reports = migrate_directory(path, dry_run=args.dry_run, backup=backup)
    else:
        print(f"پیدا نشد: {path}")
        return

    if args.json:
        print(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2))
        return

    for report in reports:
        if report.changes or report.needs_manual_work or not report.ok:
            print(report.summary())
            print()

    print(migration_summary(reports))

    if args.dry_run:
        print("\n(حالت آزمایشی — چیزی نوشته نشد)")


if __name__ == "__main__":
    main()
