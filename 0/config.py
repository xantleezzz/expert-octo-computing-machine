import os

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

CSV_FILE = "signal_log.csv"
MODEL_FILE = "model.pkl"

# Проверка на наличие всех ключей.  Вы можете добавить более сложную проверку
if not all([API_KEY, API_SECRET, TELEGRAM_TOKEN, CHAT_ID]):
    raise ValueError("Не все ключи API установлены.")
