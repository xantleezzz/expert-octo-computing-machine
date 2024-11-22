import asyncio
import logging
import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram_bot import start, handle_message, button_handler
from model_handler import load_model, train_model, save_model
from data_handler import load_tickers, initialize_csv
from utils import create_token_keyboard
import ccxt
from config import API_KEY, API_SECRET, TELEGRAM_TOKEN, CHAT_ID, MODEL_FILE, CSV_FILE, EXCHANGE_ID

async def initialize_bot(telegram_token, bot_data):
    application = ApplicationBuilder().token(telegram_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler, pass_job_queue=True, pass_chat_data=True))
    return application


async def run_bot(application):
    await application.run_polling()


async def initialize_app(exchange_id, api_key, api_secret):
    logging.info("Starting the bot...")
    exchange = getattr(ccxt, exchange_id)({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    tickers = load_tickers(exchange)
    initialize_csv()
    model, scaler = load_model(MODEL_FILE, tickers, exchange)
    return exchange, tickers, model, scaler


async def main():
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    if not telegram_token:
        logging.critical("TELEGRAM_TOKEN not found in environment variables.")
        return

    try:
        exchange, tickers, model, scaler = await initialize_app(EXCHANGE_ID, API_KEY, API_SECRET)
        bot = ccxt.binance({'apiKey': API_KEY, 'secret': API_SECRET, 'enableRateLimit': True})
        application = await initialize_bot(telegram_token, {'exchange': exchange, 'tickers': tickers, 'model': model, 'scaler': scaler, 'model_file': MODEL_FILE, 'csv_file': CSV_FILE})
        await run_bot(application)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
