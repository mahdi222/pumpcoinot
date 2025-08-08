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

announced_coins = {}
PUMP_THRESHOLD = 50
PUMP_COOLDOWN = 60 * 60

async def send_error(bot: Bot, err: Exception):
    """ارسال خطا به تلگرام با traceback کامل"""
    error_text = f"❌ خطا:\n<pre>{traceback.format_exc()}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except:
        logger.error("❌ خطا در ارسال پیام خطا به تلگرام")

async def check_pump(bot: Bot):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                coins = await response.json()

                # بررسی اینکه خروجی واقعا لیست کوین‌هاست
                if not isinstance(coins, list):
                    raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}\nمقدار: {coins}")

                found_pump = False

                for coin in coins:
                    if not isinstance(coin, dict):
                        raise ValueError(f"ساختار کوین نامعتبر است: {coin}")

                    coin_id = coin['id']
                    change = coin.get("price_change_percentage_1h_in_currency")

                    if not change or change < PUMP_THRESHOLD:
                        continue

                    now = time.time()
                    last_alert_time = announced_coins.get(coin_id, 0)

                    if now - last_alert_time < PUMP_COOLDOWN:
                        continue

                    announced_coins[coin_id] = now

                    message = f"""
🚀 پامپ شدید شناسایی شد!
<b>{coin['name']} ({coin['symbol'].upper()})</b>
📈 رشد ۱ ساعته: <b>{change:.2f}%</b>
💰 قیمت فعلی: ${coin['current_price']}
🔗 <a href="https://www.coingecko.com/en/coins/{coin['id']}">مشاهده در CoinGecko</a>
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    found_pump = True

                if not found_pump:
                    await bot.send_message(chat_id=CHAT_ID, text="ℹ️ پامپی یافت نشد.")

    except Exception as e:
        await send_error(bot, e)

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب شروع به کار کرد.")
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
