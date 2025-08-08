import os
import asyncio
import logging
import httpx
from telegram import Bot

# متغیرهای محیطی
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.5"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "1"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "15"))
VOLUME_MIN = float(os.getenv("VOLUME_MIN", "100000"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "X-CoinGecko-Api-Key": COINGECKO_API_KEY or ""
}

async def send_telegram_message(message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

async def fetch_coins():
    url = ("https://api.coingecko.com/api/v3/coins/markets"
           "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
           "&price_change_percentage=15m,30m,1h")
    async with httpx.AsyncClient(headers=HEADERS) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        return resp.json()

def is_pump(coin):
    vol = coin.get("total_volume") or 0
    change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
    return vol >= VOLUME_MIN and abs(change_1h) >= PUMP_THRESHOLD_1H

async def fetch_uniswap_data():
    query = """
    {
      pairs(first: 10, orderBy: volumeUSD, orderDirection: desc) {
        token0 { id symbol name }
        token1 { id symbol name }
        volumeUSD
      }
    }
    """
    url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"query": query})
        if resp.status_code != 200:
            logger.error(f"خطا در دریافت داده Uniswap: {resp.status_code} {resp.text}")
            return []
        data = resp.json()
        return data.get("data", {}).get("pairs", [])

async def fetch_sushiswap_data():
    query = """
    {
      pairs(first: 10, orderBy: volumeUSD, orderDirection: desc) {
        token0 { id symbol name }
        token1 { id symbol name }
        volumeUSD
      }
    }
    """
    url = "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"query": query})
        if resp.status_code != 200:
            logger.error(f"خطا در دریافت داده Sushiswap: {resp.status_code} {resp.text}")
            return []
        data = resp.json()
        return data.get("data", {}).get("pairs", [])

async def fetch_dextools_data():
    # این API رسمی نیست، ممکنه نیاز به روش دیگر باشه
    # به صورت تستی اینجا لیست خالی می‌دیم
    return []

# تابع اصلی چک کردن پامپ
async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coins()
    except Exception as e:
        error_text = f"❌ خطا در ربات:\n<pre>{str(e)}</pre>"
        logger.error(error_text)
        await send_telegram_message(error_text)
        return

    pumps = []
    for coin in coins:
        if not is_pump(coin):
            continue

        contract_address = coin.get("contract_address") or coin.get("platforms", {}).get("binance-smart-chain", "")
        contract_address = contract_address.lower() if contract_address else ""

        name = coin.get("name")
        symbol = coin.get("symbol").upper()
        price = coin.get("current_price")
        vol = coin.get("total_volume")
        change_1h = coin.get("price_change_percentage_1h_in_currency")

        contract_msg = contract_address if contract_address else "ندارد"
        link_coingecko = f"https://www.coingecko.com/en/coins/{coin.get('id')}"

        msg = (
            f"🚀 پامپ بالای {PUMP_THRESHOLD_1H}% شناسایی شد!\n"
            f"🪙 {name} ({symbol})\n"
            f"📈 رشد ۱ ساعته: {change_1h:.2f}%\n"
            f"💰 قیمت فعلی: ${price}\n"
            f"📊 حجم معاملات: {vol}\n"
            f"🔗 آدرس کانترکت: {contract_msg}\n"
            f"🌐 لینک کوین در کوین‌گکو:\n{link_coingecko}"
        )
        pumps.append(msg)

    if pumps:
        for m in pumps:
            await send_telegram_message(m)
    else:
        logger.info("هیچ پامپ بالای ۲۰٪ یافت نشد.")

async def main():
    logger.info("ربات شروع به کار کرد")
    await send_telegram_message("✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
