import asyncio
from telegram import Bot
import traceback

import os
BOT_TOKEN = 8296961071:AAEWjoANG7T00w0-svmSyIVM4vSosOjgdB4
CHAT_ID = 610160171



async def test():
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text="✅ تست موفق! ربات وصل شد.")
        print("پیام ارسال شد ✅")
    except Exception as e:
        print("❌ خطا:")
        traceback.print_exc()

asyncio.run(test())
