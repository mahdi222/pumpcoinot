import os
import asyncio
import httpx
from telegram import Bot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغیرهای محیطی اصلی (دست نزنی به اسماش)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "0.1"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "15"))

VOLUME_MIN = float(os.getenv("VOLUME_MIN", "100000"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # هر 5 دقیقه

bot = Bot(token=TELEGRAM_TOKEN)

# PancakeSwap Subgraph URL
PANCAKESWAP_API_URL = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange"

PANCAKESWAP_QUERY = """
{
  pairs(first: 100, orderBy: volumeUSD, orderDirection: desc) {
    id
    token0 {
      id
      symbol
      name
    }
    token1 {
      id
      symbol
      name
    }
    volumeUSD
    reserveUSD
  }
}
"""

async def fetch_pancakeswap_data():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(PANCAKESWAP_API_URL, json={"query": PANCAKESWAP_QUERY})
            response.raise_for_status()
            data = response.json()
            if 'errors' in data:
                logger.error(f"GraphQL error PancakeSwap: {data['errors']}")
                return []
            return data.get('data', {}).get('pairs', [])
        except Exception as e:
            logger.error(f"خطا در دریافت داده PancakeSwap: {e}")
            return []

async def fetch_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    headers = {"accept": "application/json"}
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        coins = resp.json()
        if not isinstance(coins, list):
            raise ValueError(f"خروجی API لیست نیست! نوع داده: {type(coins)}")
        return coins

def is_pump(coin):
    # بررسی پامپ با حداقل حجم
    volume = coin.get("total_volume") or 0
    price_change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
    if volume < VOLUME_MIN:
        return False
    return price_change_1h >= PUMP_THRESHOLD_1H

async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
        logger.info("پیام به تلگرام ارسال شد.")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        error_text = f"❌ خطا در ربات:\n<pre>{str(e)}</pre>"
        logger.error(error_text)
        try:
            await send_telegram_message(error_text)
        except:
            pass
        return

    pancakeswap_pairs = await fetch_pancakeswap_data()

    # ساخت دیکشنری برای جستجوی سریع جفت‌ها (توکن‌ها) در PancakeSwap با آدرس کانترکت
    pancake_tokens = set()
    for pair in pancakeswap_pairs:
        pancake_tokens.add(pair['token0']['id'].lower())
        pancake_tokens.add(pair['token1']['id'].lower())

    pumps_above_20 = []
    pumps_below_20 = []

    for coin in coins:
        if not is_pump(coin):
            continue

        contract_address = coin.get("contract_address") or coin.get("platforms", {}).get("binance-smart-chain") or ""
        contract_address = contract_address.lower() if contract_address else ""

        # بررسی اینکه توکن در PancakeSwap هست یا خیر
        dexes = []
        if contract_address in pancake_tokens:
            dexes.append("PancakeSwap")

        # ساخت پیام
        name = coin.get("name")
        symbol = coin.get("symbol").upper()
        price = coin.get("current_price")
        vol = coin.get("total_volume")
        change_1h = coin.get("price_change_percentage_1h_in_currency")

        contract_msg = contract_address if contract_address else "ندارد"
        link_coingecko = f"https://www.coingecko.com/en/coins/{coin.get('id')}"

        msg = (
            f"🚀 پامپ بالای ۲۰٪ شناسایی شد!\n"
            f"🪙 {name} ({symbol})\n"
            f"📈 رشد ۱ ساعته: {change_1h:.2f}%\n"
            f"💰 قیمت فعلی: ${price}\n"
            f"📊 حجم معاملات: {vol}\n"
            f"🔗 آدرس کانترکت: {contract_msg}\n"
            f"🌐 صرافی‌ها: {', '.join(dexes) if dexes else 'نامشخص'}\n"
            f"🌐 لینک کوین در کوین‌گکو:\n{link_coingecko}"
        )

        if change_1h >= 20:
            pumps_above_20.append(msg)
        else:
            pumps_below_20.append(msg)

    # ارسال پیام‌ها
    if pumps_above_20:
        for m in pumps_above_20:
            await send_telegram_message(m)
    else:
        logger.info("هیچ پامپ بالای ۲۰٪ یافت نشد.")

    if pumps_below_20:
        summary_msg = "🚨 پامپ‌های زیر ۲۰٪:\n\n" + "\n\n".join(pumps_below_20)
        await send_telegram_message(summary_msg)

async def periodic_check():
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    logger.info("ربات شروع به کار کرد")
    asyncio.run(periodic_check())
