import os
import asyncio
import logging
import httpx
from telegram import Bot
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغیرهای محیطی (محافظت شده و نام تغییر نکرده)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

PUMP_THRESHOLD_15M = float(os.getenv("PUMP_THRESHOLD_15M", "0.1"))
PUMP_THRESHOLD_30M = float(os.getenv("PUMP_THRESHOLD_30M", "0.1"))
PUMP_THRESHOLD_1H = float(os.getenv("PUMP_THRESHOLD_1H", "0.1"))

VOLUME_MIN = float(os.getenv("VOLUME_MIN", "10000"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # ثانیه، پیش‌فرض 5 دقیقه

bot = Bot(token=TELEGRAM_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "X-CoinGecko-Api-Key": COINGECKO_API_KEY or ""
}

# اطلاعات صرافی‌ها و API های مربوط به شبکه‌ها
DEX_INFO = {
    "bsc": {
        "name": "Binance Smart Chain",
        "scan_api": "https://api.bscscan.com/api",
        "scan_api_key": ETHERSCAN_API_KEY,
        "dexes": {
            "PancakeSwap": "https://pancakeswap.finance/swap?outputCurrency={contract}",
            # میشه دکس‌های دیگه اضافه کرد
        }
    },
    "eth": {
        "name": "Ethereum",
        "scan_api": "https://api.etherscan.io/api",
        "scan_api_key": ETHERSCAN_API_KEY,
        "dexes": {
            "Uniswap": "https://app.uniswap.org/#/swap?outputCurrency={contract}",
            # دکس‌های بیشتر مثل Sushiswap اضافه بشه
        }
    },
    "polygon": {
        "name": "Polygon (Matic)",
        "scan_api": "https://api.polygonscan.com/api",
        "scan_api_key": ETHERSCAN_API_KEY,
        "dexes": {
            "QuickSwap": "https://quickswap.exchange/#/swap?outputCurrency={contract}",
        }
    },
    "solana": {
        "name": "Solana",
        "helius_api_key": HELIUS_API_KEY,
        "dexes": {
            "Serum": "https://dex.projectserum.com/#/market/{symbol}",  # با نماد بازار
        }
    }
}

async def fetch_coingecko_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": "100",
        "page": "1",
        "sparkline": "false",
        "price_change_percentage": "15m,30m,1h"
    }
    async with httpx.AsyncClient(headers=HEADERS) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise ValueError(f"خطای API کوین‌گکو: {resp.status_code} - {resp.text}")
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"خروجی API کوین‌گکو لیست نیست! نوع داده: {type(data)}")
        return data

async def fetch_bsc_token_info(contract_address):
    """ دریافت اطلاعات توکن از BscScan """
    base_url = DEX_INFO["bsc"]["scan_api"]
    api_key = DEX_INFO["bsc"]["scan_api_key"]
    params = {
        "module": "token",
        "action": "tokeninfo",
        "contractaddress": contract_address,
        "apikey": api_key,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(base_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            return data
        else:
            logger.warning(f"BscScan token info error: {resp.status_code}")
            return None

async def fetch_etherscan_token_info(contract_address):
    """ دریافت اطلاعات توکن از Etherscan """
    base_url = DEX_INFO["eth"]["scan_api"]
    api_key = DEX_INFO["eth"]["scan_api_key"]
    params = {
        "module": "token",
        "action": "tokeninfo",
        "contractaddress": contract_address,
        "apikey": api_key,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(base_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            return data
        else:
            logger.warning(f"Etherscan token info error: {resp.status_code}")
            return None

# مشابه برای Polygon و Solana هم میشه توابع اضافه کرد (در صورت نیاز)

def format_dex_links(network_key, contract_address, symbol=""):
    dex_links = []
    info = DEX_INFO.get(network_key)
    if not info:
        return dex_links
    for dex_name, url_template in info["dexes"].items():
        if network_key == "solana":
            # برای سولانا نماد بازار میخوایم نه کانترکت
            if symbol:
                link = url_template.format(symbol=symbol)
                dex_links.append(f"[{dex_name}]({link})")
        else:
            if contract_address:
                link = url_template.format(contract=contract_address)
                dex_links.append(f"[{dex_name}]({link})")
    return dex_links

def create_pump_message(coin):
    # نمونه ساده پیام شامل نام، قیمت، پامپ و لینک کانترکت و صرافی‌ها
    contract_address = coin.get("contract_address") or "ندارد"
    symbol = coin.get("symbol") or ""
    dex_links = []

    # شبکه رو تشخیص بده - فعلاً فقط چندتا شبکه اصلی که می‌خوایم
    platform = coin.get("platforms", {})
    network_keys = []
    for net_key in DEX_INFO.keys():
        if net_key in platform and platform[net_key]:
            network_keys.append(net_key)
    # اگر کانترکت نداشتیم بررسی کنیم
    if not network_keys and coin.get("id"):
        # fallback
        network_keys.append("eth")

    for net_key in network_keys:
        dex_links.extend(format_dex_links(net_key, platform.get(net_key), symbol))

    dex_str = ", ".join(dex_links) if dex_links else "بدون صرافی شناخته شده"

    message = (
        f"🚀 پامپ شناسایی شد!\n"
        f"🪙 {coin.get('name')} ({symbol.upper()})\n"
        f"📈 رشد ۱ ساعته: {coin.get('price_change_percentage_1h_in_currency', 0):.2f}%\n"
        f"💰 قیمت فعلی: ${coin.get('current_price')}\n"
        f"📊 حجم معاملات: {coin.get('total_volume')}\n"
        f"🔗 آدرس کانترکت: {contract_address}\n"
        f"🌐 صرافی‌ها: {dex_str}\n"
        f"🔗 لینک کوین در کوین‌گکو:\nhttps://www.coingecko.com/en/coins/{coin.get('id')}"
    )
    return message

async def send_telegram_message(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام تلگرام: {e}")

async def check_pump():
    logger.info("check_pump داره اجرا میشه...")
    try:
        coins = await fetch_coingecko_coins()
        pump_found = False

        for coin in coins:
            # فقط پامپ‌های بزرگ 1 ساعته با حجم حداقل
            if (
                coin.get("price_change_percentage_1h_in_currency", 0) >= PUMP_THRESHOLD_1H and
                coin.get("total_volume", 0) >= VOLUME_MIN
            ):
                message = create_pump_message(coin)
                await send_telegram_message(message)
                pump_found = True

        if not pump_found:
            logger.info("هیچ پامپی یافت نشد.")
            await send_telegram_message("ℹ️ پامپی یافت نشد.")

    except Exception as e:
        logger.error(f"❌ خطا در ربات:\n{e}")
        await send_telegram_message(f"❌ خطا در ربات:\n<pre>{str(e)}</pre>")

async def main():
    logger.info("ربات شروع به کار کرد")
    await send_telegram_message("✅ ربات پامپ‌یاب حرفه‌ای شروع به کار کرد.")
    while True:
        await check_pump()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
