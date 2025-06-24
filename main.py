from aiohttp import web
import asyncio
import requests
from web3 import Web3
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

# === KONFIGURATION ===
BOT_TOKEN = '7629429090:AAFWBHI-wXSweLENb0J-Iii1S_14Q-C1xew'
CHAT_ID = '-1002317784481'
PRESALE_CA = '0xC1D459AD4A5D2A6a9557640b6910941718F4fC59'
SOFTCAP_ETH = Decimal('8.6')
HARDCAP_ETH = Decimal('34.4')
WEBHOOK_BASE_URL = 'https://buyalert-bot-pinksale.onrender.com'
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/{BOT_TOKEN}"

# === WEB3 SETUP ===
w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))

# === STATUS ===
total_eth = Decimal('0')
total_usd = Decimal('0')
initial_balance_eth = Decimal('0')  # Startwert des Contracts vor Bot-Start

# === EINSTELLUNGEN ===
settings = {
    "gif_url": None,
    "emoji": "💸",
    "ratio": Decimal('10')  # 1 Emoji pro 10 USD
}

# === KOMMANDOS ===
async def set_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        settings["gif_url"] = context.args[0]
        await update.message.reply_text("✅ GIF gesetzt.")
    else:
        await update.message.reply_text("❌ Bitte gib eine gültige GIF-URL an.")

async def set_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        settings["emoji"] = context.args[0]
        await update.message.reply_text(f"✅ Emoji gesetzt: {settings['emoji']}")
    else:
        await update.message.reply_text("❌ Bitte gib ein Emoji an.")

async def set_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            ratio = Decimal(context.args[0])
            settings["ratio"] = ratio
            await update.message.reply_text(f"✅ Ratio gesetzt: 1 Emoji pro ${ratio}")
        except:
            await update.message.reply_text("❌ Ungültige Zahl für Ratio.")
    else:
        await update.message.reply_text("❌ Bitte gib eine Zahl an.")

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Ich bin online und arbeite!")

# === HELFER ===
def get_eth_price():
    try:
        res = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        return Decimal(str(res.json()['ethereum']['usd']))
    except:
        return Decimal('3500')

def create_emoji_bar(amount_usd: Decimal):
    count = int((amount_usd / settings['ratio']).to_integral_value(rounding=ROUND_DOWN))
    return settings['emoji'] * count

def format_message(to_addr, value_eth, usd, total_eth, total_usd):
    def progress_bar(percent, length=10):
        filled = int((percent / 100) * length)
        empty = length - filled
        return '▰' * filled + '▱' * empty

    softcap_percent = min((total_eth / SOFTCAP_ETH * 100).quantize(Decimal('0.1')), Decimal('100'))
    hardcap_percent = min((total_eth / HARDCAP_ETH * 100).quantize(Decimal('0.1')), Decimal('100'))

    softcap_status = "✅" if softcap_percent >= 100 else "❌"
    hardcap_status = "✅" if hardcap_percent >= 100 else "❌"

    softcap_bar = progress_bar(softcap_percent)
    hardcap_bar = progress_bar(hardcap_percent)

    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    emoji_bar = create_emoji_bar(usd)

    return (
        f"🚀 <b>New Presale Buy!</b>\n"
        f"💰 <b>Amount:</b> {value_eth:.4f} ETH (${usd:.2f}) {emoji_bar}\n"
        f"🕒 <b>Time:</b> {timestamp}\n\n"
        f"📊 <b>Total Raised:</b> {total_eth:.4f} ETH (${total_usd:.2f})\n\n"
        f"📈 <b>Softcap:</b> {softcap_bar} {softcap_percent}% {softcap_status}\n"
        f"🎯 <b>Hardcap:</b> {hardcap_bar} {hardcap_percent}% {hardcap_status}\n"
        f"🔗 <b>Contract:</b> <a href='https://base.blockscan.com/address/{PRESALE_CA}'>Link</a>"
    )

async def send_alert(application, to_addr, value_eth, usd):
    global total_eth, total_usd
    total_eth += value_eth
    total_usd += usd
    msg = format_message(to_addr, value_eth, usd, total_eth, total_usd)

    if settings['gif_url']:
        await application.bot.send_animation(chat_id=CHAT_ID, animation=settings['gif_url'], caption=msg, parse_mode='HTML')
    else:
        await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='HTML')

# === PRESALE MONITOR ===
async def monitor_presale(application):
    global total_eth, total_usd, initial_balance_eth

    print("🔍 Monitoring ETH balance for Buy Events...")
    prev_balance_wei = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))
    prev_balance_eth = Decimal(w3.from_wei(prev_balance_wei, 'ether'))
    initial_balance_eth = prev_balance_eth  # Startwert speichern
    eth_price = get_eth_price()
    total_eth = initial_balance_eth
    total_usd = total_eth * eth_price

    while True:
        await asyncio.sleep(5)
        try:
            new_balance_wei = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))
            new_balance_eth = Decimal(w3.from_wei(new_balance_wei, 'ether'))

            if new_balance_eth > prev_balance_eth:
                diff_eth = new_balance_eth - prev_balance_eth
                usd = diff_eth * get_eth_price()
                buyer = "Unknown"
                await send_alert(application, buyer, diff_eth, usd)

            prev_balance_eth = new_balance_eth
        except Exception as e:
            print(f"Fehler beim Monitoring: {e}")

# === MAIN ===
async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Telegram Commands registrieren
    application.add_handler(CommandHandler("setgif", set_gif))
    application.add_handler(CommandHandler("setemoji", set_emoji))
    application.add_handler(CommandHandler("setratio", set_ratio))
    application.add_handler(CommandHandler("uptime", uptime))

    # Bot initialisieren & starten
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL)

    # Presale Monitor starten
    asyncio.create_task(monitor_presale(application))

    # Webserver für Telegram Webhook starten
    async def handle(request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response()

    async def handle_root(request):
        return web.Response(text="✅ BuyAlert Bot läuft!")

    app = web.Application()
    app.router.add_post(f'/{BOT_TOKEN}', handle)
    app.router.add_get('/', handle_root)

    port = int(os.environ.get("PORT", 8080))
    print(f"✅ Webhook läuft auf Port {port}")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Am Leben halten
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
