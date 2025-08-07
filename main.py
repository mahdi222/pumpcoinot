import os
import time
import telegram

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = telegram.Bot(token=TOKEN)

def send_heartbeat():
    bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب Railway فعال است.")

if __name__ == "__main__":
    while True:
        try:
            send_heartbeat()
            time.sleep(3600)  # هر 1 ساعت یک پیام تست می‌فرسته
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)
