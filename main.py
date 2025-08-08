import os
import asyncio
import logging
import httpx
import time
import traceback
from telegram import Bot
from telegram.constants import ParseMode

# متغیرهای محیطی
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "50"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "15"))
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))

# تنظیمات
PUMP_COOLDOWN = 60 * 60  # 1 ساعت بین هشدارهای یک کوین
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # 30 دقیقه بین پیام "پامپی یافت نشد"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PumpFinderBot/1.0"
}

async def send_error(bot: Bot, err: Exception):
    error_text = f"❌ خطا در ربات:\n<pre>{traceback.format_exc()}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام خطا به تلگرام: {e}")

async def fetch_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h",
    }
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        coins = resp.json()
        if not isinstance(coins, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")
        return coins

async def check_pump(bot: Bot):
    global last_no_pump_alert
    try:
        coins = await fetch_coins()
        now = time.time()
        found_pump_1h = False
        found_pump_30m = False
        found_pump_15m = False

        for coin in coins:
            coin_id = coin.get('id')
            name = coin.get('name')
            symbol = coin.get('symbol', '').upper()
            price = coin.get('current_price')
            volume = coin.get('total_volume', 0) or 0

            change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
            change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
            change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

            # فیلتر حجم کم
            if volume < 1:
                continue

            # پامپ بالای 1 ساعت
            if change_1h >= PUMP_THRESHOLD_1H:
                last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_1h"] = now
                    message = f"""
🚀 پامپ بالای ۲۰٪ شناسایی شد!
🪙 {name} ({symbol})
📈 رشد ۱ ساعته: {change_1h:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: ندارد
🌐 لینک کوین در کوین‌گکو:
https://www.coingecko.com/en/coins/{coin_id}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    logger.info(f"پامپ بالای ۲۰٪: {name} {change_1h:.2f}%")
                    found_pump_1h = True

            # پامپ ۳۰ دقیقه ای (بین ۱۵ تا ۲۰ درصد)
            elif change_30m >= PUMP_THRESHOLD_30M:
                last_alert = announced_coins.get(f"{coin_id}_30m", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_30m"] = now
                    message = f"""
⚡ پامپ زیر ۲۰٪ شناسایی شد!
🪙 {name} ({symbol})
📈 رشد ۳۰ دقیقه‌ای: {change_30m:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: ندارد
🌐 لینک کوین در کوین‌گکو:
https://www.coingecko.com/en/coins/{coin_id}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    logger.info(f"پامپ زیر ۲۰٪: {name} {change_30m:.2f}%")
                    found_pump_30m = True

            # پامپ ۱۵ دقیقه ای (کمتر از ۱۵ درصد)
            elif change_15m >= PUMP_THRESHOLD_15M:
                last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_15m"] = now
                    message = f"""
⚠️ پامپ احتمالی شناسایی شد!
🪙 {name} ({symbol})
📈 رشد ۱۵ دقیقه‌ای: {change_15m:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: ندارد
🌐 لینک کوین در کوین‌گکو:
https://www.coingecko.com/en/coins/{coin_id}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    logger.info(f"پامپ احتمالی: {name} {change_15m:.2f}%")
                    found_pump_15m = True

        if not found_pump_1h and not found_pump_30m and not found_pump_15m:
            if now - last_no_pump_alert > NO_PUMP_ALERT_COOLDOWN:
                await bot.send_message(chat_id=CHAT_ID, text="ℹ️ پامپی یافت نشد.")
                logger.info("هیچ پامپی یافت نشد.")
                last_no_pump_alert = now

    except Exception as e:
        await send_error(bot, e)

async def send_heartbeat(bot: Bot):
    while True:
        try:
            await bot.send_message(chat_id=CHAT_ID, text="💓 بات فعال است و در حال اجرا...")
            logger.info("پیام سلامت بات ارسال شد")
        except Exception as e:
            logger.error(f"خطا در ارسال پیام سلامت بات: {e}")
        await asyncio.sleep(300)  # هر 5 دقیقه یکبار

async def main_loop():
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    logger.info("ربات شروع به کار کرد")

    await asyncio.gather(
        run_check_pump_loop(bot),
        send_heartbeat(bot),
    )

async def run_check_pump_loop(bot: Bot):
    while True:
        logger.info("check_pump داره اجرا میشه...")
        await check_pump(bot)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
