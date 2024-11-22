import ccxt
import numpy as np
import talib
import pandas as pd
import ccxt
import logging
import os


def fetch_data(exchange, symbol, timeframe="1d", limit=500, parquet_file="all_tickers_data.parquet"):
    """Fetches OHLCV data for a symbol from a Parquet file or exchange.

    Args:
        exchange: The ccxt exchange object.
        symbol: The trading symbol.
        timeframe: The timeframe for OHLCV data.
        limit: The maximum number of bars to fetch.
        parquet_file: The path to the Parquet file.

    Returns:
        pd.DataFrame or None: DataFrame with OHLCV data, or None if an error occurs.
    """

    try:
        if os.path.exists(parquet_file) and os.path.getsize(parquet_file) > 0:
            data = pd.read_parquet(parquet_file)
            data = data[data["symbol"] == symbol]
            if not data.empty:
                return calculate_adx_and_trend(data)  # Вызываем calculate_adx_and_trend здесь

        logging.info(f"Fetching {symbol} from exchange")  # Moved before fetch attempt.

        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        # Преобразование к DataFrame с приведением типов
        data = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])

        for col in ["open", "high", "low", "close", "volume"]:
            data[col] = pd.to_numeric(data[col], errors='coerce')

        data["symbol"] = symbol
        data = calculate_adx_and_trend(data)  # Вызов calculate_adx_and_trend
        data.to_parquet(parquet_file, index=False, engine='pyarrow')

        return data

    except ccxt.NetworkError as e:
        logging.error(f"Network error fetching {symbol}: {e}")
        return None
    except ccxt.ExchangeError as e:
        logging.error(f"Exchange error fetching {symbol}: {e}")
        return None
    except OSError as e:  # добавлена обработка OSError
        logging.error(f"File system error with {parquet_file}: {e}")
        return None


    except Exception as e:
        logging.error(f"Error fetching {symbol}: {e}")
        return None


def prepare_data(data, period=14):
    try:
        # Вычисление индикаторов с помощью талиба
        data["RSI"] = talib.RSI(data["close"].astype(float), timeperiod=period)
        data["SMA"] = talib.SMA(data["close"].astype(float), timeperiod=5)  # SMA с периодом 5
        data["volatility"] = data["close"].rolling(window=20).std()
        data["market_volume"] = data["volume"].rolling(window=20).mean()
        macd, macdsignal, macdhist = talib.MACD(data['close'].astype(float), fastperiod=12, slowperiod=26,
                                                signalperiod=9)
        data["MACD"] = macd
        data["MACD_signal"] = macdsignal
        upper, middle, lower = talib.BBANDS(data['close'].astype(float), timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        data["BB_upper"] = upper
        data["BB_middle"] = middle
        data["BB_lower"] = lower
        data['ATR'] = talib.ATR(data['high'].astype(float), data['low'].astype(float), data['close'].astype(float),
                                timeperiod=14)

        data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)

        # Удаляем строки с NaN после вычисления индикаторов
        data = data.dropna()

        # Выбираем признаки и целевую переменную
        features = data[
            ["RSI", "SMA", "volatility", "market_volume", "MACD", "MACD_signal", "BB_upper", "BB_middle",
             "BB_lower", "ATR"]].values
        targets = data["target"].values

        return features, targets

    except Exception as e:
        logging.error(f"Error preparing data: {e}")
        return None, None


def calculate_adx_and_trend(data, period=14, trend_threshold=25):
    """Calculates ADX and determines the trend.

    Args:
        data (pd.DataFrame): DataFrame with 'high', 'low', and 'close' columns.
        period (int): Period for ADX calculation.
        trend_threshold (int): Threshold for trend determination.

    Returns:
        pd.DataFrame or None: DataFrame with 'adx' and 'trend' columns, or None if an error occurs.
    """
    required_cols = ["high", "low", "close"]
    if not all(col in data.columns for col in required_cols):
        logging.error("Missing columns for ADX calculation: high, low, close")
        return None

    for col in required_cols:
        if not pd.api.types.is_numeric_dtype(data[col]):
            data[col] = pd.to_numeric(data[col], errors='coerce')

    data = data.dropna(subset=required_cols)  # Remove rows with NaN in required columns

    try:
        data["adx"] = talib.ADX(data["high"], data["low"], data["close"], timeperiod=period)
        data["trend"] = data["adx"].apply(lambda x: "Тренд" if x > trend_threshold else "Флет")
        return data
    except Exception as e:
        logging.error(f"Error calculating ADX and trend: {e}")
        return None


# Загрузка тикеров


def load_tickers(exchange):
    tickers = [market["symbol"] for market in exchange.fetch_markets()]
    logging.info("Tickers loaded.")
    return tickers  # Лучше возвращать значение, чем использовать глобальную переменную


# Проверка доступности токена


def is_token_available(symbol, tickers):  # Изменено
    return symbol in tickers
