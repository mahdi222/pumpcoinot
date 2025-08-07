import asyncio
import logging
import aiohttp
import time
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = "توکن_ربات_شما"
CHAT_ID = "آیدی_عدد_چت"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# این دیکشنری برای جلوگیری از تکرار هشدار استفاده میشه
announced_coins = {}  # coin_id: timestamp

PUMP_THRESHOLD = 50  # درصد رشد در ۱ ساعت
PUMP_COOLDOWN = 60 * 60  # ثانیه: یعنی ۱ ساعت

async def check_pump(bot: Bot):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                coins = await response.json()

                for coin in coins:
                    coin_id = coin['id']
                    change = coin.get("price_change_percentage_1h_in_currency")

                    if not change or change < PUMP_THRESHOLD:
                        continue

                    now = time.time()
                    last_alert_time = announced_coins.get(coin_id, 0)

                    if now - last_alert_time < PUMP_COOLDOWN:
                        continue  # کمتر از 1 ساعت از هشدار قبلی گذشته

                    announced_coins[coin_id] = now  # به‌روزرسانی زمان اعلام

                    message = f"""
🚀 پامپ شدید شناسایی شد!
<b>{coin['name']} ({coin['symbol'].upper()})</b>
📈 رشد ۱ ساعته: <b>{change:.2f}%</b>
💰 قیمت فعلی: ${coin['current_price']}
🔗 <a href="https://www.coingecko.com/en/coins/{coin['id']}">مشاهده در CoinGecko</a>
"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"❌ خطا در دریافت داده: {e}")
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ خطا در بررسی پامپ:\n{str(e)}")

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)  # هر ۵ دقیقه بررسی

if __name__ == "__main__":
    asyncio.run(main_loop())

