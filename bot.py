import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from flask import Flask
from threading import Thread
import os
import datetime

# --- НАСТРОЙКИ (ОЧЕНЬ ВАЖНО!) ---
# УБЕДИТЕСЬ, ЧТО ВЫ ВСТАВИЛИ СЮДА СВОЙ АКТУАЛЬНЫЙ ТОКЕН
BOT_TOKEN = "8522157971:AAFDGk7ca05Ji4rOb83mRbbmlsvdpou3rwM"
ADMIN_CHAT_ID = "866572746"
# ---------------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ВЕБ-ЧАСТЬ ДЛЯ FLY.IO ---
app = Flask(__name__)
@app.route('/')
def index():
    return "I am alive!"

# --- СТРУКТУРА ДАННЫХ ДЛЯ СМЕН ---
base_shift_times = [
    "08:00-09:30", "09:30-11:00", "11:00-12:30", "12:30-14:00",
    "14:00-15:30", "15:30-17:00", "17:00-18:30", "18:30-20:00",
    "20:00-21:30", "21:30-23:00", "23:00-08:00"
]

shifts = []
slot_id_counter = 0
for _ in range(2):
    for time_slot in base_shift_times:
        shifts.append({
            "slot_id": slot_id_counter,
            "time": time_slot,
            "user_info": None
        })
        slot_id_counter += 1

# --- ОСНОВНАЯ ЛОГИКА БОТА ---

def create_shifts_keyboard():
    keyboard = []
    sorted_shifts = sorted(shifts, key=lambda x: (x['time'].split('-')[0], x['slot_id']))
    for slot in sorted_shifts:
        text = f"✅ {slot['time']} (Свободна)"
        if slot['user_info']:
            text = f"❌ {slot['time']} (Занята: {slot['user_info']['first_name']})"
        button = telegram.InlineKeyboardButton(text, callback_data=str(slot['slot_id']))
        keyboard.append([button])
    return telegram.InlineKeyboardMarkup(keyboard)

def start(update: telegram.Update, context: CallbackContext):
    user_name = update.effective_user.first_name
    update.message.reply_text(f"👋 Привет, {user_name}!\n\nЯ бот для бронирования смен. Чтобы посмотреть доступные смены, используй команду /shifts.\n\nАдминистратор может получить отчет по команде /grafik.")

def show_shifts(update: telegram.Update, context: CallbackContext):
    # ИЗМЕНЕНИЕ: Получаем дату в нужном формате
    today_date_str = datetime.datetime.now().strftime("%d.%m.%Y")
    keyboard = create_shifts_keyboard()
    update.message.reply_text(f"🗓️ **Доступные смены на {today_date_str}:**\n\nНажмите на свободную смену, чтобы занять ее.", reply_markup=keyboard, parse_mode='Markdown')

def take_shift_callback(update: telegram.Update, context: CallbackContext):
    query = update.callback_query
    target_slot_id = int(query.data)
    
    target_slot = next((slot for slot in shifts if slot["slot_id"] == target_slot_id), None)
    
    if not target_slot:
        query.answer("Произошла ошибка, слот не найден. Попробуйте обновить список: /shifts", show_alert=True)
        return

    user = query.from_user
    if target_slot['user_info'] is None:
        target_slot['user_info'] = {'id': user.id, 'first_name': user.first_name, 'username': user.username or "не указан"}
        
        query.answer(f"Отлично! Вы заняли смену: {target_slot['time']}.")
        
        admin_message = f"🔔 **Новая бронь!**\n\n👤 **Пользователь:** {user.first_name} (@{user.username})\n⏰ **Смена:** {target_slot['time']}"
        try:
            context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу: {e}")

        # ИЗМЕНЕНИЕ: Обновляем клавиатуру с датой
        today_date_str = datetime.datetime.now().strftime("%d.%m.%Y")
        context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=f"🗓️ **Доступные смены на {today_date_str}:**\n\nСписок обновлен.",
            reply_markup=create_shifts_keyboard(),
            parse_mode='Markdown'
        )
    else:
        query.answer("😔 Эта смена уже занята. Пожалуйста, выберите другую.", show_alert=True)

def reset_shifts_job():
    for slot in shifts:
        slot['user_info'] = None
    logger.info("Все смены были сброшены на новый день.")

def send_grafik(update: telegram.Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_CHAT_ID:
        update.message.reply_text("Эта команда доступна только администратору.")
        return

    # ИЗМЕНЕНИЕ: Получаем дату для отчета
    today_date_str = datetime.datetime.now().strftime("%d.%m.%Y")
    
    booked_shifts = [slot for slot in shifts if slot['user_info']]
    
    if not booked_shifts:
        report_message = f"📋 **Отчет на {today_date_str}**\n\nНа сегодня смен еще не забронировано."
    else:
        report_message = f"📋 **Отчет на {today_date_str}**\n\nЗабронированные смены:\n"
        sorted_booked = sorted(booked_shifts, key=lambda x: (x['time'].split('-')[0], x['slot_id']))
        for slot in sorted_booked:
            user_info = slot['user_info']
            report_message += f"\n• **{slot['time']}**: {user_info['first_name']} (@{user_info['username']})"
            
    try:
        context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=report_message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Не удалось отправить отчет админу: {e}")

def main_bot():
    try:
        updater = Updater(BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("shifts", show_shifts))
        dispatcher.add_handler(CommandHandler("grafik", send_grafik))
        dispatcher.add_handler(CallbackQueryHandler(take_shift_callback))
        scheduler = BackgroundScheduler(timezone="Europe/Moscow")
        scheduler.add_job(reset_shifts_job, 'cron', hour=7, minute=55, second=0)
        scheduler.start()
        updater.start_polling()
        logger.info("Бот запущен...")
    except Exception as e:
        logger.critical(f"Критическая ошибка в потоке бота: {e}", exc_info=True)

if __name__ == "__main__":
    bot_thread = Thread(target=main_bot)
    bot_thread.daemon = True
    bot_thread.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
