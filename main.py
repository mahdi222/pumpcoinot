import asyncio
from telegram import Bot

import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def test():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ تست موفق! ربات وصل شد.")

asyncio.run(test())
