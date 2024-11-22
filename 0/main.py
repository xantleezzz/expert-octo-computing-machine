import asyncio
import logging
import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram_bot import start, handle_message, button_handler
from model_handler import load_model
from data_handler import load_tickers, initialize_csv
from utils import create_token_keyboard


async def initialize_bot(telegram_token):
    """Инициализирует бота Telegram."""
    application = ApplicationBuilder().token(telegram_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    return application


async def run_bot(application):
    """Запускает бота."""
    await application.run_polling()


async def initialize_app():
    """Инициализирует все компоненты приложения."""
    logging.info("Starting the bot...")
    load_tickers()
    initialize_csv()
    model, scaler = load_model()  # Загрузка модели - можно вынести в отдельную функцию, если потребуется переобучение
    return model, scaler


async def main():
    """Основная функция запуска."""
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("CHAT_ID")  # Не используется, пока что

    if not telegram_token:
        logging.critical("TELEGRAM_TOKEN not found in environment variables.")
        return

    try:
        model, scaler = await initialize_app()
        application = await initialize_bot(telegram_token)
        await run_bot(application)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")