import os
import asyncio
import logging
import httpx
from telegram import Bot
from telegram.error import TelegramError

# مقداردهی لاگر
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بارگذاری متغیرهای محیطی بدون تغییر نام
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # ثانیه، پیش‌فرض ۵ دقیقه
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "15"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "15"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "20"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VOLUME_MIN = float(os.getenv("VOLUME_MIN", "50000"))

if not all([CHAT_ID, COINGECKO_API_KEY, ETHERSCAN_API_KEY, HELIUS_API_KEY, TELEGRAM_TOKEN]):
    logger.error("لطفاً همه متغیرهای محیطی را درست تنظیم کنید.")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)

# هدر برای کوین‌گکو با api key
HEADERS = {"Accept": "application/json", "X-CoinGecko-Api-Key": COINGECKO_API_KEY}

# لیست شبکه های معتبر که رویشون کار می‌کنیم (نمونه)
VALID_CHAINS = ["ethereum", "binance-smart-chain", "polygon-pos", "solana"]

async def fetch_coins():
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        "&price_change_percentage=15m,30m,1h"
    )
    async with httpx.AsyncClient(headers=HEADERS) as client:
        resp = await client.get(url, timeout=30)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        coins = resp.json()
        if not isinstance(coins, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")
        return coins

def format_contracts(coin):
    # استخراج آدرس کانترکت و صرافی‌های معتبر
    contract_info = []
    platforms = coin.get("platforms", {})
    for chain in VALID_CHAINS:
        address = platforms.get(chain)
        if address:
            contract_info.append(f"{chain}: `{address}`")
    if contract_info:
        return "\n🔗 آدرس کانترکت‌ها:\n" + "\n".join(contract_info)
    else:
        return "🔗 آدرس کانترکت ندارد"

def format_exchanges(coin):
    # این قسمت درصورت امکان می‌توانی توسعه بدی که صرافی‌های لیست شده کوین رو اضافه کنه
    # در حال حاضر به دلیل محدودیت api فقط لینک coingecko داده می‌شود
    return f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin.get('id')}"

def create_message(coin, timeframe: str, pump_percent: float):
    price = coin.get("current_price", 0)
    volume = coin.get("total_volume", 0)
    name = coin.get("name")
    symbol = coin.get("symbol").upper()
    contracts = format_contracts(coin)
    exchanges = format_exchanges(coin)

    msg = (
        f"🚀 پامپ بالای {pump_percent:.2f}% شناسایی شد! ({timeframe})\n"
        f"🪙 {name} ({symbol})\n"
        f"💰 قیمت فعلی: ${price:,.4f}\n"
        f"📊 حجم معاملات: {volume:,.0f} دلار\n"
        f"{contracts}\n"
        f"{exchanges}\n"
    )
    return msg

async def send_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
        logger.info("پیام به تلگرام ارسال شد.")
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        await send_message(f"❌ خطا در ربات:\n<pre>{str(e)}</pre>")
        logger.error(f"خطا در fetch_coins: {e}")
        return

    found_pumps = []
    found_minor_pumps = []

    for coin in coins:
        # نوسانات تایم فریم‌ها
        pc_15m = coin.get("price_change_percentage_15m_in_currency") or 0
        pc_30m = coin.get("price_change_percentage_30m_in_currency") or 0
        pc_1h = coin.get("price_change_percentage_1h_in_currency") or 0
        volume = coin.get("total_volume", 0)

        # فیلتر حجم
        if volume < VOLUME_MIN:
            continue

        # بررسی پامپ‌ها در هر تایم فریم
        if pc_15m >= PUMP_THRESHOLD_15M:
            found_pumps.append(create_message(coin, "۱۵ دقیقه", pc_15m))
        elif pc_15m > 0:
            found_minor_pumps.append(create_message(coin, "۱۵ دقیقه", pc_15m))

        if pc_30m >= PUMP_THRESHOLD_30M:
            found_pumps.append(create_message(coin, "۳۰ دقیقه", pc_30m))
        elif pc_30m > 0:
            found_minor_pumps.append(create_message(coin, "۳۰ دقیقه", pc_30m))

        if pc_1h >= PUMP_THRESHOLD_1H:
            found_pumps.append(create_message(coin, "۱ ساعت", pc_1h))
        elif pc_1h > 0:
            found_minor_pumps.append(create_message(coin, "۱ ساعت", pc_1h))

    if found_pumps:
        for msg in found_pumps:
            await send_message(msg)
    else:
        await send_message("ℹ️ پامپی یافت نشد.")

    if found_minor_pumps:
        minor_msg = "🚨 پامپ‌های زیر حد آستانه (کمتر از آستانه تعریف شده):\n\n" + "\n---\n".join(found_minor_pumps)
        await send_message(minor_msg)

async def periodic_check():
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    logger.info("✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    asyncio.run(periodic_check())
