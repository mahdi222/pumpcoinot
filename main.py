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
NO_PUMP_ALERT_COOLDOWN = 60 * 5  # 30 دقیقه بین پیام "پامپی یافت نشد"

PUMP_THRESHOLD_1H = 50   # رشد ۱ ساعت برای پامپ اصلی
PUMP_THRESHOLD_30M = 15  # رشد ۳۰ دقیقه برای پامپ متوسط
PUMP_THRESHOLD_15M = 0.1   # رشد ۱۵ دقیقه برای پامپ احتمالی
VOLUME_INCREASE_RATIO = 1.5  # حجم باید حداقل 1.5 برابر میانگین باشه برای پامپ

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

                    # چون کوین‌گکو حجم میانگین تاریخی رو نمیده، اینجا فرض می‌کنیم حجم پامپ شده حداقل 1.5 برابر حجم قبلیه
                    # برای نمونه ساده، حجم رو مقایسه نمی‌کنیم دقیق، فقط اگر حجم خیلی کم بود رد می‌کنیم (مثلاً کمتر از 1000 دلار)
                    if volume < 1000:
                        continue

                    change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
                    change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
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
📊 حجم معاملات: {volume:,}
🔗 <a href="https://www.coingecko.com/en/coins/{coin_id}">مشاهده در CoinGecko</a>
"""
                            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                            logger.info(f"پامپ شدید: {name} {change_1h:.2f}%")
                            found_pump = True

                    # پامپ متوسط (۳۰ دقیقه)
                    elif change_30m >= PUMP_THRESHOLD_30M:
                        last_alert = announced_coins.get(f"{coin_id}_30m", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_30m"] = now
                            message = f"""
⚡ پامپ متوسط در حال شکل‌گیری!
<b>{name} ({symbol})</b>
📈 رشد ۳۰ دقیقه‌ای: <b>{change_30m:.2f}%</b>
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 <a href="https://www.coingecko.com/en/coins/{coin_id}">مشاهده در CoinGecko</a>
"""
                            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                            logger.info(f"پامپ متوسط: {name} {change_30m:.2f}%")
                            found_pump_mid = True

                    # پامپ احتمالی (۱۵ دقیقه)
                    elif change_15m >= PUMP_THRESHOLD_15M:
                        last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_15m"] = now
                            message = f"""
⚠️ پامپ احتمالی در حال شکل‌گیری!
<b>{name} ({symbol})</b>
📈 رشد ۱۵ دقیقه‌ای: <b>{change_15m:.2f}%</b>
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 <a href="https://www.coingecko.com/en/coins/{coin_id}">مشاهده در CoinGecko</a>
"""
                            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                            logger.info(f"پامپ احتمالی: {name} {change_15m:.2f}%")
                            found_pump_alert = True

                # پیام عدم پامپ (فقط هر ۳۰ دقیقه یک بار)
                global last_no_pump_alert
                if not found_pump and not found_pump_mid and not found_pump_alert:
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
        except Exception:
            logger.error("خطا در ارسال پیام سلامت بات")
        await asyncio.sleep(300)  # هر 5 دقیقه یکبار

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    logger.info("ربات شروع به کار کرد")

    await asyncio.gather(
        run_check_pump_loop(bot),
        send_heartbeat(bot),
    )

async def run_check_pump_loop(bot: Bot):
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
