import telegram
import time

TOKEN = "توکن باتت"
CHAT_ID = "آی‌دی عددی تلگرامت"

bot = telegram.Bot(token=TOKEN)

while True:
    bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب Railway فعال است.")
    time.sleep(3600)  # هر 1 ساعت یه پیام تست می‌فرسته
