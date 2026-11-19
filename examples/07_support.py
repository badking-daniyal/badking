"""پشتیبانی مشتری: صف تیکت با SQLite.

هدف: کاربر تیکت بزند، ادمین جواب بدهد، همه چیز ذخیره شود.

    python 07_support.py

دیتابیس خودش ساخته می‌شود: tickets.db
"""

import asyncio
import os
import sqlite3
from datetime import datetime

from badking import Bot, F

DB = "tickets.db"
ADMIN_ID = 123456789  # شناسه خودت


def setup_db() -> None:
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            subject TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            from_admin INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def create_ticket(user_id: int, username: str | None, subject: str) -> int:
    conn = sqlite3.connect(DB)
    cur = conn.execute(
        "INSERT INTO tickets (user_id, username, subject, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, subject, datetime.now().isoformat()),
    )
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ticket_id


def add_reply(ticket_id: int, from_admin: bool, text: str) -> None:
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO replies (ticket_id, from_admin, text, created_at) VALUES (?, ?, ?, ?)",
        (ticket_id, int(from_admin), text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_ticket(ticket_id: int) -> tuple | None:
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id, user_id, subject, status FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()
    conn.close()
    return row


def open_tickets() -> list[tuple]:
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT id, user_id, subject FROM tickets WHERE status = 'open' ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def close_ticket(ticket_id: int) -> None:
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()


async def main() -> None:
    setup_db()
    bot = Bot(os.environ["BADKING_TOKEN"])

    @bot.on_message(F.text == "/new")
    async def new_ticket(message):
        subject = message.text.replace("/new", "").strip()
        if not subject:
            await message.reply("موضوع را بنویس:\n/new مشکل در پرداخت")
            return

        ticket_id = create_ticket(
            message.from_user.id, message.from_user.username, subject
        )
        await message.reply(
            f"تیکت #{ticket_id} ثبت شد.\n"
            "هر پیامی بفرستی به این تیکت اضافه می‌شود."
        )

    @bot.on_message(F.text == "/tickets")
    async def list_tickets(message):
        if message.from_user.id != ADMIN_ID:
            return

        rows = open_tickets()
        if not rows:
            await message.reply("تیکت بازی نیست.")
            return

        lines = [f"#{tid} — {subject}" for tid, _, subject in rows]
        await message.reply("تیکت‌های باز:\n" + "\n".join(lines))

    @bot.on_message(F.text == "/close")
    async def close(message):
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.reply("/close 12")
            return

        ticket_id = int(parts[1])
        close_ticket(ticket_id)
        await message.reply(f"تیکت #{ticket_id} بسته شد.")

    @bot.on_message(F.text, ~F.text.startswith("/"))
    async def route_message(message):
        """پیام عادی: اگر ادمین است، جواب تیکت؛ وگرنه پیام جدید."""
        if message.from_user.id == ADMIN_ID:
            # ادمین با ریپلای جواب می‌دهد
            if not message.reply_to_message:
                return
            # در پیام ریپلای‌شده دنبال #شماره بگرد
            original = message.reply_to_message.text or ""
            if "#" not in original:
                return
            try:
                ticket_id = int(original.split("#")[1].split()[0])
            except (IndexError, ValueError):
                return

            row = get_ticket(ticket_id)
            if not row:
                return

            add_reply(ticket_id, True, message.text)
            await bot.send_message(
                row[1], f"پاسخ تیکت #{ticket_id}:\n{message.text}"
            )
            return

        # کاربر عادی: پیام به آخرین تیکت بازش اضافه می‌شود
        conn = sqlite3.connect(DB)
        row = conn.execute(
            "SELECT id FROM tickets WHERE user_id = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
            (message.from_user.id,),
        ).fetchone()
        conn.close()

        if not row:
            await message.reply("تیکت بازی نداری. /new بزن.")
            return

        ticket_id = row[0]
        add_reply(ticket_id, False, message.text)

        await bot.send_message(
            ADMIN_ID,
            f"پیام جدید در تیکت #{ticket_id}\n"
            f"از {message.from_user.first_name}:\n\n{message.text}",
        )
        await message.reply("به تیکت اضافه شد.")

    print("ربات پشتیبانی روشن شد.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
