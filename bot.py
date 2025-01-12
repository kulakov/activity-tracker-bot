from config import BOT_TOKEN, SPREADSHEET_ID
import os
import json
import logging
from datetime import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import gspread
from google.oauth2.service_account import Credentials

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
ACTIVITY, ENERGY_STATUS = range(2)

# Теги для категоризации
TAGS = {
    "РОЛИ": {
        "Управленческие": ["Гендиректор", "Программный директор", "Артдиректор", "Менеджер", "Самоменеджер", "Продакт"],
        "Экспертные": ["Стратег", "Маркетолог", "Продакт", "Ресерчер", "Дизайнер", "Писатель", "Копирайтер"],
        "Образовательные": ["Учитель", "Тренер", "Трекер", "Ученик"],
        "Социальные": ["Друг", "Сын", "Муж", "Бадди", "Жилетка", "Нетворк", "Человек"]
    },
    "СКИЛЫ": {
        "⚪ Базовые": ["планировать", "анализ", "координация", "договариваться"],
        "🟣 Энергозатратные": ["решать проблемы", "чинить людей", "переговоры"],
        "🟡 Энергия": ["придумывать", "изобретать", "дружить", "учить"],
        "🟢 Целевые": ["любопытство", "режиссура", "проектировать", "английский"]
    }
}

def setup_google_sheets():
    """Настройка подключения к Google Sheets через переменные окружения."""
    credentials_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    client = gspread.authorize(credentials)
    return client.open_by_key(SPREADSHEET_ID).sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало разговора и запрос активности."""
    keyboard = [['Закончить']]
    await update.message.reply_text(
        'Привет! Расскажи, что ты сегодня делал? Опиши каждую активность отдельным сообщением.\n'
        'Когда закончишь, нажми "Закончить".',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['activities'] = []
    return ACTIVITY

def analyze_activity(text: str) -> dict:
    """Анализ активности и определение тегов."""
    found_tags = {
        "roles": [],
        "skills": [],
    }
    
    text_lower = text.lower()
    
    for category, subcategories in TAGS.items():
        for subcategory, tags in subcategories.items():
            for tag in tags:
                if tag.lower() in text_lower:
                    if category == "РОЛИ":
                        found_tags["roles"].append(tag)
                    elif category == "СКИЛЫ":
                        found_tags["skills"].append(tag)
    
    return found_tags

async def record_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запись активности и запрос про энергию."""
    text = update.message.text
    
    if text == 'Закончить':
        if not context.user_data.get('activities'):
            await update.message.reply_text(
                "Ты не указал ни одной активности. Расскажи, что делал сегодня?"
            )
            return ACTIVITY
            
        sheet = setup_google_sheets()
        moscow_tz = pytz.timezone('Europe/Moscow')
        date = datetime.now(moscow_tz).strftime('%Y-%m-%d')
        
        for activity_data in context.user_data['activities']:
            activity_text = activity_data['text']
            energy_status = activity_data['energy']
            tags = activity_data['tags']
            
            sheet.append_row([
                date,
                activity_text,
                energy_status,
                ', '.join(tags['roles']),
                ', '.join(tags['skills'])
            ])
        
        await update.message.reply_text(
            "Спасибо! Все активности сохранены.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    tags = analyze_activity(text)
    context.user_data['current_activity'] = {
        'text': text,
        'tags': tags
    }
    
    keyboard = [['Даёт энергию ➕', 'Забирает энергию ➖']]
    await update.message.reply_text(
        'Эта активность даёт или забирает энергию?',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ENERGY_STATUS

async def record_energy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запись статуса энергии и запрос следующей активности."""
    energy_status = update.message.text
    current_activity = context.user_data.get('current_activity')
    
    if not current_activity:
        return ConversationHandler.END
    
    current_activity['energy'] = energy_status
    context.user_data['activities'].append(current_activity)
    
    keyboard = [['Закончить']]
    await update.message.reply_text(
        'Записал! Что еще ты делал?',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ACTIVITY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена разговора."""
    await update.message.reply_text(
        'Отменено. Данные не сохранены.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ACTIVITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, record_activity)
            ],
            ENERGY_STATUS: [
                MessageHandler(
                    filters.Regex('^(Даёт энергию ➕|Забирает энергию ➖)$'),
                    record_energy
                )
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()