from threading import Thread
from bot import app, main_bot

# Start the Telegram bot thread when gunicorn loads this module
bot_thread = Thread(target=main_bot)
bot_thread.daemon = True
bot_thread.start()
