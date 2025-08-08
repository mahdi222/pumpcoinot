import os
import asyncio
import httpx
import html
import logging
from telegram import Bot

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PUMP_THRESHOLD = float(os.getenv("PUMP_THRESHOLD", 0.5))

async def send_telegram(bot: Bot, message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {e}")

async def send_error(bot: Bot, error_text):
    safe_text = html.escape(str(error_text))
    await send_telegram(bot, f"⚠️ خطا:\n{safe_text}")

async def check_pump(bot: Bot):
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

            if not isinstance(data, list):
                await send_error(bot, f"❌ خروجی API لیست نیست!\n\nنوع داده: {type(data)}\n\n{data}")
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
                    await send_telegram(bot, message)

    except Exception as e:
        await send_error(bot, f"❌ خطای غیرمنتظره در check_pump:\n{str(e)}")

async def main():
    if not TELEGRAM_TOKEN:
        print("خطا: متغیر محیطی TELEGRAM_TOKEN تعریف نشده یا خالی است!")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    await send_telegram(bot, "✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.\n💓 بات فعال است و در حال اجرا...")
    while True:
        await check_pump(bot)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
