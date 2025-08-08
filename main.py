import os
import asyncio
import logging
import httpx
import time
import traceback
from telegram import Bot
from telegram.constants import ParseMode

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "50"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "15"))
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # ثانیه، پیش‌فرض 300 (۵ دقیقه)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # ۳۰ دقیقه بین پیام عدم پامپ

async def send_error(bot: Bot, err: Exception):
    error_text = f"❌ خطا در ربات:\n<pre>{traceback.format_exc()}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except Exception:
        logger.error("❌ خطا در ارسال پیام خطا به تلگرام")

async def fetch_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    headers = {"X-CoinGecko-Api-Key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h",
        "category": "meme",
    }
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        return resp.json()

async def check_pump(bot: Bot):
    global last_no_pump_alert
    try:
        coins = await fetch_coins()
        found_pump_1h = False
        found_pump_30m = False
        found_pump_15m = False
        now = time.time()

        for coin in coins:
            coin_id = coin.get('id')
            name = coin.get('name')
            symbol = coin.get('symbol', '').upper()
            price = coin.get('current_price', 0)
            volume = coin.get('total_volume', 0) or 0

            if volume < 1:
                continue

            change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
            change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
            change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

            contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"

            exchange_links = f"https://www.coingecko.com/en/coins/{coin_id}"

            if change_1h >= PUMP_THRESHOLD_1H:
                last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                if now - last_alert > CHECK_INTERVAL:
                    announced_coins[f"{coin_id}_1h"] = now
                    message = f"""
🚀 پامپ بالای ۲۰٪ شناسایی شد!
🪙 {name} ({symbol})
📈 رشد ۱ ساعته: {change_1h:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: {contract_address}
🌐 لینک کوین در کوین‌گکو:
{exchange_links}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    found_pump_1h = True

            elif change_30m >= PUMP_THRESHOLD_30M:
                last_alert = announced_coins.get(f"{coin_id}_30m", 0)
                if now - last_alert > CHECK_INTERVAL:
                    announced_coins[f"{coin_id}_30m"] = now
                    message = f"""
⚡ پامپ زیر ۲۰٪ قابل توجه!
🪙 {name} ({symbol})
📈 رشد ۳۰ دقیقه‌ای: {change_30m:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: {contract_address}
🌐 لینک کوین در کوین‌گکو:
{exchange_links}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    found_pump_30m = True

            elif change_15m >= PUMP_THRESHOLD_15M:
                last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                if now - last_alert > CHECK_INTERVAL:
                    announced_coins[f"{coin_id}_15m"] = now
                    message = f"""
⚠️ پامپ احتمالی در حال شکل‌گیری!
🪙 {name} ({symbol})
📈 رشد ۱۵ دقیقه‌ای: {change_15m:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: {contract_address}
🌐 لینک کوین در کوین‌گکو:
{exchange_links}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    found_pump_15m = True

        if not (found_pump_1h or found_pump_30m or found_pump_15m):
            if now - last_no_pump_alert > NO_PUMP_ALERT_COOLDOWN:
                await bot.send_message(chat_id=CHAT_ID, text="ℹ️ پامپی یافت نشد.")
                last_no_pump_alert = now

    except Exception as e:
        await send_error(bot, e)

async def send_heartbeat(bot: Bot):
    while True:
        try:
            await bot.send_message(chat_id=CHAT_ID, text="💓 بات فعال است و در حال اجرا...")
            logger.info("پیام سلامت بات ارسال شد")
        except Exception:
            logger.error("خطا در ارسال پیام سلامت بات")
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
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main_loop())
