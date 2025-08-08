import os
import asyncio
import logging
import httpx
from telegram import Bot

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغیرهای محیطی - تغییر نده اسم‌ها رو
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.5"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "0.7"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "1.0"))

VOLUME_MIN = float(os.getenv("VOLUME_MIN", "100000"))  # حداقل حجم معاملات برای بررسی

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # ثانیه، زمان بین هر بررسی (مثلاً 300 ثانیه = 5 دقیقه)

# اطمینان از مقداردهی متغیرهای مهم
required_vars = [TELEGRAM_TOKEN, CHAT_ID, COINGECKO_API_KEY, ETHERSCAN_API_KEY, HELIUS_API_KEY]
if any(v is None for v in required_vars):
    logger.error("لطفاً همه متغیرهای محیطی را درست تنظیم کنید.")
    exit(1)

bot = Bot(token=TELEGRAM_TOKEN)

HEADERS = {"Accept": "application/json"}

# ---------------------------- بخش دریافت کوین‌ها از CoinGecko ----------------------------

async def fetch_coingecko_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=HEADERS)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        data = resp.json()
        return data

# ---------------------------- بخش دریافت توکن‌ها از PancakeSwap (BSC) ----------------------------

PANCAKESWAP_API_URL = "https://bsc.streamingfast.io/subgraphs/name/pancakeswap/exchange-v2"
PANCAKESWAP_QUERY = """
{
  tokens(first: 100, orderBy: volumeUSD, orderDirection: desc) {
    id
    symbol
    name
    volumeUSD
    totalLiquidity
    derivedBNB
  }
}
"""

async def fetch_pancakeswap_tokens():
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(PANCAKESWAP_API_URL, json={"query": PANCAKESWAP_QUERY})
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", {}).get("tokens", [])

# ---------------------------- بخش دریافت توکن‌ها از Uniswap (Ethereum) ----------------------------

UNISWAP_API_URL = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
UNISWAP_QUERY = """
{
  tokens(first: 100, orderBy: volumeUSD, orderDirection: desc) {
    id
    symbol
    name
    volumeUSD
    totalLiquidity
  }
}
"""

async def fetch_uniswap_tokens():
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(UNISWAP_API_URL, json={"query": UNISWAP_QUERY})
        resp.raise_for_status()
        result = resp.json()
        return result.get("data", {}).get("tokens", [])

# ---------------------------- بخش ارسال پیام به تلگرام ----------------------------

async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

# ---------------------------- بخش تحلیل پامپ ----------------------------

def check_pump_percent(change, threshold):
    try:
        return float(change) >= threshold
    except Exception:
        return False

def format_contract_address(contract):
    if contract:
        return f"<a href='{contract}'>آدرس کانترکت</a>"
    return "آدرس کانترکت ندارد"

def format_dex_links(symbol):
    # به طور نمونه میسازم لینک Pancake و Uniswap (شما میتونی با API های اختصاصی واقعی بگیری)
    links = []
    if symbol:
        links.append(f"<a href='https://pancakeswap.finance/swap?outputCurrency={symbol}'>PancakeSwap</a>")
        links.append(f"<a href='https://app.uniswap.org/#/swap?outputCurrency={symbol}'>Uniswap</a>")
    return " - ".join(links)

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")

    try:
        coingecko_coins = await fetch_coingecko_coins()
        pancakeswap_tokens = await fetch_pancakeswap_tokens()
        uniswap_tokens = await fetch_uniswap_tokens()

        # یک دیکشنری برای دسترسی سریع به توکن‌ها بر اساس symbol
        dex_tokens = {}
        for token in pancakeswap_tokens + uniswap_tokens:
            dex_tokens[token["symbol"].upper()] = token

        pumped_above_20 = []
        pumped_below_20 = []

        for coin in coingecko_coins:
            symbol = coin.get("symbol", "").upper()
            price = coin.get("current_price")
            vol = coin.get("total_volume", 0)
            chg_15m = coin.get("price_change_percentage_15m_in_currency")
            chg_30m = coin.get("price_change_percentage_30m_in_currency")
            chg_1h = coin.get("price_change_percentage_1h_in_currency")
            contract = coin.get("contract_address", None) or coin.get("platforms", {}).get("ethereum", None)
            # بررسی حجم معاملات حداقل
            if vol < VOLUME_MIN:
                continue

            # بررسی پامپ بر اساس 1 ساعت (می‌تونی تایم فریم دیگه اضافه کنی)
            if check_pump_percent(chg_1h, PUMP_THRESHOLD_1H):
                message = (
                    f"🚀 پامپ بالای ۲۰٪ شناسایی شد!\n"
                    f"🪙 {coin.get('name')} ({symbol})\n"
                    f"📈 رشد ۱۵ دقیقه: {chg_15m:.2f}%\n"
                    f"📈 رشد ۳۰ دقیقه: {chg_30m:.2f}%\n"
                    f"📈 رشد ۱ ساعت: {chg_1h:.2f}%\n"
                    f"💰 قیمت فعلی: ${price:.4f}\n"
                    f"📊 حجم معاملات: {vol:,}\n"
                    f"🔗 {format_contract_address(contract)}\n"
                    f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin.get('id')}\n"
                    f"🌐 دکس‌ها: {format_dex_links(symbol)}"
                )
                pumped_above_20.append(message)
            elif check_pump_percent(chg_1h, PUMP_THRESHOLD_15M):
                message = (
                    f"⚠️ پامپ زیر ۲۰٪ قابل توجه شناسایی شد!\n"
                    f"🪙 {coin.get('name')} ({symbol})\n"
                    f"📈 رشد ۱۵ دقیقه: {chg_15m:.2f}%\n"
                    f"📈 رشد ۳۰ دقیقه: {chg_30m:.2f}%\n"
                    f"📈 رشد ۱ ساعت: {chg_1h:.2f}%\n"
                    f"💰 قیمت فعلی: ${price:.4f}\n"
                    f"📊 حجم معاملات: {vol:,}\n"
                    f"🔗 {format_contract_address(contract)}\n"
                    f"🌐 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin.get('id')}\n"
                    f"🌐 دکس‌ها: {format_dex_links(symbol)}"
                )
                pumped_below_20.append(message)

        # ارسال پیام‌ها
        if pumped_above_20:
            for msg in pumped_above_20:
                await send_telegram_message(msg)
        else:
            await send_telegram_message("ℹ️ هیچ پامپ بالای ۲۰٪ یافت نشد.")

        if pumped_below_20:
            below20_text = "\n\n".join(pumped_below_20)
            await send_telegram_message(f"⚠️ پامپ‌های زیر ۲۰٪ قابل توجه:\n\n{below20_text}")

    except Exception as e:
        err_msg = f"❌ خطا در ربات:\n<pre>{e}</pre>"
        logger.error(err_msg)
        try:
            await send_telegram_message(err_msg)
        except Exception as ex:
            logger.error(f"خطا در ارسال پیام خطا به تلگرام: {ex}")

# ---------------------------- حلقه اصلی ----------------------------

async def main():
    logger.info("ربات شروع به کار کرد")
    await send_telegram_message("✅ ربات پامپ‌یاب ارتقا یافته شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
