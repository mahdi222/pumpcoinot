import asyncio
import logging
import httpx
import os
import time
import traceback
from telegram import Bot
from telegram.constants import ParseMode

# --- متغیرهای محیطی (Railway) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # اگر داری
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")  # برای اتریوم و BSC
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")  # برای سولانا

PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))  # تست 0.1, بعدا بذار 15
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "15"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "20"))

VOLUME_MIN = float(os.getenv("VOLUME_MIN", "1000"))  # حداقل حجم معامله برای پامپ در دلار

PUMP_COOLDOWN = 60 * 60  # 1 ساعت فاصله تکرار هشدار برای هر کوین
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # 30 دقیقه برای پیام پامپ نیافتاد

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0

HEADERS = {
    "Accept": "application/json",
    "X-CoinGecko-Api-Key": COINGECKO_API_KEY if COINGECKO_API_KEY else ""
}


async def send_telegram(bot: Bot, text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")


async def send_error(bot: Bot, err: Exception):
    tb = traceback.format_exc()
    err_text = f"❌ خطا در ربات:\n<pre>{tb}</pre>"
    logger.error(tb)
    # برخی تگ‌های HTML تلگرام قبول نداره؛ پاک کردن تگ <class> و ... اگر بود
    err_text = err_text.replace("<", "&lt;").replace(">", "&gt;")
    try:
        await bot.send_message(chat_id=CHAT_ID, text=err_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام خطا به تلگرام: {e}")


async def fetch_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h"
    }
    async with httpx.AsyncClient(headers=HEADERS) as client:
        resp = await client.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(data)}")
        return data


def get_contract_address(coin):
    # توی داده coingecko کانترکت در شبکه‌ها زیر key "platforms" است:
    platforms = coin.get("platforms", {})
    # اولویت شبکه‌ها (بایننس اسمارت چین, اتریوم, متیک, سولانا) — کانترکت آدرس معتبر نیست اگر خالی بود یا '0x0'
    for net in ["binance-smart-chain", "ethereum", "polygon-pos", "solana"]:
        addr = platforms.get(net)
        if addr and addr != "" and addr != "0x0000000000000000000000000000000000000000":
            return addr, net
    return None, None


async def check_pump(bot: Bot):
    global last_no_pump_alert

    try:
        coins = await fetch_coins()
        now = time.time()
        found_any = False

        for coin in coins:
            coin_id = coin.get("id")
            name = coin.get("name")
            symbol = coin.get("symbol", "").upper()
            price = coin.get("current_price", 0)
            volume = coin.get("total_volume") or 0

            if volume < VOLUME_MIN:
                continue

            change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
            change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
            change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

            contract_addr, network = get_contract_address(coin)
            contract_info = f"<b>آدرس کانترکت ({network}):</b> <code>{contract_addr}</code>" if contract_addr else "🔗 آدرس کانترکت ندارد"

            coingecko_link = f"https://www.coingecko.com/en/coins/{coin_id}"

            # اول بررسی پامپ 1h بالای 20% (پیام جدا)
            if change_1h >= PUMP_THRESHOLD_1H:
                last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_1h"] = now
                    message = (
                        f"🚀 پامپ بالای ۲۰٪ شناسایی شد!\n"
                        f"🪙 {name} ({symbol})\n"
                        f"📈 رشد ۱ ساعته: {change_1h:.2f}%\n"
                        f"💰 قیمت فعلی: ${price}\n"
                        f"📊 حجم معاملات: {volume:,}\n"
                        f"{contract_info}\n"
                        f"🌐 لینک کوین در کوین‌گکو:\n{coingecko_link}"
                    )
                    await send_telegram(bot, message)
                    found_any = True
                    continue

            # پامپ 30m بین 15 تا 20 (یا زیر 20، به شرط پیام جدا)
            if change_30m >= PUMP_THRESHOLD_30M and change_30m < PUMP_THRESHOLD_1H:
                last_alert = announced_coins.get(f"{coin_id}_30m", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_30m"] = now
                    message = (
                        f"⚡ پامپ قابل توجه (زیر ۲۰٪) شناسایی شد!\n"
                        f"🪙 {name} ({symbol})\n"
                        f"📈 رشد ۳۰ دقیقه‌ای: {change_30m:.2f}%\n"
                        f"💰 قیمت فعلی: ${price}\n"
                        f"📊 حجم معاملات: {volume:,}\n"
                        f"{contract_info}\n"
                        f"🌐 لینک کوین در کوین‌گکو:\n{coingecko_link}"
                    )
                    await send_telegram(bot, message)
                    found_any = True
                    continue

            # پامپ 15m بالای آستانه تعریف شده و زیر 30m
            if change_15m >= PUMP_THRESHOLD_15M and change_15m < PUMP_THRESHOLD_30M:
                last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_15m"] = now
                    message = (
                        f"⚠️ پامپ احتمالی شناسایی شد!\n"
                        f"🪙 {name} ({symbol})\n"
                        f"📈 رشد ۱۵ دقیقه‌ای: {change_15m:.2f}%\n"
                        f"💰 قیمت فعلی: ${price}\n"
                        f"📊 حجم معاملات: {volume:,}\n"
                        f"{contract_info}\n"
                        f"🌐 لینک کوین در کوین‌گکو:\n{coingecko_link}"
                    )
                    await send_telegram(bot, message)
                    found_any = True
                    continue

        if not found_any:
            if time.time() - last_no_pump_alert > NO_PUMP_ALERT_COOLDOWN:
                await send_telegram(bot, "ℹ️ پامپی یافت نشد.")
                last_no_pump_alert = time.time()

    except Exception as e:
        await send_error(bot, e)


async def send_heartbeat(bot: Bot):
    while True:
        try:
            await bot.send_message(chat_id=CHAT_ID, text="💓 بات فعال است و در حال اجرا...")
            logger.info("پیام سلامت بات ارسال شد")
        except Exception:
            logger.error("خطا در ارسال پیام سلامت بات")
        await asyncio.sleep(300)  # هر 5 دقیقه


async def main_loop():
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    logger.info("ربات شروع به کار کرد")

    while True:
        logger.info("check_pump داره اجرا میشه...")
        await check_pump(bot)
        await asyncio.sleep(300)  # هر 5 دقیقه


if __name__ == "__main__":
    asyncio.run(main_loop())
