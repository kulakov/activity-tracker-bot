from config import BOT_TOKEN, SPREADSHEET_ID
import os
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

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
ACTIVITY, ENERGY_STATUS = range(2)

def setup_google_sheets():
    """Настройка подключения к Google Sheets."""
    try:
        credentials = Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога."""
    keyboard = [['Закончить']]
    await update.message.reply_text(
        "Привет! Расскажи, что ты делал сегодня. Пиши по одному сообщению на каждую активность.\nКогда закончишь, нажми 'Закончить'.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['activities'] = []
    return ACTIVITY

async def record_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение активности."""
    text = update.message.text

    if text.lower() == 'закончить':
        if not context.user_data.get('activities'):
            await update.message.reply_text("Ты не указал ни одной активности. Расскажи, что делал сегодня?")
            return ACTIVITY

        sheet = setup_google_sheets()
        if not sheet:
            await update.message.reply_text("Ошибка подключения к таблице Google Sheets.")
            return ConversationHandler.END

        moscow_tz = pytz.timezone('Europe/Moscow')
        date = datetime.now(moscow_tz).strftime('%Y-%m-%d')

        for activity in context.user_data['activities']:
            try:
                sheet.append_row([date, activity['text'], activity['energy']])
            except Exception as e:
                logger.error(f"Ошибка записи данных: {e}")
                await update.message.reply_text("Ошибка записи данных в Google Sheets.")
                return ConversationHandler.END

        await update.message.reply_text("Спасибо! Все данные сохранены.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data['activities'].append({'text': text, 'energy': None})
    keyboard = [['Даёт энергию', 'Забирает энергию']]
    await update.message.reply_text("Эта активность даёт или забирает энергию?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ENERGY_STATUS

async def record_energy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение статуса энергии."""
    energy_status = update.message.text
    if not context.user_data.get('activities'):
        return ConversationHandler.END

    context.user_data['activities'][-1]['energy'] = energy_status
    keyboard = [['Закончить']]
    await update.message.reply_text("Записал! Что еще ты делал?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ACTIVITY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    await update.message.reply_text("Диалог отменён. Данные не сохранены.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_activity)],
            ENERGY_STATUS: [MessageHandler(filters.Regex('^(Даёт энергию|Забирает энергию)$'), record_energy)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(conv_handler)

    # Настройка вебхука
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv('PORT', '8443')),  # Порт задаётся Render автоматически
        url_path=BOT_TOKEN,
        webhook_url=f"https://activity-tracker-bot.onrender.com/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()