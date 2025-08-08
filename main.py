import os
import asyncio
import logging
import html
import traceback
from telegram import Bot
from telegram.constants import ParseMode
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دریافت متغیرها
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PUMP_THRESHOLD = float(os.getenv("PUMP_THRESHOLD", 0.5))

announced_coins = {}
last_no_pump_alert = 0
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # 30 دقیقه بین پیام "پامپی یافت نشد"
PUMP_COOLDOWN = 60 * 60  # یک ساعت بین هشدار هر کوین


async def send_telegram(bot: Bot, text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")


async def send_error(bot: Bot, err: Exception):
    tb_text = html.escape(traceback.format_exc())
    message = f"❌ خطا در برنامه:\n<pre>{tb_text}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام خطا به تلگرام: {e}")


async def check_pump(bot: Bot):
    global last_no_pump_alert
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "price_change_percentage": "15m,30m,1h"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if not isinstance(data, list):
                    await send_telegram(bot, f"❌ خروجی API لیست نیست!\nنوع داده: <code>{type(data)}</code>\n\n{html.escape(str(data))}")
                    return

                found_pump = False
                now = asyncio.get_event_loop().time()

                for coin in data:
                    coin_id = coin.get('id')
                    name = coin.get('name')
                    symbol = coin.get('symbol', '').upper()
                    price = coin.get('current_price', 0)
                    volume = coin.get('total_volume', 0)
                    change_1h = coin.get('price_change_percentage_1h_in_currency') or 0

                    if change_1h >= PUMP_THRESHOLD:
                        last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                        if now - last_alert > PUMP_COOLDOWN:
                            announced_coins[f"{coin_id}_1h"] = now
                            msg = (
                                f"🚀 <b>پامپ بالای ۲۰٪ شناسایی شد!</b>\n"
                                f"🪙 <b>{name} ({symbol})</b>\n"
                                f"📈 رشد ۱ ساعته: <b>{change_1h:.2f}%</b>\n"
                                f"💰 قیمت فعلی: ${price}\n"
                                f"📊 حجم معاملات: {volume:,}\n"
                                f"🔗 <code>{coin.get('contract_address','آدرس کانترکت ندارد')}</code>\n"
                                f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin_id}"
                            )
                            await send_telegram(bot, msg)
                            logger.info(f"پامپ شناسایی شد: {name} {change_1h:.2f}%")
                            found_pump = True

                if not found_pump and (now - last_no_pump_alert) > NO_PUMP_ALERT_COOLDOWN:
                    await send_telegram(bot, "ℹ️ پامپی یافت نشد.")
                    last_no_pump_alert = now

    except Exception as e:
        await send_error(bot, e)


async def send_heartbeat(bot: Bot):
    while True:
        try:
            await send_telegram(bot, "💓 بات فعال است و در حال اجرا...")
            logger.info("پیام سلامت بات ارسال شد")
        except Exception as e:
            logger.error(f"خطا در ارسال پیام سلامت بات: {e}")
        await asyncio.sleep(300)


async def main():
    if not TELEGRAM_TOKEN:
        print("❌ خطا: متغیر محیطی TELEGRAM_TOKEN تعریف نشده یا خالی است.")
        return

    if not CHAT_ID:
        print("❌ خطا: متغیر محیطی CHAT_ID تعریف نشده یا خالی است.")
        return

    logger.info(f"TELEGRAM_TOKEN length: {len(TELEGRAM_TOKEN)}")
    logger.info(f"CHAT_ID: {CHAT_ID}")

    bot = Bot(token=TELEGRAM_TOKEN)

    await send_telegram(bot, "✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    await asyncio.gather(
        check_pump_loop(bot),
        send_heartbeat(bot)
    )


async def check_pump_loop(bot: Bot):
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)  # هر 5 دقیقه


if __name__ == "__main__":
    asyncio.run(main())
