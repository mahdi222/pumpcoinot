import asyncio
import logging
import httpx
import os
import traceback
from telegram import Bot
from telegram.constants import ParseMode

# متغیرهای محیطی (اسم متغیرها رو تغییر نده)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD = float(os.getenv("PUMP_THRESHOLD", "15"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # 30 دقیقه بین پیام "پامپی یافت نشد"
PUMP_COOLDOWN = 60 * 60  # یک ساعت بین هشدارهای یک کوین

HEADERS = {"Accept": "application/json"}
if COINGECKO_API_KEY:
    HEADERS["X-CoinGecko-Api-Key"] = COINGECKO_API_KEY

def escape_html(text: str) -> str:
    # برای متن خطا که در <pre> قرار میگیره، چند کاراکتر خاص رو escape کنیم
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

async def send_error(bot: Bot, err: Exception):
    error_text = f"❌ خطا:\n<pre>{escape_html(traceback.format_exc())}</pre>"
    logger.error(traceback.format_exc())
    try:
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پیام خطا به تلگرام: {e}")

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

    global last_no_pump_alert
    now = asyncio.get_event_loop().time()

    try:
        async with httpx.AsyncClient(headers=HEADERS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")

            coins = resp.json()

            if not isinstance(coins, list):
                raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")

            found_pump_high = False
            found_pump_low = False

            for coin in coins:
                coin_id = coin.get("id")
                name = coin.get("name")
                symbol = coin.get("symbol", "").upper()
                price = coin.get("current_price")
                volume = coin.get("total_volume") or 0

                if volume < 1:
                    continue

                change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

                # بررسی پامپ بالای 20 درصد
                if change_1h >= 20:
                    last_alert = announced_coins.get(f"{coin_id}_high", 0)
                    if now - last_alert > PUMP_COOLDOWN:
                        announced_coins[f"{coin_id}_high"] = now
                        contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"
                        exchanges = coin.get("exchanges", [])
                        exchanges_text = ", ".join(exchanges) if exchanges else "نامشخص"
                        message = (
                            f"🚀 پامپ بالای ۲۰٪ شناسایی شد!\n"
                            f"🪙 {name} ({symbol})\n"
                            f"📈 رشد ۱ ساعته: {change_1h:.2f}%\n"
                            f"💰 قیمت فعلی: ${price}\n"
                            f"📊 حجم معاملات: {volume:,}\n"
                            f"🔗 آدرس کانترکت: {contract_address}\n"
                            f"🌐 قابل معامله در: {exchanges_text}\n"
                            f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin_id}"
                        )
                        await bot.send_message(chat_id=CHAT_ID, text=message)
                        logger.info(f"پامپ بالای ۲۰٪: {name} {change_1h:.2f}%")
                        found_pump_high = True

                # بررسی پامپ زیر 20 درصد اما بالای مقدار آستانه
                elif change_1h >= PUMP_THRESHOLD:
                    last_alert = announced_coins.get(f"{coin_id}_low", 0)
                    if now - last_alert > PUMP_COOLDOWN:
                        announced_coins[f"{coin_id}_low"] = now
                        contract_address = coin.get("contract_address") or "آدرس کانترکت ندارد"
                        exchanges = coin.get("exchanges", [])
                        exchanges_text = ", ".join(exchanges) if exchanges else "نامشخص"
                        message = (
                            f"⚠️ پامپ زیر ۲۰٪ قابل توجه:\n"
                            f"🪙 {name} ({symbol})\n"
                            f"📈 رشد ۱ ساعته: {change_1h:.2f}%\n"
                            f"💰 قیمت فعلی: ${price}\n"
                            f"📊 حجم معاملات: {volume:,}\n"
                            f"🔗 آدرس کانترکت: {contract_address}\n"
                            f"🌐 قابل معامله در: {exchanges_text}\n"
                            f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin_id}"
                        )
                        await bot.send_message(chat_id=CHAT_ID, text=message)
                        logger.info(f"پامپ زیر ۲۰٪: {name} {change_1h:.2f}%")
                        found_pump_low = True

            if not found_pump_high and not found_pump_low:
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
