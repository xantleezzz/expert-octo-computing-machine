import numpy as np
from datetime import datetime
import logging
import talib


def example_strategy(prices, symbol, avg_period=5, take_profit_pct=2, stop_loss_pct=2):
    """
    Generates a simple trading signal based on the average price.

    Args:
        prices: A list or numpy array of prices.
        symbol: The trading symbol.
        avg_period: The period for calculating the average price.
        take_profit_pct: The take-profit percentage.
        stop_loss_pct: The stop-loss percentage.

    Returns:
        A dictionary containing the signal information or None if not enough data.
    """
    try:
        if len(prices) < avg_period:
            logging.warning(f"Not enough data for example strategy on {symbol}.")
            return None

        avg_price = np.mean(prices[-avg_period:])
        current_price = prices[-1]

        signal = "🔺Long" if current_price > avg_price else "🔻Short"

        take_profit = current_price * (1 + take_profit_pct / 100)
        stop_loss = current_price * (1 - stop_loss_pct / 100)

        signal_info = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "signal": signal,
            "current_price": current_price,
            "entry_range": (current_price * 0.99, current_price * 1.01),  # Можно сделать этот диапазон настраиваемым
            "take_profit": take_profit,
            "stop_loss": stop_loss,
        }

        logging.info(f"Example strategy generated signal for {symbol}: {signal} at {current_price}")
        return signal_info

    except Exception as e:
        logging.error(f"Error in example_strategy for {symbol}: {e}")
        return None


def aggregate_signals(signals, threshold=1):
    signal_counts = {"🔺Long": 0, "🔻Short": 0}
    final_signal = None

    for signal in signals:
        if signal and signal.get("signal"):  # Используем get для безопасного доступа
            signal_counts[signal["signal"]] += 1
            final_signal = signal

    total_signals = sum(signal_counts.values())

    if final_signal is not None and total_signals >= threshold:  # Добавили проверку на total_signals
        complete_signal_info = {
            "timestamp": final_signal.get("timestamp", datetime.now()),
            "symbol": final_signal.get("symbol"),
            # Упростили логику определения сигнала
            "signal": max(signal_counts, key=signal_counts.get),
            "entry_range": final_signal.get("entry_range", (None, None)),
            "take_profit": final_signal.get("take_profit"),
            "stop_loss": final_signal.get("stop_loss"),
            "current_price": final_signal.get("current_price"),
        }
        # Проверка наличия всех необходимых ключей
        required_keys = ["timestamp", "symbol", "signal", "entry_range", "take_profit", "stop_loss", "current_price"]
        if all(key in complete_signal_info for key in required_keys):
            return complete_signal_info

    return None


def generate_signals(model, scaler, prices, symbol, entry_range_pct=1, take_profit_pct=2, stop_loss_pct=2):
    """
    Generates trading signals based on a machine learning model.

    Args:
        model: The trained machine learning model.
        scaler: The scaler used for feature scaling.
        prices: A list or numpy array of prices.
        symbol: The trading symbol.
        entry_range_pct: The entry range percentage.
        take_profit_pct: The take-profit percentage.
        stop_loss_pct: The stop-loss percentage.

    Returns:
        A dictionary containing the signal information, or None if an error occurs.
    """

    logging.info(f"Generating signals for {symbol}...")

    if model is None or scaler is None:
        logging.error(f"Error generating signals for {symbol}: Model or scaler is None.")
        return None

    try:
        if not prices:
            raise ValueError("Prices array is empty.")

        rsi = talib.RSI(prices, timeperiod=14)[-1]
        sma = talib.SMA(prices, timeperiod=5)[-1]

        features = scaler.transform([[rsi, sma]])
        prediction = model.predict(features)[0]
        current_price = prices[-1]

        entry_range = (current_price * (1 - entry_range_pct / 100), current_price * (1 + entry_range_pct / 100))
        take_profit = current_price * (1 + take_profit_pct / 100)
        stop_loss = current_price * (1 - stop_loss_pct / 100)

        signal_info = {
            # ... (остальной код без изменений)
        }

        logging.info(f"Generated signal for {symbol}: {signal_info['signal']} at {current_price}")
        return signal_info

    except ValueError as e:  # Обработка пустого массива prices
        logging.error(f"Error generating signals for {symbol}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error generating signals for {symbol}: {e}")
        return None
