from config import BOT_TOKEN, SPREADSHEET_ID
import os
import logging
from datetime import datetime, timedelta, time
import pytz
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    Defaults  # Добавляем Defaults к существующим импортам
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
ACTIVITY, ENERGY_STATUS, SET_TIME = range(3)

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
                await asyncio.sleep(0.1)  # Задержка между запросами
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

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Установка времени уведомлений."""
    await update.message.reply_text(
        "Во сколько тебе удобно получать напоминание? Напиши время в формате ЧЧ:ММ (например, 09:00)."
    )
    return SET_TIME

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение времени уведомлений."""
    try:
        user_time = datetime.strptime(update.message.text, '%H:%M').time()
        context.user_data['reminder_time'] = user_time
        await update.message.reply_text(f"Время напоминания установлено на {user_time.strftime('%H:%M')}.")
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуй снова.")
        return SET_TIME

    return ConversationHandler.END

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ежедневное напоминание."""
    job = context.job
    await context.bot.send_message(job.chat_id, text="Привет! Расскажи, что ты делал сегодня. Нажми /start для начала.")

async def change_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Изменение времени напоминаний."""
    await update.message.reply_text("Давай поменяем время. Напиши новое время в формате ЧЧ:ММ.")
    return SET_TIME

def main():
    """Запуск бота."""
    defaults = Defaults(block=False)
    application = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

    # Команды
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('set_time', set_time))
    application.add_handler(CommandHandler('change_time', change_time))

    # Хендлеры
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_activity)],
            ENERGY_STATUS: [MessageHandler(filters.Regex('^(Даёт энергию|Забирает энергию)$'), record_energy)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()
    

    # Ежедневный джоб
    async def schedule_jobs(context: ContextTypes.DEFAULT_TYPE):
        job_queue = application.job_queue
        user_time = context.user_data.get('reminder_time', time(9, 0))  # По умолчанию 09:00
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)
        reminder_time = datetime.combine(now.date(), user_time, tzinfo=moscow_tz)
        if reminder_time <= now:
            reminder_time += timedelta(days=1)

        job_queue.run_daily(
            callback=daily_reminder,
            time=reminder_time.time(),
            chat_id=context.chat_data['chat_id']
        )

    # Команды
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('set_time', set_time))
    application.add_handler(CommandHandler('change_time', change_time))

    # Хендлеры
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_activity)],
            ENERGY_STATUS: [MessageHandler(filters.Regex('^(Даёт энергию|Забирает энергию)$'), record_energy)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()