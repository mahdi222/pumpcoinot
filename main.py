import telegram
import time

import os

TOKEN = os.getenv("8296961071:AAEWjoANG7T00w0-svmSyIVM4vSosOjgdB4
")
CHAT_ID = os.getenv("610160171")

bot = telegram.Bot(token=TOKEN)

while True:
    bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب Railway فعال است.")
    time.sleep(3600)  # هر 1 ساعت یه پیام تست می‌فرسته
