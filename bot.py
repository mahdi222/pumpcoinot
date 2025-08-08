import asyncio
from web3 import Web3
from telegram import Bot
import os

# ---------------- Config from Environment ----------------
WSS = os.getenv("BSC_WSS")  # WebSocket RPC endpoint (Ankr, Infura, QuickNode)
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
ALLOWED_IDS = [int(x) for x in os.getenv("TG_ALLOWED_IDS").split(",")]
FACTORY_ADDRESS = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"  # PancakeSwap Factory (BSC)

# ---------------- Web3 + Telegram ----------------
w3 = Web3(Web3.WebsocketProvider(WSS))
bot = Bot(token=TELEGRAM_TOKEN)

FACTORY_ABI = [{
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
        {"indexed": False, "internalType": "address", "name": "pair", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "", "type": "uint256"}
    ],
    "name": "PairCreated",
    "type": "event"
}]

factory = w3.eth.contract(address=w3.toChecksumAddress(FACTORY_ADDRESS), abi=FACTORY_ABI)

# ---------------- Bot Functions ----------------
async def send_alert(msg):
    for chat_id in ALLOWED_IDS:
        await bot.send_message(chat_id=chat_id, text=msg)

async def handle_event(event):
    token0 = event['args']['token0']
    token1 = event['args']['token1']
    pair = event['args']['pair']
    msg = f"🚀 New Pair Created!\nToken0: {token0}\nToken1: {token1}\nPair: {pair}"
    await send_alert(msg)

async def log_loop(event_filter, poll_interval):
    while True:
        for event in event_filter.get_new_entries():
            await handle_event(event)
        await asyncio.sleep(poll_interval)

def main():
    event_filter = factory.events.PairCreated.create_filter(fromBlock='latest')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(log_loop(event_filter, 2))

if __name__ == '__main__':
    main()
