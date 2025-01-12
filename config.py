from dotenv import load_dotenv
import os

# Загружаем переменные окружения из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Для отладки: убедитесь, что переменные загружены корректно
print("BOT_TOKEN:", BOT_TOKEN)
print("SPREADSHEET_ID:", SPREADSHEET_ID)