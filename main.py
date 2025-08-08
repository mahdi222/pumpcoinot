import asyncio
import logging
import httpx
import time
import os
import traceback
from telegram import Bot
from telegram.constants import ParseMode

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

announced_coins = {}
last_no_pump_alert = 0
NO_PUMP_ALERT_COOLDOWN = 60 * 30  # ۳۰ دقیقه بین پیام "پامپی یافت نشد"

PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", 20))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", 10))
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", 5))

PUMP_COOLDOWN = 60 * 60  # یک ساعت برای هر هشدار

HEADERS = {
    "Accept": "application/json",
    "X-CoinGecko-Api-Key": COINGECKO_API_KEY
}

def build_pump_message(coin, pump_level: str, change_percent: float, timeframe: str):
    name = coin.get('name', 'نامشخص')
    symbol = coin.get('symbol', '').upper()
    price = coin.get('current_price', 'نامشخص')
    volume = coin.get('total_volume', 0)
    platforms = coin.get('platforms', {})
    contract_address = None
    contract_link = "آدرس کانترکت ندارد"
    
    # اولویت شبکه‌ها: بایننس اسمارت چین، اتریوم، متیک، سولانا
    for net in ['binance-smart-chain', 'ethereum', 'polygon-pos', 'solana']:
        address = platforms.get(net)
        if address:
            contract_address = address
            if net == 'ethereum':
                contract_link = f"https://etherscan.io/address/{address}"
            elif net == 'binance-smart-chain':
                contract_link = f"https://bscscan.com/address/{address}"
            elif net == 'polygon-pos':
                contract_link = f"https://polygonscan.com/address/{address}"
            elif net == 'solana':
                contract_link = f"https://explorer.solana.com/address/{address}"
            break

    coingecko_link = f"https://www.coingecko.com/en/coins/{coin.get('id', '')}"

    message = f"""🚀 پامپ {pump_level} شناسایی شد!
🪙 {name} ({symbol})
⏳ تایم‌فریم: {timeframe}
📈 رشد: <b>{change_percent:.2f}%</b>
💰 قیمت فعلی: ${price}
📊 حجم معاملات: {volume:,}
🔗 آدرس کانترکت: {contract_address if contract_address else 'ندارد'}
🌐 لینک کانترکت: {contract_link if contract_address else 'ندارد'}
🌐 لینک کوین در کوین‌گکو:
{coingecko_link}
"""
    return message


async def send_error(bot: Bot, err: Exception):
    try:
        error_text = f"❌ خطا در برنامه:\n<pre>{traceback.format_exc()}</pre>"
        logger.error(traceback.format_exc())
        await bot.send_message(chat_id=CHAT_ID, text=error_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام خطا به تلگرام: {e}")

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
        async with httpx.AsyncClient(headers=HEADERS) as client:
            response = await client.get(url, params=params)
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(data)}")

            now = time.time()
            found_pump_20_plus = False
            found_pump_below_20 = False

            for coin in data:
                if not isinstance(coin, dict):
                    continue

                coin_id = coin.get('id', '')
                name = coin.get('name', '')
                symbol = coin.get('symbol', '').upper()
                price = coin.get('current_price', 0)
                volume = coin.get('total_volume') or 0

                if volume < 1:
                    continue

                change_15m = coin.get("price_change_percentage_15m_in_currency") or 0
                change_30m = coin.get("price_change_percentage_30m_in_currency") or 0
                change_1h = coin.get("price_change_percentage_1h_in_currency") or 0

                # پامپ بالای 20 درصد (۱ ساعت)
                if change_1h >= PUMP_THRESHOLD_1H:
                    last_alert = announced_coins.get(f"{coin_id}_1h", 0)
                    if now - last_alert > PUMP_COOLDOWN:
                        announced_coins[f"{coin_id}_1h"] = now
                        message = build_pump_message(coin, "بالای ۲۰٪", change_1h, "۱ ساعت")
                        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                        logger.info(f"پامپ بالای ۲۰٪: {name} {change_1h:.2f}%")
                        found_pump_20_plus = True

                # پامپ بین ۱۰ تا ۲۰ درصد (۳۰ دقیقه)
                elif change_30m >= PUMP_THRESHOLD_30M:
                    last_alert = announced_coins.get(f"{coin_id}_30m", 0)
                    if now - last_alert > PUMP_COOLDOWN:
                        announced_coins[f"{coin_id}_30m"] = now
                        message = build_pump_message(coin, "بین ۱۰ تا ۲۰٪", change_30m, "۳۰ دقیقه")
                        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                        logger.info(f"پامپ بین ۱۰ تا ۲۰٪: {name} {change_30m:.2f}%")
                        found_pump_below_20 = True

                # پامپ بین ۵ تا ۱۰ درصد (۱۵ دقیقه)
                elif change_15m >= PUMP_THRESHOLD_15M:
                    last_alert = announced_coins.get(f"{coin_id}_15m", 0)
                    if now - last_alert > PUMP_COOLDOWN:
                        announced_coins[f"{coin_id}_15m"] = now
                        message = build_pump_message(coin, "بین ۵ تا ۱۰٪", change_15m, "۱۵ دقیقه")
                        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                        logger.info(f"پامپ بین ۵ تا ۱۰٪: {name} {change_15m:.2f}%")
                        found_pump_below_20 = True

            global last_no_pump_alert
            if not found_pump_20_plus and not found_pump_below_20:
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
