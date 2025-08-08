import os
import asyncio
import httpx
import html
import logging
from telegram import Bot

# فعال کردن لاگ‌ها
logging.basicConfig(level=logging.INFO)

# متغیرهای محیطی
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PUMP_THRESHOLD = float(os.getenv("PUMP_THRESHOLD", 0.5))

# ساخت بات تلگرام
bot = Bot(token=TELEGRAM_TOKEN)

# تابع ارسال پیام عادی
async def send_telegram(message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {e}")

# تابع ارسال پیام خطا (با escape HTML)
async def send_error(error_text):
    safe_text = html.escape(str(error_text))
    await send_telegram(f"⚠️ خطا:\n{safe_text}")

# تابع بررسی پامپ
async def check_pump():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "1h"
            }
            r = await client.get(url, params=params)
            data = r.json()

            # اگر داده لیست نبود، ارور بده
            if not isinstance(data, list):
                await send_error(f"❌ خروجی API لیست نیست!\n\n📦 نوع داده: {type(data)}\n\n📄 محتوای برگشتی:\n{data}")
                return

            for coin in data:
                change_1h = coin.get("price_change_percentage_1h_in_currency")
                if change_1h is not None and change_1h >= PUMP_THRESHOLD:
                    message = (
                        f"🚀 پامپ شناسایی شد!\n"
                        f"🪙 کوین: {coin['name']} ({coin['symbol'].upper()})\n"
                        f"📈 تغییر 1ساعت: {change_1h:.2f}%\n"
                        f"💰 قیمت: ${coin['current_price']}"
                    )
                    await send_telegram(message)

    except Exception as e:
        await send_error(f"❌ خطای غیرمنتظره در check_pump:\n{str(e)}")

# تابع اصلی
async def main():
    await send_telegram("✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.\n💓 بات فعال است و در حال اجرا...")
    while True:
        await check_pump()
        await asyncio.sleep(60)  # هر 1 دقیقه بررسی

if __name__ == "__main__":
    asyncio.run(main())
