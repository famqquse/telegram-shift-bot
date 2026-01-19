import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from flask import Flask
from threading import Thread
import os # Импортируем os

# --- НАСТРОЙКИ ---
# Вставьте сюда токен вашего бота (полученный от @BotFather)
BOT_TOKEN = "8522157971:AAEbql6voTI5zGA7zbOJxGZXkU_al51aXPo"
# Вставьте сюда ваш ID в Telegram, чтобы бот присылал вам уведомления.
# Чтобы узнать свой ID, можно написать боту @userinfobot
ADMIN_CHAT_ID = "866572746"
# -----------------

# Настройка логирования для отладки
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ВЕБ-ЧАСТЬ ДЛЯ RENDER.COM (ЧТОБЫ БОТ НЕ ЗАСЫПАЛ) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "I am alive!"

def run_flask():
    # Render предоставляет порт в переменной окружения PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
# --------------------------------------------------------


# --- ОСНОВНАЯ ЛОГИКА ВАШЕГО БОТА (ничего не изменилось) ---
shifts = {
    "08:00-09:30": None, "09:30-11:00": None, "11:00-12:30": None,
    "12:30-14:00": None, "14:00-15:30": None, "15:30-17:00": None,
    "17:00-18:30": None, "18:30-20:00": None, "20:00-21:30": None,
    "21:30-23:00": None, "23:00-08:00": None,
}

def create_shifts_keyboard():
    keyboard = []
    for shift_time, user_info in shifts.items():
        text = f"✅ {shift_time} (Свободна)"
        if user_info:
            text = f"❌ {shift_time} (Занята)"
        button = telegram.InlineKeyboardButton(text, callback_data=shift_time)
        keyboard.append([button])
    return telegram.InlineKeyboardMarkup(keyboard)

def start(update: telegram.Update, context: CallbackContext):
    user_name = update.effective_user.first_name
    update.message.reply_text(f"👋 Привет, {user_name}!\n\nЯ бот для бронирования смен. Чтобы посмотреть доступные смены, используй команду /shifts.")

def show_shifts(update: telegram.Update, context: CallbackContext):
    keyboard = create_shifts_keyboard()
    update.message.reply_text("🗓️ **Доступные смены на сегодня:**\n\nНажмите на свободную смену, чтобы занять ее.", reply_markup=keyboard, parse_mode='Markdown')

def take_shift_callback(update: telegram.Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    shift_time = query.data
    user = query.from_user
    if shifts.get(shift_time) is None:
        shifts[shift_time] = {'id': user.id, 'first_name': user.first_name, 'username': user.username or "не указан"}
        query.edit_message_text(f"✅ Отлично! Вы заняли смену: **{shift_time}**.\n\nСписок смен обновлен.", parse_mode='Markdown')
        context.bot.edit_message_reply_markup(chat_id=query.message.chat_id, message_id=query.message.message_id, reply_markup=create_shifts_keyboard())
        admin_message = f"🔔 **Новая бронь!**\n\n👤 **Пользователь:** {user.first_name} (@{user.username})\n⏰ **Смена:** {shift_time}"
        try:
            context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу: {e}")
    else:
        query.answer("😔 Эта смена уже занята. Пожалуйста, выберите другую.", show_alert=True)

def reset_shifts_job(context: CallbackContext):
    global shifts
    for shift_time in shifts:
        shifts[shift_time] = None
    logger.info("Все смены были сброшены.")

def main_bot():
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("shifts", show_shifts))
    dispatcher.add_handler(CallbackQueryHandler(take_shift_callback))
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduler.add_job(reset_shifts_job, 'cron', hour=7, minute=55, second=0, args=[updater.job_queue.context])
    scheduler.start()
    updater.start_polling()
    logger.info("Бот запущен...")
    updater.idle()
# -------------------------------------------------------------

if __name__ == '__main__':
    # Запускаем веб-сервер в основном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # Запускаем бота в фоновом потоке
    main_bot()

