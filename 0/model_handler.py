import logging
import numpy as np
import pandas as pd
import pickle  # Добавлен импорт pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from data_handler import fetch_data, prepare_data
import logging
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from data_handler import fetch_data, prepare_data  # explicit import


def save_model(model, scaler, model_file):  # Добавлен model_file
    try:
        with open(model_file, "wb") as file:  # Используем model_file
            pickle.dump((model, scaler), file)
        logging.info(f"Model and scaler saved to {model_file} successfully.")
    except Exception as e:
        logging.error(f"Error saving model and scaler to {model_file}: {e}")
        raise  # Генерируем исключение


# Обучение модели
def train_model(tickers, exchange, model_file):  # Добавили exchange и model_file
    all_features, all_targets = [], []

    for symbol in tickers:
        data = fetch_data(exchange, symbol)  # Передаем exchange
        if data is not None and not data.empty:
            features, targets = prepare_data(data)
            if features.size > 0 and targets.size > 0:
                all_features.append(features)
                all_targets.append(targets)

    if all_features and all_targets:
        # Объединение всех фич и целей
        all_features = np.vstack(all_features)
        all_targets = np.hstack(all_targets)

        # Масштабирование данных
        scaler = StandardScaler()
        all_features = scaler.fit_transform(all_features)

        # Разделение данных на обучающую и тестовую выборки
        X_train, X_test, y_train, y_test = train_test_split(
            all_features, all_targets, test_size=0.2, random_state=42
        )

        # Обучение модели
        model = RandomForestClassifier()
        model.fit(X_train, y_train)

        logging.info("Model trained successfully.")

        # Сохранение модели и скейлера
        save_model(model, scaler, model_file)  # Передаем model_file

        return model, scaler
    else:
        logging.error("No data to train the model.")
        return None, None


def load_model(model_file, tickers, exchange):  # Добавлен exchange
    try:
        if os.path.exists(model_file):  # Используем model_file
            with open(model_file, "rb") as file:
                model, scaler = pickle.load(file)
            logging.info(f"Model and scaler loaded from {model_file} successfully.")
            return model, scaler
        else:
            logging.info(f"Model file {model_file} not found. Training a new model.")
            return train_model(tickers, exchange, model_file)  # Передаем exchange и model_file

    except Exception as e:
        logging.error(f"Error loading model from {model_file}: {e}")
        raise  # Генерируем исключение


# Бэктестинг


def backtest_strategy(symbol, model, scaler, start_date=None, end_date=None):
    try:
        data = fetch_data(symbol, start_date=start_date, end_date=end_date)
        if data is None:
            raise ValueError(f"No data found for {symbol}")

        features, targets = prepare_data(data)
        if len(features) == 0:
            raise ValueError(f"No features prepared for {symbol}")

        features_scaled = scaler.transform(features)
        predictions = model.predict(features_scaled)

        accuracy = accuracy_score(targets, predictions)
        precision = precision_score(targets, predictions)
        recall = recall_score(targets, predictions)
        f1 = f1_score(targets, predictions)

        logging.info(f"Backtesting results for {symbol}:")
        logging.info(f"  Accuracy: {accuracy:.2f}")
        logging.info(f"  Precision: {precision:.2f}")
        logging.info(f"  Recall: {recall:.2f}")
        logging.info(f"  F1-score: {f1:.2f}")

        return accuracy, precision, recall, f1

    except ValueError as e:
        logging.error(f"Backtesting error for {symbol}: {e}")
        return None, None, None, None  # Возвращает None, если есть ошибка


    except Exception as e:
        logging.exception(f"Unexpected error during backtesting for {symbol}: {e}")
        return None, None, None, None
