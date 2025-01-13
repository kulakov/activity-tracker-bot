from config import BOT_TOKEN, SPREADSHEET_ID
import os
import logging
from datetime import datetime, timedelta, time
import pytz
import asyncio
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
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
        logger.info("Начинаем подключение к Google Sheets")
        
        google_creds_str = os.getenv('GOOGLE_CREDENTIALS')
        if not google_creds_str:
            logger.error("Переменная GOOGLE_CREDENTIALS не найдена")
            return None
            
        try:
            temp_creds_path = '/tmp/temp_credentials.json'
            with open(temp_creds_path, 'w') as f:
                f.write(google_creds_str)
            logger.info("Временный файл credentials создан успешно")
            
            credentials = Credentials.from_service_account_file(
                temp_creds_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets',
                       'https://www.googleapis.com/auth/drive']
            )
            
            os.remove(temp_creds_path)
            logger.info("Временный файл credentials удален")
            
            client = gspread.authorize(credentials)
            logger.info("Авторизация с Google выполнена успешно")
            
            sheet = client.open_by_key(SPREADSHEET_ID).sheet1
            logger.info(f"Подключение к таблице {SPREADSHEET_ID} выполнено успешно")
            
            return sheet
            
        except Exception as e:
            logger.error(f"Ошибка при работе с credentials: {str(e)}")
            if os.path.exists(temp_creds_path):
                os.remove(temp_creds_path)
            return None
            
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {str(e)}")
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
            logger.error("Не удалось получить объект sheet")
            await update.message.reply_text("Ошибка подключения к таблице. Пожалуйста, попробуйте позже.")
            return ConversationHandler.END

        cet_tz = pytz.timezone('Europe/Paris')
        date = datetime.now(cet_tz).strftime('%Y-%m-%d')

        success = True
        try:
            for activity in context.user_data['activities']:
                logger.info(f"Попытка записи активности: {activity}")
                sheet.append_row([date, activity['text'], activity['energy']])
                logger.info(f"Активность успешно записана: {date}, {activity['text']}, {activity['energy']}")
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при записи данных: {str(e)}")
            success = False

        if success:
            await update.message.reply_text(
                "Спасибо! Все данные сохранены. Теперь давай настроим время для ежедневных напоминаний.",
                reply_markup=ReplyKeyboardRemove()
            )
            return SET_TIME
        else:
            await update.message.reply_text(
                "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    context.user_data['activities'].append({'text': text, 'energy': None})
    keyboard = [['Даёт энергию', 'Забирает энергию']]
    await update.message.reply_text(
        "Эта активность даёт или забирает энергию?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
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
        "Во сколько тебе удобно получать напоминание? Ответь в формате ЧЧ:ММ, используя два числа и двоеточие между ними.\n\n" +
        "Правильно: 09:00, 14:30, 21:45\n" +
        "Неправильно: 9:00, 2:30pm, 9.00",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_TIME

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение времени уведомлений."""
    try:
        user_time = datetime.strptime(update.message.text, '%H:%M').time()
        context.user_data['reminder_time'] = user_time
        
        # Отменяем существующее напоминание, если оно есть
        if 'reminder_job' in context.user_data:
            context.user_data['reminder_job'].schedule_removal()
        
        # Устанавливаем новое напоминание
        chat_id = update.effective_chat.id
        cet_tz = pytz.timezone('Europe/Paris')
        now = datetime.now(cet_tz)
        
        # Вычисляем время до следующего напоминания
        reminder_time = cet_tz.localize(datetime.combine(now.date(), user_time))
        if reminder_time < now:
            reminder_time += timedelta(days=1)
        
        # Планируем ежедневное напоминание
        job = context.job_queue.run_daily(
            daily_reminder,
            time=user_time,
            chat_id=chat_id,
            name=str(chat_id)
        )
        context.user_data['reminder_job'] = job
        
        await update.message.reply_text(
            f"Отлично! Буду напоминать тебе каждый день в {user_time.strftime('%H:%M')}."
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Неверный формат! Используй два числа и двоеточие, например: 09:00, 14:30, 21:45\n\n" +
            "Часы должны быть от 00 до 23\n" +
            "Минуты должны быть от 00 до 59"
        )
        return SET_TIME

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ежедневное напоминание."""
    job = context.job
    await context.bot.send_message(
        job.chat_id,
        text="Привет! Расскажи, что ты делал сегодня. Используй /start для начала записи."
    )

async def change_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Изменение времени напоминаний."""
    await update.message.reply_text(
        "Давай поменяем время. Ответь в формате ЧЧ:ММ, используя два числа и двоеточие между ними.\n\n" +
        "Правильно: 09:00, 14:30, 21:45\n" +
        "Неправильно: 9:00, 2:30pm, 9.00"
    )
    return SET_TIME

def main():
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Основной обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('set_time', set_time)
        ],
        states={
            ACTIVITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    record_activity
                )
            ],
            ENERGY_STATUS: [
                MessageHandler(
                    filters.Regex('^(Даёт энергию|Забирает энергию)$'),
                    record_energy
                )
            ],
            SET_TIME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    save_time
                )
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)
    
    # Отдельный обработчик для изменения времени
    application.add_handler(CommandHandler('change_time', change_time))
    
    application.run_polling()

if __name__ == '__main__':
    main()