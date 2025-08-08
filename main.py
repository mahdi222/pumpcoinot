import os
import asyncio
import logging
import aiohttp
import time
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ذخیره زمان هشدار برای جلوگیری از اسپم
announced_coins = {}
PUMP_THRESHOLD = 50       # درصد رشد
PUMP_COOLDOWN = 60 * 60   # یک ساعت

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
            async with session.get(url, params=params, timeout=20) as response:
                if response.status != 200:
                    logger.error(f"خطای API: {response.status}")
                    return
                coins = await response.json()

        for coin in coins:
            coin_id = coin['id']
            change = coin.get("price_change_percentage_1h_in_currency")

            if not change or change < PUMP_THRESHOLD:
                continue

            now = time.time()
            if now - announced_coins.get(coin_id, 0) < PUMP_COOLDOWN:
                continue

            announced_coins[coin_id] = now
            message = f"""
🚀 پامپ شدید شناسایی شد!
<b>{coin['name']} ({coin['symbol'].upper()})</b>
📈 رشد ۱ ساعته: <b>{change:.2f}%</b>
💰 قیمت فعلی: ${coin['current_price']}
🔗 <a href="https://www.coingecko.com/en/coins/{coin['id']}">مشاهده در CoinGecko</a>
"""
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)

    except asyncio.TimeoutError:
        logger.error("⏳ تایم‌اوت در اتصال به API")
    except Exception as e:
        logger.error(f"❌ خطا: {e}")

async def main_loop():
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ لطفاً TOKEN و CHAT_ID را به عنوان Environment Variables تنظیم کنید.")
        return

    bot = Bot(token=BOT_TOKEN)
    while True:
        await check_pump(bot)
        await asyncio.sleep(300)  # هر ۵ دقیقه

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("⏹ توقف ربات توسط کاربر")
