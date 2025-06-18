import nest_asyncio
import asyncio
import json
import requests
from web3 import Web3
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from telegram import Update, Bot, InputMediaAnimation
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread
import os

# === KONFIGURATION ===
BOT_TOKEN = '7629429090:AAFWBHI-wXSweLENb0J-Iii1S_14Q-C1xew'
CHAT_ID = '-1002317784481'
PRESALE_CA = '0xC1D459AD4A5D2A6a9557640b6910941718F4fC59'
SOFTCAP_ETH = Decimal('8.6')
HARDCAP_ETH = Decimal('34.4')

# === WEB3 SETUP ===
w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))

# === STATUS ===
total_eth = Decimal('0')
total_usd = Decimal('0')

# === EINSTELLUNGEN ===
settings = {
    "gif_url": None,
    "emoji": "💸",
    "ratio": Decimal('10')  # 1 emoji pro 10 USD
}

# === TELEGRAM SETUP ===
bot = Bot(BOT_TOKEN)

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
        return Decimal(res.json()['ethereum']['usd'])
    except:
        return Decimal('3500')

def create_emoji_bar(amount_usd: Decimal):
    count = int((amount_usd / settings['ratio']).to_integral_value(rounding=ROUND_DOWN))
    return settings['emoji'] * count

def format_message(to_addr, value_eth, usd, total_eth, total_usd):
    percent = (total_eth / HARDCAP_ETH * 100).quantize(Decimal('0.01'))
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    emoji_bar = create_emoji_bar(usd)

    return (
        f"🚀 <b>New Presale Buy!</b>\n"
        f"💰 <b>Amount:</b> {value_eth:.4f} ETH (${usd:.2f}) {emoji_bar}\n"
        f"🕒 <b>Time:</b> {timestamp}\n\n"
        f"📊 <b>Total Raised:</b> {total_eth:.4f} ETH (${total_usd:.2f})\n"
        f"🎯 <b>Progress:</b> {percent}%"
    )

async def send_alert(to_addr, value_eth, usd):
    global total_eth, total_usd
    total_eth += value_eth
    total_usd += usd
    msg = format_message(to_addr, value_eth, usd, total_eth, total_usd)

    if settings['gif_url']:
        await bot.send_animation(chat_id=CHAT_ID, animation=settings['gif_url'], caption=msg, parse_mode='HTML')
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='HTML')

# === PRESALE MONITOR ===
async def monitor_presale():
    print("🔍 Monitoring ETH balance for Buy Events...")
    prev_balance = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))
    eth_price = get_eth_price()

    while True:
        await asyncio.sleep(5)
        new_balance = w3.eth.get_balance(Web3.to_checksum_address(PRESALE_CA))

        if new_balance > prev_balance:
            diff_wei = new_balance - prev_balance
            value_eth = Decimal(w3.from_wei(diff_wei, 'ether'))
            usd = value_eth * eth_price
            buyer = "Unknown"
            await send_alert(buyer, value_eth, usd)

        prev_balance = new_balance

# === KEEP ALIVE ===
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot ist online!"

def run_web():
    app_web.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))  

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# === BOT STARTEN ===
async def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("setgif", set_gif))
    app.add_handler(CommandHandler("setemoji", set_emoji))
    app.add_handler(CommandHandler("setratio", set_ratio))
    app.add_handler(CommandHandler("uptime", uptime))

    asyncio.create_task(monitor_presale())

    # Webhook Setup
    WEBHOOK_URL = f"https://buyalert-bot-pinksale.onrender.com/{BOT_TOKEN}"
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url=WEBHOOK_URL)

    print("✅ Bot läuft über Webhook.")

    # Starte Flask-Webhook-Server
    from telegram.ext import Application
    from telegram.ext.webhookhandler import WebhookHandler

    async def telegram_webhook():
        return await app.webhook_handler(request)

    app_web.add_url_rule(f"/{BOT_TOKEN}", view_func=lambda: asyncio.run(telegram_webhook()), methods=["POST"])

if __name__ == '__main__':
    asyncio.run(main())
