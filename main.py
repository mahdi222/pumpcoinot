import os
import asyncio
import logging
import httpx
from telegram import Bot
from telegram.error import TelegramError

# ====== تنظیم لاگ ======
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== دریافت متغیرهای محیطی ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "15"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "15"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "20"))

VOLUME_MIN = float(os.getenv("VOLUME_MIN", "1000000"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # برحسب ثانیه (مثلا 300 یعنی هر 5 دقیقه)

# ====== اعتبارسنجی متغیرها ======
required_vars = [
    ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
    ("CHAT_ID", CHAT_ID),
    ("COINGECKO_API_KEY", COINGECKO_API_KEY),
    ("ETHERSCAN_API_KEY", ETHERSCAN_API_KEY),
    ("HELIUS_API_KEY", HELIUS_API_KEY),
]

for name, val in required_vars:
    if not val:
        logger.error(f"لطفاً متغیر محیطی {name} را درست تنظیم کنید.")
        exit(1)

bot = Bot(token=TELEGRAM_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "X-CoinGecko-Api-Key": COINGECKO_API_KEY,
}

async def send_telegram_message(text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

async def fetch_coins():
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"
        "&sparkline=false&price_change_percentage=15m,30m,1h"
    )
    async with httpx.AsyncClient(headers=HEADERS) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        return resp.json()

def format_coin_message(coin, timeframe_label, change):
    volume = coin.get("total_volume", 0)
    contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"
    if contract_address != "آدرس کانترکت ندارد":
        contract_address = f'<a href="https://bscscan.com/token/{contract_address}">{contract_address}</a>'
    message = (
        f"🚀 پامپ بالای {PUMP_THRESHOLD_1H}% شناسایی شد!\n"
        f"🪙 {coin['name']} ({coin['symbol'].upper()})\n"
        f"📈 رشد {timeframe_label}: {change:.2f}%\n"
        f"💰 قیمت فعلی: ${coin['current_price']}\n"
        f"📊 حجم معاملات: {volume:,}\n"
        f"🔗 آدرس کانترکت: {contract_address}\n"
        f"🌐 <a href='https://www.coingecko.com/en/coins/{coin['id']}'>لینک کوین در کوین‌گکو</a>"
    )
    return message

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        err_text = f"❌ خطا در ربات:\n<pre>{e}</pre>"
        logger.error(err_text)
        await send_telegram_message(err_text)
        return

    pumps_found = 0
    for coin in coins:
        volume = coin.get("total_volume", 0) or 0
        if volume < VOLUME_MIN:
            continue

        # دریافت درصد تغییرات
        change_15m = coin.get("price_change_percentage_15m_in_currency")
        change_30m = coin.get("price_change_percentage_30m_in_currency")
        change_1h = coin.get("price_change_percentage_1h_in_currency")

        # بررسی پامپ روی هر تایم فریم با آستانه‌های تعریف شده
        msgs = []
        if change_15m is not None and change_15m >= PUMP_THRESHOLD_15M:
            msgs.append(format_coin_message(coin, "۱۵ دقیقه", change_15m))
        if change_30m is not None and change_30m >= PUMP_THRESHOLD_30M:
            msgs.append(format_coin_message(coin, "۳۰ دقیقه", change_30m))
        if change_1h is not None and change_1h >= PUMP_THRESHOLD_1H:
            msgs.append(format_coin_message(coin, "۱ ساعت", change_1h))

        for msg in msgs:
            pumps_found += 1
            await send_telegram_message(msg)

    if pumps_found == 0:
        logger.info("هیچ پامپ بالای آستانه یافت نشد.")

async def main_loop():
    logger.info("ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    await send_telegram_message("✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main_loop())
