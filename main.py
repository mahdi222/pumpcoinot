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
PUMP_THRESHOLD_1H = 50   # رشد ۱ ساعت برای پامپ اصلی
PUMP_THRESHOLD_15M = 5   # رشد ۱۵ دقیقه برای پامپ احتمالی
PUMP_COOLDOWN = 60 * 60  # یک ساعت برای هر هشدار

async def send_error(bot: Bot, err: Exception):
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
        "price_change_percentage": "15m,1h"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                coins = await response.json()

                if not isinstance(coins, list):
                    raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")

                found_pump = False
                found_pump_alert = False

                now = time.time()

                for coin in coins:
                    if not isinstance(coin, dict):
                        continue

                    coin_id = coin['id']
                    name = coin['name']
                    symbol = coin['symbol'].upper()
                    price = coin['current_price']
                    change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
                    change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

                    # پامپ اصلی
                    if change_1h >= PUMP_THRESHOLD_1H:
                        last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_1h"] = now
                            message = f"""
🚀 پامپ شدید شناسایی شد!
<b>{name} ({symbol})</b>
📈 رشد ۱ ساعته: <b>{change_1h:.2f}%</b>
💰 قیمت فعلی: ${price}
🔗 <a href="https://www.coingecko.com/en/coins/{coin_id}">مشاهده در CoinGecko</a>
"""
                            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                            found_pump = True

                    # پامپ احتمالی
                    elif change_15m >= PUMP_THRESHOLD_15M:
                        last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_15m"] = now
                            message = f"""
⚠️ پامپ احتمالی در حال شکل‌گیری!
<b>{name} ({symbol})</b>
📈 رشد ۱۵ دقیقه‌ای: <b>{change_15m:.2f}%</b>
💰 قیمت فعلی: ${price}
🔗 <a href="https://www.coingecko.com/en/coins/{coin_id}">مشاهده در CoinGecko</a>
"""
                            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                            found_pump_alert = True

                if not found_pump and not found_pump_alert:
                    await bot.send_message(chat_id=CHAT_ID, text="ℹ️ پامپی یافت نشد.")

    except Exception as e:
        await send_error(bot, e)

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب دو مرحله‌ای شروع به کار کرد.")
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
