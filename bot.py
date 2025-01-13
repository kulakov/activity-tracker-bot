def setup_google_sheets():
    """Настройка подключения к Google Sheets."""
    try:
        logger.info("Начинаем подключение к Google Sheets")
        
        # Получаем credentials из переменной окружения
        google_creds_str = os.getenv('GOOGLE_CREDENTIALS')
        if not google_creds_str:
            logger.error("Переменная GOOGLE_CREDENTIALS не найдена")
            return None
            
        # Создаем временный файл с credentials
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
            
            # Удаляем временный файл
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
                await asyncio.sleep(1)  # Увеличенная задержка между запросами
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