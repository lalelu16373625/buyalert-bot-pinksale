import asyncio
import requests
from web3 import Web3
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
import os

# === KONFIGURATION ===
BOT_TOKEN = '7629429090:AAFWBHI-wXSweLENb0J-Iii1S_14Q-C1xew'  # Dein Telegram-Bot-Token
CHAT_ID = '-1002317784481'  # Deine Telegram-Chat-ID (Gruppe oder Kanal)
PRESALE_CA = '0xC1D459AD4A5D2A6a9557640b6910941718F4fC59'  # Presale Contract-Adresse
SOFTCAP_ETH = Decimal('8.6')
HARDCAP_ETH = Decimal('34.4')
WEBHOOK_BASE_URL = 'https://buyalert-bot-pinksale.onrender.com'  # Deine öffentliche URL bei Render etc.
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/{BOT_TOKEN}"

# === WEB3 SETUP ===
w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))

# === GLOBALER STATUS ===
total_eth = Decimal('0')
total_usd = Decimal('0')

# === EINSTELLUNGEN ===
settings = {
    "gif_url": None,
    "emoji": "💸",
    "ratio": Decimal('10')  # 1 Emoji pro 10 USD
}

# === TELEGRAM COMMANDS ===
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

# === HILFSFUNKTIONEN ===
def get_eth_price() -> Decimal:
    try:
        res = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd', timeout=10)
        return Decimal(str(res.json()['ethereum']['usd']))
    except Exception:
        return Decimal('3500')  # Fallback-Preis

def create_emoji_bar(amount_usd: Decimal) -> str:
    count = int((amount_usd / settings['ratio']).to_integral_value(rounding=ROUND_DOWN))
    return settings['emoji'] * count

def format_message(to_addr: str, value_eth: Decimal, usd: Decimal, total_eth: Decimal, total_usd: Decimal) -> str:
    percent = (total_eth / HARDCAP_ETH * 100).quantize(Decimal('0.01'))
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    emoji_bar = create_emoji_bar(usd)
    return (
        f"🚀 <b>New Presale Buy!</b>\n"
        f"💰 <b>Amount:</b> {value_eth:.4f} ETH (${usd:.2f}) {emoji_bar}\n"
        f"🕒 <b>Time:</b> {timestamp}\n\n"
        f"📊 <b>Total Raised:</b> {total_eth:.4f} ETH (${total_usd:.2f})\n"
        f"🎯 <b>Progress:</b> {percent}%\n"
        f"🔗 <b>Contract:</b> <a href='https://base.blockscan.com/address/{PRESALE_CA}'>Link</a>"
    )

async def send_alert(application, to_addr: str, value_eth: Decimal, usd: Decimal):
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
    print("🔍 Monitoring ETH balance for Buy Events...")
    prev_balance = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))

    while True:
        await asyncio.sleep(5)
        try:
            new_balance = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))
            if new_balance > prev_balance:
                diff_wei = new_balance - prev_balance
                value_eth = Decimal(w3.from_wei(diff_wei, 'ether'))
                eth_price = get_eth_price()
                usd = value_eth * eth_price
                buyer = "Unknown"
                await send_alert(application, buyer, value_eth, usd)
            prev_balance = new_balance
        except Exception as e:
            print(f"Fehler beim Monitoring: {e}")

# === START-FUNKTION ===
async def run():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Telegram Commands registrieren
    application.add_handler(CommandHandler("setgif", set_gif))
    application.add_handler(CommandHandler("setemoji", set_emoji))
    application.add_handler(CommandHandler("setratio", set_ratio))
    application.add_handler(CommandHandler("uptime", uptime))

    # Starte Presale-Monitor parallel
    asyncio.create_task(monitor_presale(application))

    # Starte Webhook (wartet intern auf Updates)
    await application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True,
    )

# === ENTRYPOINT ===
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(run())
    loop.run_forever()
