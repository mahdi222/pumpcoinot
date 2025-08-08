import os
import asyncio
import logging
import httpx
from telegram import Bot
from telegram.error import TelegramError

# متغیرهای محیطی (نام هارو تغییر ندادم، مقدارشون رو تو Railway تنظیم کن)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # اگر API key دارین، استفاده کنین، اجباری نیست
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "0.1"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "15"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # هر چند ثانیه چک کنه، پیشفرض 5 دقیقه
VOLUME_MIN = float(os.getenv("VOLUME_MIN", "1000000"))  # حجم حداقل

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)

async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

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
    headers = {}
    if COINGECKO_API_KEY:
        headers["X-CoinGecko-Api-Key"] = COINGECKO_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(data)}")
        return data

def format_coin_message(coin, pump_percent, timeframe):
    contract_address = coin.get("contract_address") or "ندارد"
    exchanges = coin.get("exchanges") or "نامشخص"
    price = coin.get("current_price")
    volume = coin.get("total_volume")
    name = coin.get("name")
    symbol = coin.get("symbol").upper()
    coingecko_url = f"https://www.coingecko.com/en/coins/{coin.get('id')}"

    message = (
        f"🚀 پامپ بالای {pump_percent:.2f}% ({timeframe}) شناسایی شد!\n"
        f"🪙 {name} ({symbol})\n"
        f"💰 قیمت فعلی: ${price}\n"
        f"📊 حجم معاملات: {volume:,}\n"
        f"🔗 آدرس کانترکت: {contract_address}\n"
        f"🌐 صرافی‌ها / دکس‌ها: {exchanges}\n"
        f"🌍 لینک کوین در کوین‌گکو:\n{coingecko_url}"
    )
    return message

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        await send_telegram_message(f"❌ خطا در ربات:\n<pre>{e}</pre>")
        logger.error(f"خطا در check_pump: {e}")
        return

    found_pumps = []
    found_small_pumps = []

    for coin in coins:
        try:
            change_15m = coin.get("price_change_percentage_15m_in_currency")
            change_30m = coin.get("price_change_percentage_30m_in_currency")
            change_1h = coin.get("price_change_percentage_1h_in_currency")
            volume = coin.get("total_volume", 0)

            # نادیده گرفتن کوین‌هایی با حجم کمتر از حداقل
            if volume < VOLUME_MIN:
                continue

            # بررسی پامپ‌های مختلف تایم فریم
            pumps = []
            if change_15m is not None and abs(change_15m) >= PUMP_THRESHOLD_15M:
                pumps.append(("15 دقیقه", change_15m))
            if change_30m is not None and abs(change_30m) >= PUMP_THRESHOLD_30M:
                pumps.append(("30 دقیقه", change_30m))
            if change_1h is not None and abs(change_1h) >= PUMP_THRESHOLD_1H:
                pumps.append(("1 ساعت", change_1h))

            for timeframe, change in pumps:
                if change >= 20:
                    msg = format_coin_message(coin, change, timeframe)
                    found_pumps.append(msg)
                elif change > 0:
                    msg = format_coin_message(coin, change, timeframe)
                    found_small_pumps.append(msg)

        except Exception as e:
            logger.error(f"خطا در پردازش کوین {coin.get('id')}: {e}")

    if found_pumps:
        for msg in found_pumps:
            await send_telegram_message(msg)
    else:
        await send_telegram_message("ℹ️ پامپی یافت نشد.")

    if found_small_pumps:
        small_msg = "📉 پامپ‌های زیر ۲۰٪ شناسایی شد:\n\n" + "\n\n".join(found_small_pumps)
        await send_telegram_message(small_msg)

async def main():
    logger.info("ربات شروع به کار کرد")
    await send_telegram_message("✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
