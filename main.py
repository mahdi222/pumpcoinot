import asyncio
import logging
import httpx
import os
import time
import traceback
from telegram import Bot
from telegram.constants import ParseMode

# متغیرهای محیطی (اسم متغیرها دقیقاً همونایی که گفتی)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # اگر API Key داری، اگر نداری میتونی خالی بذاری
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
PUMP_THRESHOLD = float(os.getenv("PUMP_THRESHOLD", "15"))  # پیش‌فرض 15%
VS_CURRENCY = os.getenv("VS_CURRENCY", "usd")

# تنظیمات
PUMP_COOLDOWN = 60 * 60  # یک ساعت بین هر هشدار
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # 30 دقیقه پیام "پامپ پیدا نشد"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0

async def send_error(bot: Bot, err: Exception):
    error_text = f"❌ خطا:\n<pre>{traceback.format_exc()}</pre>"
    logger.error(traceback.format_exc())
    try:
        # حذف تگ‌های HTML که ممکنه تلگرام قبول نکنه
        safe_text = error_text.replace('<', '&lt;').replace('>', '&gt;')
        await bot.send_message(chat_id=CHAT_ID, text=safe_text, parse_mode=ParseMode.HTML)
    except Exception:
        logger.error("❌ خطا در ارسال پیام خطا به تلگرام")

async def fetch_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": VS_CURRENCY,
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d",
    }
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-api-key"] = COINGECKO_API_KEY

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        return resp.json()

async def check_pump(bot: Bot):
    global last_no_pump_alert
    try:
        logger.info("check_pump داره اجرا میشه...")
        coins = await fetch_coins()
        found_pump = False
        now = time.time()

        for coin in coins:
            coin_id = coin.get("id", "")
            name = coin.get("name", "")
            symbol = coin.get("symbol", "").upper()
            price = coin.get("current_price", 0)
            volume = coin.get("total_volume", 0)
            contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"
            # برخی کوین‌ها مثل بیت‌کوین کانترکت ندارن، اگر contract_address خالی بود متن بالا رو میذاریم

            change_1h = coin.get("price_change_percentage_1h_in_currency")
            if change_1h is None:
                change_1h = 0

            if change_1h >= PUMP_THRESHOLD:
                last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                if now - last_alert > PUMP_COOLDOWN:
                    announced_coins[f"{coin_id}_1h"] = now

                    # لینک کانترکت: اگر contract_address معتبر بود لینک میسازیم
                    contract_link = "آدرس کانترکت ندارد"
                    if contract_address != "آدرس کانترکت ندارد":
                        # فرض میکنیم شبکه اتریوم هست، میشه توسعه داد برای شبکه‌های دیگه
                        contract_link = f"https://etherscan.io/address/{contract_address}"

                    message = f"""
🚀 پامپ بالای {PUMP_THRESHOLD}% شناسایی شد!
🪙 {name} ({symbol})
📈 رشد ۱ ساعته: {change_1h:.2f}%
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: {contract_address if contract_address != 'آدرس کانترکت ندارد' else 'ندارد'}
🔗 لینک کانترکت: {contract_link if contract_address != 'آدرس کانترکت ندارد' else 'ندارد'}
🌐 لینک کوین در کوین‌گکو:
https://www.coingecko.com/en/coins/{coin_id}
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                    logger.info(f"پامپ شدید: {name} {change_1h:.2f}%")
                    found_pump = True

        if not found_pump and now - last_no_pump_alert > NO_PUMP_ALERT_COOLDOWN:
            await bot.send_message(chat_id=CHAT_ID, text="ℹ️ پامپی یافت نشد.")
            last_no_pump_alert = now
            logger.info("هیچ پامپی یافت نشد.")

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
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("توکن تلگرام یا چت آیدی تنظیم نشده‌اند!")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    logger.info("ربات شروع به کار کرد")

    await asyncio.gather(
        run_check_pump_loop(bot),
        send_heartbeat(bot),
    )

async def run_check_pump_loop(bot: Bot):
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)  # هر 5 دقیقه

if __name__ == "__main__":
    asyncio.run(main_loop())
