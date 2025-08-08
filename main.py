import os
import asyncio
import logging
import httpx
from telegram import Bot
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت متغیرهای محیطی بدون تغییر نام
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "0"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "0"))
VOLUME_MIN = float(os.getenv("VOLUME_MIN", "0"))
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "300"))  # ثانیه، پیش فرض ۵ دقیقه

# لاگ مقادیر محیطی برای دیباگ
logger.info(f"CHAT_ID: {CHAT_ID}")
logger.info(f"COINGECKO_API_KEY: {'set' if COINGECKO_API_KEY else 'not set'}")
logger.info(f"ETHERSCAN_API_KEY: {'set' if ETHERSCAN_API_KEY else 'not set'}")
logger.info(f"HELIUS_API_KEY: {'set' if HELIUS_API_KEY else 'not set'}")
logger.info(f"TELEGRAM_TOKEN: {'set' if TELEGRAM_TOKEN else 'not set'}")
logger.info(f"PUMP_THRESHOLD_15M: {PUMP_THRESHOLD_15M}")
logger.info(f"PUMP_THRESHOLD_30M: {PUMP_THRESHOLD_30M}")
logger.info(f"PUMP_THRESHOLD_1H: {PUMP_THRESHOLD_1H}")
logger.info(f"VOLUME_MIN: {VOLUME_MIN}")
logger.info(f"CHECK_INTERVAL: {CHECK_INTERVAL}")

# چک کردن کامل بودن متغیرهای حیاتی
if not all([CHAT_ID, COINGECKO_API_KEY, ETHERSCAN_API_KEY, HELIUS_API_KEY, TELEGRAM_TOKEN]):
    logger.error("لطفاً همه متغیرهای محیطی حیاتی را درست تنظیم کنید.")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "x-api-key": COINGECKO_API_KEY or ""
}

async def fetch_coins():
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd"
        "&order=market_cap_desc"
        "&per_page=100"
        "&page=1"
        "&sparkline=false"
        "&price_change_percentage=15m,30m,1h"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(data)}")
        return data

async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

def format_coin_message(coin, pump_percent, timeframe):
    contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"
    contract_link = f'<a href="https://etherscan.io/token/{contract_address}">{contract_address}</a>' if contract_address != "آدرس کانترکت ندارد" else contract_address

    exchanges = coin.get("exchanges") or ["نامشخص"]
    exchanges_str = ", ".join(exchanges)

    msg = (
        f"🚀 پامپ بالای {pump_percent}% در {timeframe} شناسایی شد!\n"
        f"🪙 {coin.get('name')} ({coin.get('symbol').upper()})\n"
        f"📈 رشد {timeframe}: {pump_percent}%\n"
        f"💰 قیمت فعلی: ${coin.get('current_price')}\n"
        f"📊 حجم معاملات: {coin.get('total_volume')}\n"
        f"🔗 آدرس کانترکت: {contract_link}\n"
        f"🌐 صرافی‌ها: {exchanges_str}\n"
        f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin.get('id')}"
    )
    return msg

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        await send_telegram_message(f"❌ خطا در ربات:\n<pre>{str(e)}</pre>")
        logger.error(f"خطا در check_pump: {e}")
        return

    pump_found = False
    for coin in coins:
        # بررسی حجم معاملات حداقل
        if coin.get("total_volume", 0) < VOLUME_MIN:
            continue

        # بررسی پامپ در تایم‌فریم‌های مختلف
        changes = {
            "15m": coin.get("price_change_percentage_15m_in_currency"),
            "30m": coin.get("price_change_percentage_30m_in_currency"),
            "1h": coin.get("price_change_percentage_1h_in_currency"),
        }

        for timeframe, change in changes.items():
            if change is None:
                continue
            pump_threshold = 0
            if timeframe == "15m":
                pump_threshold = PUMP_THRESHOLD_15M
            elif timeframe == "30m":
                pump_threshold = PUMP_THRESHOLD_30M
            elif timeframe == "1h":
                pump_threshold = PUMP_THRESHOLD_1H

            if change >= pump_threshold and pump_threshold > 0:
                msg = format_coin_message(coin, round(change, 2), timeframe)
                await send_telegram_message(msg)
                pump_found = True

    if not pump_found:
        logger.info("هیچ پامپی یافت نشد.")
        await send_telegram_message("ℹ️ پامپی یافت نشد.")

async def main():
    await send_telegram_message("✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
