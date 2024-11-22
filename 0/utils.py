import os
import csv
from config import CSV_FILE
import logging
from telegram import Bot

def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "timestamp",
                    "symbol",
                    "signal",
                    "entry_range_low",
                    "entry_range_high",
                    "take_profit",
                    "stop_loss",
                    "current_price",
                ]
            )


def log_signal_to_csv(signal_info, csv_file):  # Добавлен csv_file как аргумент
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                signal_info['timestamp'], signal_info['symbol'], signal_info['signal'],
                signal_info['entry_range'][0], signal_info['entry_range'][1],
                signal_info['take_profit'], signal_info['stop_loss'], signal_info['current_price']
            ])
    except Exception as e:
        logging.error(f"Error logging signal to CSV: {e}")



async def volatility_volume_alert(bot: Bot, symbol, data, volatility_threshold=1.5, volume_threshold=1.5):
    """Отправляет оповещения о высокой волатильности или объеме."""
    try:
        if data["volatility"].iloc[-1] > data["volatility"].mean() * volatility_threshold:
            await bot.send_message(chat_id=CHAT_ID, text=f"Высокая волатильность для {symbol}")
        if data["market_volume"].iloc[-1] > data["market_volume"].mean() * volume_threshold:
            await bot.send_message(chat_id=CHAT_ID, text=f"Высокий объем для {symbol}")
    except Exception as e:
        logging.error(f"Error sending volatility/volume alert for {symbol}: {e}")