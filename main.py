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
last_no_pump_alert = 0
NO_PUMP_ALERT_COOLDOWN = 60 * 5  # 5 دقیقه بین پیام "پامپی یافت نشد"

PUMP_THRESHOLD_1H = 50   # رشد ۱ ساعت برای پامپ اصلی
PUMP_THRESHOLD_30M = 15  # رشد ۳۰ دقیقه برای پامپ متوسط
PUMP_THRESHOLD_15M = 0.5   # رشد ۱۵ دقیقه برای پامپ احتمالی (مثال)

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
        "price_change_percentage": "15m,30m,1h",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                coins = await response.json()

                if not isinstance(coins, list):
                    raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")

                found_pump = False
                found_pump_alert = False
                found_pump_mid = False

                now = time.time()

                for coin in coins:
                    if not isinstance(coin, dict):
                        continue

                    coin_id = coin['id']
                    name = coin['name']
                    symbol = coin['symbol'].upper()
                    price = coin['current_price']
                    volume = coin.get("total_volume") or 0

                    # مقداردهی پیش‌فرض در صورت None بودن مقادیر درصد تغییر قیمت
                    change_15m = coin.get("price_change_percentage_15m_in_currency")
                    if change_15m is None:
                        change_15m = 0.0
                    change_30m = coin.get("price_change_percentage_30m_in_currency")
                    if change_30m is None:
                        change_30m = 0.0
                    change_1h = coin.get("price_change_percentage_1h_in_currency")
                    if change_1h is None:
                        change_1h = 0.0

                    # پامپ اصلی
                    if change_1h >= PUMP_THRESHOLD_1H:
                        last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_1h"] = now
                            message = f"""
🚀 پامپ شدید شناسایی شد!
<b>{name} ({symbol})</b>
📈 رشد ۱ ساعته: <b>{change_1h:.2f}%</b>
💰 قیمت ف
