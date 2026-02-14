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

from strategic_engine import StrategicEngine
from strategic_prompts import (
    STARTER_PROMPTS, TASK_TYPES, format_starter_prompt, get_random_narrative
)

# Установка ключа OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога (оригинальные + стратегические)
(
    ACTIVITY, ENERGY_STATUS, SET_TIME, TRANSCRIPT_REVIEW,
    GOAL_SELECT, QUEST_SELECT, TASK_ACTION, FOCUS_MENU, FUN_GATE
) = range(9)

# Стратегический движок (singleton)
engine = StrategicEngine()


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


# ═══════════════════════════════════════════════════════════════
# Оригинальные обработчики (activity tracking)
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога — теперь с утренним брифингом."""
    # Показываем стратегический брифинг + стандартное приветствие
    briefing = engine.get_morning_briefing()

    keyboard = [
        ['🎯 Стратегия', '📝 Записать день'],
        ['🚀 Быстрый старт', '📊 Статус']
    ]
    await update.message.reply_text(
        f"{briefing}\n\n"
        "Что делаем?\n"
        "🎯 Стратегия — работа над целями\n"
        "📝 Записать день — трекинг активностей\n"
        "🚀 Быстрый старт — готовая задача за 30-60 мин\n"
        "📊 Статус — прогресс и уровень",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['activities'] = []
    return FOCUS_MENU

async def handle_focus_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка главного меню фокуса."""
    text = update.message.text

    if text == '📝 Записать день':
        keyboard = [['Закончить']]
        await update.message.reply_text(
            "Расскажи, что ты делал сегодня. Пиши по одному сообщению на каждую активность.\n"
            "Когда закончишь, нажми 'Закончить'.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ACTIVITY

    elif text == '🎯 Стратегия':
        return await show_goals(update, context)

    elif text == '🚀 Быстрый старт':
        return await show_quick_start(update, context)

    elif text == '📊 Статус':
        return await show_status(update, context)

    else:
        # Любой другой текст — записываем как активность
        keyboard = [['Закончить']]
        context.user_data['activities'] = []
        context.user_data['activities'].append({'text': text})
        await update.message.reply_text(
            "Как эта активность повлияла на твою энергию?\n"
            "Ответь: -2, -1, 0, 1, 2\n"
            "Или: даёт энергию / забирает энергию / нейтрально",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENERGY_STATUS

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
            # После записи активностей — предлагаем стратегическую задачу (task switching)
            suggestion = engine.get_switch_suggestion()
            await update.message.reply_text(
                f"Спасибо! Все данные сохранены.\n\n{suggestion}",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    # Записываем активность и спрашиваем энергию
    context.user_data['activities'].append({'text': text})
    await update.message.reply_text(
        "Как эта активность повлияла на твою энергию?\n"
        "Ответь: -2, -1, 0, 1, 2\n"
        "Или: даёт энергию / забирает энергию / нейтрально"
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
    """Ежедневное напоминание — теперь со стратегическим брифингом."""
    job = context.job
    briefing = engine.get_morning_briefing()
    await context.bot.send_message(
        job.chat_id,
        text=f"{briefing}\n\nИспользуй /start для начала работы."
    )

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение времени уведомлений."""
    try:
        user_time = datetime.strptime(update.message.text, '%H:%M').time()
        context.user_data['reminder_time'] = user_time

        logger.info(f"Устанавливаем напоминание на {user_time}")

        # Отменяем существующее напоминание, если оно есть
        if 'reminder_job' in context.user_data:
            logger.info("Удаляем существующее напоминание")
            context.user_data['reminder_job'].schedule_removal()

        # Устанавливаем новое напоминание
        chat_id = update.effective_chat.id
        cet_tz = pytz.timezone('Europe/Paris')
        now = datetime.now(cet_tz)

        # Вычисляем время до следующего напоминания
        reminder_time = cet_tz.localize(datetime.combine(now.date(), user_time))
        if reminder_time < now:
            reminder_time += timedelta(days=1)

        logger.info(f"Следующее напоминание запланировано на {reminder_time}")

        # Планируем ежедневное напоминание
        job = context.job_queue.run_daily(
            daily_reminder,
            time=user_time,
            chat_id=chat_id,
            name=str(chat_id)
        )
        context.user_data['reminder_job'] = job
        logger.info("Напоминание успешно запланировано")

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


# ═══════════════════════════════════════════════════════════════
# Стратегические обработчики
# ═══════════════════════════════════════════════════════════════

async def show_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список стратегических целей. /goals"""
    goals = engine.data.get_goals()

    lines = ["🎯 **Стратегические цели**\n"]
    keyboard_buttons = []
    for i, g in enumerate(goals, 1):
        active = sum(1 for q in g["quests"] if q["status"] == "active")
        lines.append(f"{i}. {g['icon']} {g['title']} ({g['xp']} XP, {active} квестов)")
        keyboard_buttons.append(f"{i}")

    lines.append("\nОтправь номер цели для декомпозиции на квесты")

    keyboard = [keyboard_buttons, ['◀️ Назад']]
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['goal_list'] = goals
    return GOAL_SELECT

async def handle_goal_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора цели."""
    text = update.message.text

    if text == '◀️ Назад':
        return await start(update, context)

    try:
        idx = int(text) - 1
        goals = context.user_data.get('goal_list', engine.data.get_goals())
        if 0 <= idx < len(goals):
            goal = goals[idx]
            context.user_data['current_goal_id'] = goal['id']

            # Показываем декомпозицию цели
            decomposition = engine.decompose_goal_to_quests(goal['id'])

            # Также показываем активные квесты
            active_quests = engine.data.get_active_quests(goal['id'])
            if active_quests:
                decomposition += "\n\n📋 **Активные квесты:**\n"
                for g, q in active_quests:
                    done = sum(1 for t in q["tasks"] if t["status"] == "done")
                    total = len(q["tasks"])
                    decomposition += f"• {q['title']} ({done}/{total}, {q['progress']}%)\n"

            keyboard = []
            # Количество предложенных квестов
            quest_count = len(engine.data.get_goal(goal['id']).get('quests', []))
            suggestions = engine.decompose_goal_to_quests(goal['id'])
            # Простой подсчёт по шаблонам
            template_count = suggestions.count('. **')
            buttons = [str(i) for i in range(1, template_count + 1)]
            if buttons:
                keyboard.append(buttons)
            keyboard.append(['◀️ К целям'])

            await update.message.reply_text(
                decomposition,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return QUEST_SELECT
        else:
            await update.message.reply_text("Неверный номер. Попробуй ещё.")
            return GOAL_SELECT
    except ValueError:
        await update.message.reply_text("Отправь номер цели (1, 2, 3...)")
        return GOAL_SELECT

async def handle_quest_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора квеста из шаблонов."""
    text = update.message.text

    if text == '◀️ К целям':
        return await show_goals(update, context)

    goal_id = context.user_data.get('current_goal_id')
    if not goal_id:
        return await show_goals(update, context)

    try:
        idx = int(text) - 1
        result = engine.add_predefined_quest(goal_id, idx)
        if result:
            await update.message.reply_text(
                result,
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Неверный номер квеста. Попробуй ещё.")
            return QUEST_SELECT
    except ValueError:
        await update.message.reply_text("Отправь номер квеста (1, 2, 3...)")
        return QUEST_SELECT

async def show_quick_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает стартовые промпты — быстрый вход в стратегическую задачу. /focus"""
    menu = engine.format_starter_menu()

    prompts = engine.get_starter_prompts()
    context.user_data['starter_prompts'] = prompts

    buttons = [str(i) for i in range(1, len(prompts) + 1)]
    keyboard = [buttons, ['🔄 Другие задачи', '◀️ Назад']]

    await update.message.reply_text(
        menu,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TASK_ACTION

async def handle_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора стартового промпта."""
    text = update.message.text

    if text == '◀️ Назад':
        return await start(update, context)

    if text == '🔄 Другие задачи':
        return await show_quick_start(update, context)

    prompts = context.user_data.get('starter_prompts', [])

    try:
        idx = int(text) - 1
        if 0 <= idx < len(prompts):
            prompt_data, goal = prompts[idx]
            detailed = format_starter_prompt(prompt_data, goal)

            # Создаём гештальт для этой задачи
            engine.create_gestalt(goal['id'], prompt_data['title'], 10)

            keyboard = [['✅ Сделано!', '⏭ Другую задачу'], ['◀️ Назад']]
            await update.message.reply_text(
                f"{detailed}\n\n"
                "Когда закончишь — нажми '✅ Сделано!' для получения XP",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            context.user_data['active_starter'] = {
                'prompt': prompt_data,
                'goal': goal
            }
            return TASK_ACTION
        else:
            await update.message.reply_text("Неверный номер. Попробуй ещё.")
            return TASK_ACTION
    except ValueError:
        pass

    # Обработка завершения задачи
    if text == '✅ Сделано!':
        starter = context.user_data.get('active_starter')
        if starter:
            goal = starter['goal']
            prompt_data = starter['prompt']
            xp = prompt_data.get('xp', 10)

            # Начисляем XP напрямую
            engine.data._add_player_xp(xp)
            engine.data._update_daily_counter("strategic")
            engine.data.update_streak()
            engine.data.save()

            # Формируем ответ
            player = engine.data.get_player()
            gate = engine.data.get_gate_status()

            response = (
                f"{get_random_narrative('task_complete', xp=xp)}\n\n"
                f"⚔️ {player['title']} (ур. {player['level']}) | XP: {player['total_xp']}\n"
                f"{gate}\n\n"
            )

            # Предлагаем следующую задачу
            suggestion = engine.data.suggest_next_strategic_task()
            if suggestion:
                response += f"📋 Следующая задача:\n{suggestion}"

            # Variable reward: случайный ракурс (30% шанс)
            import random
            if random.random() < 0.3:
                angle = engine.data.get_random_angle(goal['id'])
                response += f"\n\n💡 Мысль: {angle}"

            await update.message.reply_text(
                response,
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data.pop('active_starter', None)
            return ConversationHandler.END

    if text == '⏭ Другую задачу':
        return await show_quick_start(update, context)

    await update.message.reply_text("Отправь номер задачи или нажми кнопку.")
    return TASK_ACTION

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает статус игрока. /status"""
    status = engine.data.get_player_status_text()
    gate = engine.data.get_gate_status()

    gestalt = engine.get_gestalt_reminder()
    gestalt_text = f"\n\n{gestalt}" if gestalt else ""

    keyboard = [['◀️ Назад']]
    await update.message.reply_text(
        f"{status}\n\n{gate}{gestalt_text}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return FOCUS_MENU


# ═══════════════════════════════════════════════════════════════
# Standalone-команды (не требуют conversation state)
# ═══════════════════════════════════════════════════════════════

async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /goals — показать стратегические цели."""
    return await show_goals(update, context)

async def cmd_focus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /focus — быстрый старт стратегической задачи."""
    return await show_quick_start(update, context)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /status — статус вне диалога."""
    status = engine.data.get_player_status_text()
    gate = engine.data.get_gate_status()
    gestalt = engine.get_gestalt_reminder()
    gestalt_text = f"\n\n{gestalt}" if gestalt else ""
    await update.message.reply_text(f"{status}\n\n{gate}{gestalt_text}")

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /next — следующая стратегическая задача."""
    suggestion = engine.data.suggest_next_strategic_task()
    if suggestion:
        switch = engine.get_switch_suggestion()
        await update.message.reply_text(switch)
    else:
        await update.message.reply_text(
            "Нет активных стратегических задач.\n"
            "Используй /goals чтобы добавить квесты."
        )

async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /done [goal_id quest_id task_id] — завершить задачу."""
    args = context.args
    if len(args) >= 3:
        goal_id, quest_id, task_id = args[0], args[1], args[2]
        result = engine.complete_strategic_task(goal_id, quest_id, task_id)
        await update.message.reply_text(result)
    else:
        # Если нет аргументов — завершаем следующую задачу
        next_task = engine.data.get_next_task()
        if next_task:
            goal, quest, task = next_task
            result = engine.complete_strategic_task(goal['id'], quest['id'], task['id'])
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("Нет активных задач для завершения.")

async def cmd_fun(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /fun — проверить gate и записать fun-активность."""
    allowed, message = engine.check_fun_gate()
    if allowed:
        result = engine.record_fun_activity()
        await update.message.reply_text(f"{message}\n\n{result}")
    else:
        await update.message.reply_text(message)

async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /week — недельная сводка."""
    summary = engine.get_weekly_summary()
    await update.message.reply_text(summary)

async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /briefing — утренний брифинг."""
    briefing = engine.get_morning_briefing()
    await update.message.reply_text(briefing)

async def cmd_quest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /quest — быстрое добавление квеста.
    Формат: /quest goal_id Название квеста | задача 1 | задача 2 | задача 3
    """
    if not context.args:
        await update.message.reply_text(
            "Формат: /quest goal_id Название квеста | задача 1 | задача 2 | задача 3\n\n"
            "Goal IDs: jetstyle_growth, ai_products, consulting, creative\n\n"
            "Пример:\n"
            "/quest ai_products Подготовка к IT-Regatta | написать тезисы | подготовить демо | прогнать с коллегой"
        )
        return

    # Парсим аргументы
    full_text = ' '.join(context.args)
    parts = full_text.split('|')

    # Первая часть: goal_id + название квеста
    first_part = parts[0].strip().split(' ', 1)
    if len(first_part) < 2:
        await update.message.reply_text("Нужно указать goal_id и название квеста.")
        return

    goal_id = first_part[0]
    quest_title = first_part[1].strip()
    tasks = [p.strip() for p in parts[1:] if p.strip()]

    quest = engine.data.add_quest(goal_id, quest_title, "main", tasks if tasks else None)
    if quest:
        response = get_random_narrative('quest_start')
        response += f"\n\nКвест «{quest_title}» добавлен к цели {goal_id}!"
        if tasks:
            response += f"\nЗадач: {len(tasks)}  |  XP: +{quest['xp_reward']}"
            response += f"\nПервый шаг: {tasks[0]}"
            # Создаём гештальт
            engine.data.add_gestalt(goal_id, f"{quest_title}: {tasks[0]}", 0)
        await update.message.reply_text(response)
    else:
        await update.message.reply_text(
            f"Не удалось добавить квест. Проверь goal_id: {goal_id}\n"
            "Доступные: jetstyle_growth, ai_products, consulting, creative"
        )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help — список всех команд."""
    help_text = (
        "📖 **Команды бота**\n\n"
        "**Основные:**\n"
        "/start — главное меню с брифингом\n"
        "/analyze — анализ транскрипта через AI\n\n"
        "**Стратегия:**\n"
        "/goals — стратегические цели и квесты\n"
        "/focus — быстрый старт задачи (30-60 мин)\n"
        "/next — следующая стратегическая задача\n"
        "/done — завершить текущую задачу (+XP)\n"
        "/quest — добавить свой квест\n\n"
        "**Прогресс:**\n"
        "/status — уровень, XP, прогресс\n"
        "/briefing — утренний брифинг\n"
        "/week — сводка за неделю\n\n"
        "**Gate-механизм:**\n"
        "/fun — разблокировать fun-проект\n"
        "(нужно сначала 2 стратегических задачи)\n\n"
        "**Прочее:**\n"
        "/set_time — настроить время напоминания\n"
        "/cancel — отменить текущий диалог\n"
        "добавь тег/контекст/роль [название]"
    )
    await update.message.reply_text(help_text)


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Основной обработчик диалога (расширенный стратегическими состояниями)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('set_time', set_time),
            CommandHandler('analyze', process_transcript),
            CommandHandler('goals', cmd_goals),
            CommandHandler('focus', cmd_focus),
        ],
        states={
            FOCUS_MENU: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_focus_menu
                )
            ],
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
            GOAL_SELECT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_goal_select
                )
            ],
            QUEST_SELECT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_quest_select
                )
            ],
            TASK_ACTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_task_action
                )
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)

    # Standalone-команды (работают вне conversation)
    application.add_handler(CommandHandler('status', cmd_status))
    application.add_handler(CommandHandler('next', cmd_next))
    application.add_handler(CommandHandler('done', cmd_done))
    application.add_handler(CommandHandler('fun', cmd_fun))
    application.add_handler(CommandHandler('week', cmd_week))
    application.add_handler(CommandHandler('briefing', cmd_briefing))
    application.add_handler(CommandHandler('quest', cmd_quest))
    application.add_handler(CommandHandler('help', cmd_help))

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
