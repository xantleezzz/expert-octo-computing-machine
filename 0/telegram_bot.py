from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from data_handler import fetch_data, is_token_available
from model_handler import load_model, train_model, save_model
from strategy import generate_signals, aggregate_signals
from utils import volatility_volume_alert, log_signal_to_csv
import logging
from datetime import datetime


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Введите токен для добавления.")


def create_token_keyboard(user_tickers):
    keyboard = [[InlineKeyboardButton(token, callback_data=f"signal_{token}")] for token in user_tickers]
    if user_tickers:
        keyboard.append([InlineKeyboardButton("Очистить", callback_data="clear")])
    return InlineKeyboardMarkup(keyboard)


async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    chat_data = context.chat_data
    if query.data.startswith("signal_"):
        token = query.data.split("_")[1]
        symbol = f"{token}/USDT"
        if is_token_available(symbol, chat_data['tickers']):
            await generate_and_send_signal(update, context, symbol)
        else:
            await query.message.reply_text(f"Токен {token} недоступен.")
    elif query.data == "clear":
        context.chat_data['user_tickers'] = []
        await query.message.reply_text("Все токены очищены.")
        reply_markup = create_token_keyboard([])
        await update.message.reply_text("Выберите токен:", reply_markup=reply_markup)


async def handle_message(update: Update, context: CallbackContext):
    try:
        user_input = update.message.text.strip().upper()
        if user_input and not user_input.endswith("/USDT"):
            user_input += "/USDT"
        logging.info(f"User input: {user_input}")
        chat_data = context.chat_data
        if not chat_data:
            chat_data = context.chat_data = {}
            chat_data['user_tickers'] = []

        if is_token_available(user_input, chat_data['tickers']):
            if len(chat_data['user_tickers']) < 5:
                chat_data['user_tickers'].append(user_input)
                await update.message.reply_text(f"Токен {user_input} добавлен.")
                keyboard = create_token_keyboard(chat_data['user_tickers'])
                await update.message.reply_text("Выберите токен:", reply_markup=keyboard)
            else:
                await update.message.reply_text("Вы достигли максимального количества токенов (5).")
        else:
            await update.message.reply_text(f"Токен {user_input} недоступен на бирже.")
    except Exception as e:
        logging.exception(f"Error handling message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке сообщения.")


async def generate_and_send_signal(update: Update, context: CallbackContext, symbol):
    chat_data = context.chat_data
    try:
        data = fetch_data(chat_data['exchange'], symbol)
        if data is None or data.empty:
            logging.error(f"No data available for {symbol}.")
            return
        model, scaler = chat_data['model'], chat_data['scaler']
        if model is not None and scaler is not None:
            signal_info = generate_signals(model, scaler, data["close"].values, symbol)
            if signal_info:
                await send_signal(update, context, signal_info)
            else:
                logging.warning(f"No signal generated for {symbol}.")

            last_accuracy = context.user_data.get("last_accuracy", 1.0)
            if last_accuracy < 0.7:
                try:
                    model, scaler = train_model(chat_data['exchange'], chat_data['tickers'], chat_data['model_file'])
                    if model is not None and scaler is not None:
                        save_model(model, scaler, chat_data['model_file'])
                        logging.info(f"Model retrained and saved to {chat_data['model_file']}")
                        chat_data['model'], chat_data['scaler'] = model, scaler
                    else:
                        logging.error("Failed to retrain model")
                except Exception as e:
                    logging.error(f"Error retraining model: {e}")
        else:
            logging.error("Model not available for generating signals.")
        trend_status = data["trend"].iloc[-1] if "trend" in data.columns else "N/A"
        await update.message.reply_text(f"Текущий тренд для {symbol}: {trend_status}")
        await volatility_volume_alert(symbol, data, update, context)
    except Exception as e:
        logging.exception(f"Error in generate_and_send_signal: {e}")



async def send_signal(update: Update, context: CallbackContext, signal_info):
    try:
        required_keys = ["timestamp", "symbol", "signal", "entry_range", "take_profit", "stop_loss", "current_price"]
        if not all(key in signal_info for key in required_keys):
            missing_keys = [key for key in required_keys if key not in signal_info]
            logging.error(f"Signal info is missing required fields: {missing_keys}")
            return

        entry_range = signal_info["entry_range"]
        message = (
            f"Сигнал на {signal_info['symbol']}:\n"
            f"Сигнал: {signal_info['signal']}\n"
            f"Диапазон входа: {entry_range[0]} - {entry_range[1]}\n"
            f"Take Profit: {signal_info['take_profit']}\n"
            f"Stop Loss: {signal_info['stop_loss']}\n"
            f"Текущая цена: {signal_info['current_price']}"
        )

        await update.message.reply_text(text=message)
        log_signal_to_csv(signal_info, context.chat_data['csv_file'])

    except Exception as e:
        logging.exception(f"Error sending signal: {e}")
