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
    filters
)
import gspread
from google.oauth2.service_account import Credentials
from prompts import Categories, SYSTEM_PROMPT, ANALYSIS_PROMPT
import json
import re
import openai
from typing import Dict, List

# Установка ключа OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
ACTIVITY, ENERGY_STATUS, SET_TIME, TRANSCRIPT_REVIEW = range(4)

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

async def analyze_with_chatgpt(text: str) -> str:
    """Отправка текста в ChatGPT и получение анализа"""
    try:
        # Загружаем категории
        categories = Categories()
        
        # Формируем промпт
        prompt = ANALYSIS_PROMPT.format(
            справочник_категорий=json.dumps(categories._data, ensure_ascii=False, indent=2),
            текст=text
        )
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при работе с ChatGPT: {e}")
        raise

def parse_chatgpt_response(response: str) -> List[Dict]:
    """Парсинг ответа от ChatGPT в структурированный формат"""
    activities = []
    
    # Разбиваем ответ на секции
    sections = response.split('\n\n')
    
    for section in sections:
        # Ищем строки с тегами
        if '[' in section and ']' in section:
            # Парсим теги и текст
            tags = re.findall(r'\[(.*?)\]', section)
            text = section.split('|')[-1].strip() if '|' in section else section
            
            activities.append({
                'text': text,
                'tags': tags,
                'raw_section': section  # сохраняем оригинальную секцию для отладки
            })
    
    return activities

async def process_transcript(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка транскрипта"""
    text = update.message.text
    
    if len(text) < 100:  # Минимальная длина для транскрипта
        return ACTIVITY
        
    await update.message.reply_text("Получил транскрипт. Анализирую...")
    
    try:
        # Отправляем в ChatGPT
        response = await analyze_with_chatgpt(text)
        
        # Парсим ответ
        activities = parse_chatgpt_response(response)
        
        # Сохраняем в контекст для последующей записи
        context.user_data['activities'] = activities
        
        # Показываем результат пользователю
        summary = "Вот что я понял из транскрипта:\n\n"
        for activity in activities:
            summary += f"- {activity['text']}\n"
            if activity.get('tags'):
                summary += f"  Теги: {', '.join(activity['tags'])}\n"
        
        keyboard = [['Всё верно', 'Нужны правки']]
        await update.message.reply_text(
            summary,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
        return TRANSCRIPT_REVIEW
        
    except Exception as e:
        logger.error(f"Ошибка при обработке транскрипта: {e}")
        await update.message.reply_text(
            "Извини, произошла ошибка при обработке транскрипта. Попробуй отправить его снова или опиши активности обычным способом."
        )
        return ACTIVITY

async def handle_transcript_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения анализа транскрипта"""
    answer = update.message.text
    
    if answer == 'Всё верно':
        # Записываем в таблицу
        sheet = setup_google_sheets()
        if not sheet:
            await update.message.reply_text("Ошибка подключения к таблице.")
            return ConversationHandler.END
            
        cet_tz = pytz.timezone('Europe/Paris')
        date = datetime.now(cet_tz).strftime('%Y-%m-%d')
        
        success = True
        try:
            for activity in context.user_data['activities']:
                sheet.append_row([
                    date,
                    activity['text'],
                    activity.get('energy', '0'),  # Нейтральная энергия по умолчанию
                    activity.get('roles', ''),    # Роли из ChatGPT
                    activity.get('skills', ''),   # Скилы из ChatGPT
                    activity.get('summary', '')   # Конспект из ChatGPT
                ])
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при записи данных: {e}")
            success = False
            
        if success:
            await update.message.reply_text(
                "Отлично! Все активности сохранены.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "Произошла ошибка при сохранении. Попробуйте позже.",
                reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
        
    else:  # Нужны правки
        await update.message.reply_text(
            "Хорошо, давай записывать активности по одной. Что ты делал?",
            reply_markup=ReplyKeyboardMarkup([['Закончить']], resize_keyboard=True)
        )
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
                sheet.append_row([
                    date, 
                    activity['text'], 
                    activity['energy'],
                    activity.get('roles', ''),  # Роли из ChatGPT
                    activity.get('skills', ''),  # Скилы из ChatGPT
                    activity.get('summary', '')  # Конспект из ChatGPT
                ])
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

async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление новой категории"""
    text = update.message.text.lower()
    
    # Определяем тип категории
    if text.startswith('добавь тег'):
        category_type = 'СКИЛЫ'
        value = text.replace('добавь тег', '').strip()
    elif text.startswith('добавь контекст'):
        category_type = 'КОНТЕКСТЫ'
        value = text.replace('добавь контекст', '').strip()
    elif text.startswith('добавь роль'):
        category_type = 'РОЛИ'
        value = text.replace('добавь роль', '').strip()
    else:
        await update.message.reply_text(
            "Используй команды:\n" +
            "добавь тег [название]\n" +
            "добавь контекст [название]\n" +
            "добавь роль [название]"
        )
        return
    
    # Добавляем категорию
    categories = Categories()
    if categories.add_category(category_type, value):
        await update.message.reply_text(f"Добавлено в {category_type}: {value}")
        
        # Если есть активная активность, добавляем тег к ней
        if context.user_data.get('current_activity'):
            if 'tags' not in context.user_data['current_activity']:
                context.user_data['current_activity']['tags'] = []
            context.user_data['current_activity']['tags'].append(value)
            await update.message.reply_text(f"Тег добавлен к текущей активности")
    else:
        await update.message.reply_text(f"Ошибка при добавлении {value} в {category_type}")

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Установка времени уведомлений."""
    await update.message.reply_text(
        "Во сколько тебе удобно получать напоминание? Ответь в формате ЧЧ:ММ, используя два числа и двоеточие между ними.\n\n" +
        "Правильно: 09:00, 14:30, 21:45\n" +
        "Неправильно: 9:00, 2:30pm, 9.00",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_TIME

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
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
            f"Отлично! Буду напоминать тебе каждый день в {user_time.strftime('%H:%M')}.",
            reply_markup=ReplyKeyboardRemove()
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

def main():
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Основной обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('set_time', set_time),
            CommandHandler('analyze', process_transcript)  # Добавляем команду для анализа
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
                    filters.Regex('^-2|-1|0|1|2|.*даёт.*|.*забирает.*|.*нейтрально.*$'),
                    record_energy
                )
            ],
            SET_TIME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    save_time
                )
            ],
            TRANSCRIPT_REVIEW: [
                MessageHandler(
                    filters.Regex('^(Всё верно|Нужны правки)$'),
                    handle_transcript_review
                )
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)
    
    # Добавляем обработчик категорий
    application.add_handler(MessageHandler(
        filters.Regex('^добавь (тег|контекст|роль)'), 
        add_category
    ))
    
    # Отдельный обработчик для изменения времени
    application.add_handler(CommandHandler('change_time', set_time))
    
    application.run_polling()

if __name__ == '__main__':
    main()