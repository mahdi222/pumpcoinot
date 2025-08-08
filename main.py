import asyncio
import logging
import aiohttp
import time
import os
import traceback
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_error(bot: Bot, err: Exception):
    error_text = f"❌ خطا:\n<pre>{traceback.format_exc()}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام خطا به تلگرام: {e}")

async def check_pump(bot: Bot):
    logger.info("check_pump داره اجرا میشه...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme",
        "order": "market_cap_desc",
        "per_page": 5,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                coins = await response.json()
                logger.info(f"{len(coins)} تا کوین دریافت شد")

                if not isinstance(coins, list):
                    raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")

                msg = "📊 تست اتصال API و وضعیت کوین‌ها:\n\n"
                for coin in coins:
                    name = coin.get('name', 'N/A')
                    symbol = coin.get('symbol', 'N/A').upper()
                    change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
                    change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
                    change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
                    volume = coin.get("total_volume") or 0
                    msg += f"{name} ({symbol}): 15m={change_15m:.2f}%, 30m={change_30m:.2f}%, 1h={change_1h:.2f}%, حجم: {volume}\n"

                await bot.send_message(chat_id=CHAT_ID, text=msg)
                logger.info("پیام وضعیت کوین‌ها ارسال شد")

    except Exception as e:
        logger.error(f"خطا در check_pump: {e}")
        await send_error(bot, e)

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات شروع به کار کرد")
    logger.info("ربات شروع به کار کرد")

    while True:
        await check_pump(bot)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
