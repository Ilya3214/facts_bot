import telebot
import threading
import time
from datetime import datetime, timedelta
from random import choice

TOKEN = '6758207571:AAHJWyIwAOfM4LnG0uIRaJ8fM9C4cCFMHl8'
bot = telebot.TeleBot(TOKEN)

# Threshold for inactivity (24 hours)
USER_INACTIVITY_THRESHOLD = 18000  # 24 hours in seconds

# Dictionary to track individual user activity
user_activity = {}

# List of random questions
questions = [
    "Как ты там, бля, держишься?",
    "Чё как, старина, всё заебок?",
    "Ну что, заебался уже или как?",
    "Как обстоят дела, братишка, всё по пизде или норм?",
    "Чё новенького? Есть чё пошлячить?",
    "Как на работе, не доебывают?",
    "Чё по чём, братан, какие планы на выходные?",
    "На что последнее время мудакуешь, есть чё интересное?",
    "Нахуярил чё-нибудь клёвое недавно?",
    "Как там твои любовные еботни, всё гладко?"
]

def check_daily_inactivity():
    while True:
        current_time = datetime.now()
        for user_id, (chat_id, last_time) in list(user_activity.items()):
            if current_time - last_time > timedelta(seconds=USER_INACTIVITY_THRESHOLD):
                question = choice(questions)
                bot.send_message(chat_id, f"@{user_id}, {question}")
                # Update the last time a question was asked
                user_activity[user_id] = (chat_id, current_time)
        time.sleep(60)  # Check every hour

inactivity_thread = threading.Thread(target=check_daily_inactivity)
inactivity_thread.start()

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.username
    chat_id = message.chat.id
    user_activity[user_id] = (chat_id, datetime.now())

if __name__ == '__main__':
    bot.polling(none_stop=True)
