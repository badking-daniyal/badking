"""فرم چندمرحله‌ای با FSM.

هدف: مکالمه‌ای که چند سؤال می‌پرسد و جواب‌ها را نگه می‌دارد.

    python 03_form.py
"""

import asyncio
import os

from badking import Bot, F, FSMContext, MemoryStorage, State, StatesGroup


class Registration(StatesGroup):
    name = State()
    age = State()
    city = State()


async def main() -> None:
    bot = Bot(os.environ["BADKING_TOKEN"], storage=MemoryStorage())

    @bot.on_message(F.text == "/register")
    async def start(message, state: FSMContext):
        await state.set_state(Registration.name)
        await message.reply("اسمت چیه؟")

    @bot.on_message(Registration.name, F.text)
    async def got_name(message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await state.set_state(Registration.age)
        await message.reply("چند سالته؟")

    @bot.on_message(Registration.age, F.text)
    async def got_age(message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (5 <= int(text) <= 120):
            await message.reply("یک عدد بین ۵ تا ۱۲۰ بفرست.")
            return  # در همان حالت می‌مانیم

        await state.update_data(age=int(text))
        await state.set_state(Registration.city)
        await message.reply("کدام شهر؟")

    @bot.on_message(Registration.city, F.text)
    async def got_city(message, state: FSMContext):
        await state.update_data(city=message.text.strip())
        data = await state.get_data()

        await message.reply(
            "ثبت شد:\n"
            f"نام: {data['name']}\n"
            f"سن: {data['age']}\n"
            f"شهر: {data['city']}"
        )
        await state.clear()  # پاک کردن، وگرنه در همان حالت می‌ماند

    @bot.on_message(F.text == "/cancel")
    async def cancel(message, state: FSMContext):
        await state.clear()
        await message.reply("لغو شد.")

    print("ربات روشن شد. /register را بزن.")
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
