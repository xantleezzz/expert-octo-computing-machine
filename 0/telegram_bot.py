from data_handler import fetch_data, is_token_available
from model_handler import load_model, train_model, save_model  # Импортируйте train_model и save_model
from strategy import generate_signals
from utils import volatility_volume_alert, log_signal_to_csv  # Импортируйте log_signal_to_csv
import ccxt
import pandas as pd
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
import logging


# Обработчик команды /start
async def start(update: Update, context):
    """Функция для отправки приветственного сообщения при старте бота."""
    await update.message.reply_text("Привет! Введите токен для добавления.")


def create_token_keyboard(user_tickers):
    keyboard = [[InlineKeyboardButton(token, callback_data=f"signal_{token}")] for token in user_tickers]
    if user_tickers:
        keyboard.append([InlineKeyboardButton("Очистить", callback_data="clear")])
    return InlineKeyboardMarkup(keyboard)


async def button_handler(update: Update, context: CallbackContext, user_tickers: set, exchange, tickers, bot, chat_id, model_file, csv_file): #  Добавлен csv_file
    query = update.callback_query
    await query.answer()

    if query.data.startswith("signal_"):
        token = query.data.split("_")[1]
        symbol = f"{token}/USDT"

        if is_token_available(symbol, tickers):
            await generate_and_send_signal(symbol, exchange, tickers, bot, chat_id, model_file)
            await query.message.reply_text(f"Сигнал для {token} отправлен.")  # Пока просто сообщение
        else:
            await query.message.reply_text(f"Токен {token} недоступен.")

    elif query.data == "clear":
        user_tickers.clear()
        await query.message.reply_text("Все токены очищены.")

        # Обновляем клавиатуру после очистки
        reply_markup = create_token_keyboard(user_tickers)
        await update.message.reply_text("Выберите токен:", reply_markup=reply_markup)

async def get_data(update: Update, context: ContextTypes.DEFAULT_TYPE, exchange, tickers, user_tickers, bot, chat_id):
    try:
        command_parts = update.message.text.split()
        if len(command_parts) < 2:
            raise IndexError("Не указан токен.")
        elif len(command_parts) > 2:
            raise IndexError("Введено слишком много аргументов. Укажите только токен.")

        token = command_parts[1].upper()
        symbol = f"{token}/USDT"

        if not is_token_available(symbol, tickers):
            await update.message.reply_text(f"Токен {token} недоступен на бирже.")
            return

        data = fetch_data(exchange, symbol)
        if data is not None:
            if not data.empty:
                output_data = data[["timestamp", "open", "close"]].head(10)
                output_string = output_data.to_string()
                await update.message.reply_text(f"Данные для {symbol}:\n```\n{output_string}\n```",
                                                parse_mode='MarkdownV2')

                # Отправка клавиатуры:
                reply_markup = create_token_keyboard(user_tickers)
                await update.message.reply_text("Выберите токен:", reply_markup=reply_markup)

            else:
                await update.message.reply_text(f"Пустые данные для {symbol}")
        else:
            await update.message.reply_text(f"Ошибка получения данных для {symbol}")

    except IndexError as e:
        await update.message.reply_text(str(e))
    except ccxt.NetworkError as e:
        await update.message.reply_text(f"Ошибка сети: {e}")
    except ccxt.ExchangeError as e:
        await update.message.reply_text(f"Ошибка биржи: {e}")
    except pd.errors.EmptyDataError:
        await update.message.reply_text(f"Пустой DataFrame для {symbol}")
    except Exception as e:
        await update.message.reply_text(f"Произошла неизвестная ошибка: {e}")


async def generate_and_send_signal(symbol, exchange, tickers, bot, chat_id, model_file, csv_file):  # Добавлен csv_file
    """Generates and sends a trading signal.

    Args:
        symbol: The trading symbol.
        exchange: The ccxt exchange object.
        tickers: List of available tickers.
        bot: telegram bot instance.
        chat_id: The Telegram chat ID.
        model_file: The path to the model file.
    """
    try:
        data = fetch_data(exchange, symbol)  # Передаем exchange

        if data is None or data.empty:
            logging.error(f"No data available for {symbol}.")
            return

        model, scaler = load_model(model_file, tickers, exchange)  # Передаем model_file, tickers, exchange

        if model is not None and scaler is not None:  # Проверка на None
            signal_info = generate_signals(model, scaler, data["close"].values, symbol)
            if signal_info:
                await send_signal(signal_info, bot, chat_id)  # Передаем bot и chat_id
            else:
                logging.warning(f"No signal generated for {symbol}.")

            last_accuracy = context.user_data.get("last_accuracy", 1.0)  # Добавьте сохранение accuracy в user_data
            retrain_condition = last_accuracy < 0.7  # Переобучать если accuracy < 0.7
            context.user_data["last_accuracy"] = accuracy  # accuracy  должно быть доступно в функции
            if retrain_condition:
                try:
                    model, scaler = train_model(tickers, exchange, model_file)
                    if model is not None and scaler is not None:
                        save_model(model, scaler, model_file)
                        logging.info(f"Model retrained and saved to {model_file}")
                    else:
                        logging.error("Failed to retrain model")
                except Exception as e:
                    logging.error(f"Error retraining model: {e}")
        else:
            logging.error("Model not available for generating signals.")

        trend_status = data["trend"].iloc[
            -1] if "trend" in data.columns else "N/A"  # Проверка на существование столбца.
        await bot.send_message(chat_id=chat_id, text=f"Текущий тренд для {symbol}: {trend_status}")

        await volatility_volume_alert(symbol, data, bot, chat_id)  # Передаем bot и chat_id, если нужно

    except Exception as e:
        logging.error(f"Error in generating and sending signal for {symbol}: {e}")


# Отправка сигнала в Telegram
async def send_signal(signal_info, bot: Bot, chat_id, csv_file): #  Добавлен csv_file
    """Sends a trading signal to Telegram.

    Args:
        signal_info (dict): A dictionary containing the signal information.
        bot (telegram.Bot): The Telegram bot instance.
        chat_id (int): The Telegram chat ID.
    """
    try:
        required_keys = [
            "timestamp", "symbol", "signal", "entry_range",
            "take_profit", "stop_loss", "current_price"
        ]

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


        # Отправка сообщения в Telegram
        await bot.send_message(chat_id=chat_id, text=message)  # Используем chat_id из аргументов

        log_signal_to_csv(signal_info, csv_file)

    from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes, CallbackContext
    import logging

    async def handle_message(update: Update, context: CallbackContext, user_tickers: list, max_tickers: int = 5):
        try:
            user_input = update.message.text.strip().upper()

            if user_input and not user_input.endswith("/USDT"):
                user_input += "/USDT"

            logging.info(f"User input: {user_input}")

            if is_token_available(user_input):  # Предполагается, что эта функция определена где-то еще
                if len(user_tickers) < max_tickers:
                    user_tickers.append(user_input)
                    await update.message.reply_text(f"Токен {user_input} добавлен.")

                    # Создаем клавиатуру только один раз и обновляем её
                    keyboard = create_token_keyboard(user_tickers)
                    await update.message.reply_text("Выберите токен:", reply_markup=keyboard)
                else:
                    await update.message.reply_text(f"Вы достигли максимального количества токенов ({max_tickers}).")
            else:
                await update.message.reply_text(f"Токен {user_input} недоступен на бирже.")


        except Exception as e:
            logging.error(f"Error handling message: {e}")
            await update.message.reply_text("Произошла ошибка при обработке сообщения.")

    def create_token_keyboard(user_tickers):  # Теперь принимает user_tickers как аргумент
        keyboard = [[InlineKeyboardButton(token, callback_data=f"signal_{token}")] for token in user_tickers]
        if user_tickers:
            keyboard.append([InlineKeyboardButton("Очистить", callback_data="clear")])
        return InlineKeyboardMarkup(keyboard)

    except Exception as e:
        logging.error(f"Error sending signal: {e}")

