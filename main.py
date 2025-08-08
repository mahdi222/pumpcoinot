import asyncio
import logging
import aiohttp
import os
import time
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

# متغیرهای Threshold (مثلا رشد بیش از 20%)
PUMP_THRESHOLD_PERCENT = 0.5

async def fetch_coingecko_meme_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme",
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h",
        "x_cg_pro_api_key": COINGECKO_API_KEY,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return await resp.json()

async def get_etherscan_contract_info(contract_address):
    # نمونه درخواست ساده به Etherscan (توکن‌ و کانترکت چک)
    url = f"https://api.etherscan.io/api"
    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": contract_address,
        "apikey": ETHERSCAN_API_KEY
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            return data

async def get_solana_token_info(mint_address):
    # نمونه درخواست ساده به Helius سولانا
    url = f"https://api.helius.xyz/v0/tokens/{mint_address}"
    headers = {
        "Authorization": f"Bearer {HELIUS_API_KEY}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            return data

async def check_pumps(bot: Bot):
    try:
        coins = await fetch_coingecko_meme_coins()

        for coin in coins:
            # چک رشد ۱ ساعته بالای 20 درصد
            change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0
            if change_1h >= PUMP_THRESHOLD_PERCENT:
                name = coin["name"]
                symbol = coin["symbol"].upper()
                price = coin["current_price"]
                contract_address = coin.get("contract_address") or "ندارد"
                url_coingecko = f"https://www.coingecko.com/en/coins/{coin['id']}"

                # اینجا می‌تونی اطلاعات بیشتر از Etherscan یا Helius بگیری
                # فعلا پیام ساده میفرستیم

                message = f"""🚀 پامپ شدید شناسایی شد!
<b>{name} ({symbol})</b>
📈 رشد ۱ ساعته: <b>{change_1h:.2f}%</b>
💰 قیمت فعلی: ${price}
📜 آدرس کانترکت: <code>{contract_address}</code>
🔗 مشاهده در CoinGecko: {url_coingecko}
"""
                await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML)
                logger.info(f"ارسال پیام پامپ: {name}")

        # اگر پامپی نبود، پیام نده (یا در نسخه بعد اضافه می‌کنیم)

    except Exception as e:
        logger.error(f"خطا در check_pumps: {e}")

async def main_loop():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    while True:
        await check_pumps(bot)
        await asyncio.sleep(300)  # هر 5 دقیقه بررسی کن

if __name__ == "__main__":
    asyncio.run(main_loop())
