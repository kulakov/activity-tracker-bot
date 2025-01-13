from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Состояния диалога
ACTIVITY, ENERGY_STATUS, SET_TIME = range(3)

async def record_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение активности."""
    text = update.message.text

    if text.lower() == 'закончить':
        if not context.user_data.get('activities'):
            await update.message.reply_text("Ты не указал ни одной активности. Расскажи, что делал сегодня?")
            return ACTIVITY

        # Сохранение в Google Sheets
        sheet = setup_google_sheets()
        if not sheet:
            await update.message.reply_text("Ошибка подключения к таблице Google Sheets.")
            return ConversationHandler.END

        cet_tz = pytz.timezone('Europe/Paris')
        date = datetime.now(cet_tz).strftime('%Y-%m-%d')

        try:
            for activity in context.user_data['activities']:
                sheet.append_row([date, activity['text'], activity['energy']])
                await asyncio.sleep(1)  # Увеличиваем задержку между запросами
        except Exception as e:
            logger.error(f"Ошибка записи данных: {e}")
            await update.message.reply_text("Ошибка записи данных в Google Sheets.")
            return ConversationHandler.END

        # После сохранения спрашиваем про время уведомлений
        await update.message.reply_text(
            "Спасибо! Все данные сохранены. Теперь давай настроим время для ежедневных напоминаний.",
            reply_markup=ReplyKeyboardRemove()
        )
        return SET_TIME

    # Сохраняем активность и спрашиваем про энергию
    if 'activities' not in context.user_data:
        context.user_data['activities'] = []
    
    context.user_data['activities'].append({'text': text, 'energy': None})
    keyboard = [['Даёт энергию', 'Забирает энергию']]
    await update.message.reply_text(
        "Эта активность даёт или забирает энергию?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ENERGY_STATUS

def main():
    """Запуск бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
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

    application.add_handler(conv_handler)
    
    # Добавляем отдельные команды
    application.add_handler(CommandHandler('set_time', set_time))
    application.add_handler(CommandHandler('change_time', change_time))

    application.run_polling()