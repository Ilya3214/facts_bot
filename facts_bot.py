import telebot
import openai
import schedule
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
import random
import logging

# Настройка логирования
logging.basicConfig(filename='bot.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Конфигурация бота и API
bot_token = 'telegram_bot_token_here'
openai_api_key = 'openai_api_key_here'
bot = telebot.TeleBot(bot_token)
openai.api_key = openai_api_key

# Структуры данных для управления состоянием
user_requests = defaultdict(lambda: {'count': 0, 'time': datetime.now()})
start_requests = defaultdict(lambda: datetime.now() - timedelta(days=1))
ask_requests = defaultdict(lambda: datetime.now() - timedelta(days=1))
user_topics = defaultdict(list)
user_last_fact_time = defaultdict(lambda: datetime.now() - timedelta(days=1))
user_editing_topics = defaultdict(lambda: False)

# Вспомогательные функции
def log(message):
    logging.info(message)

def is_command_available(last_used):
    return datetime.now().date() > last_used.date()

def get_fact_with_topic(chat_id, topic):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "вы - полезный помощник."},
                {"role": "user", "content": f"Расскажите мне интересный факт о: {topic}"}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        log(f"Error in get_fact_with_topic: {e}")
        return "Произошла ошибка при получении факта."

def send_random_fact(chat_id):
    topics = user_topics[chat_id]
    if topics:
        random_topic = random.choice(topics)
        fact = get_fact_with_topic(chat_id, random_topic)
        bot.send_message(chat_id, fact)
        user_last_fact_time[chat_id] = datetime.now()
    else:
        bot.send_message(chat_id, "Вы не указали темы для интересных фактов. Используйте /factsedit, чтобы добавить темы.")

# Обработчики команд
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if is_command_available(start_requests[chat_id]):
        start_requests[chat_id] = datetime.now()
        welcome_text = "Привет! Я, Sheldon, который расскажет тебе интересные факты. Напиши /fact чтобы получить факт."
        bot.reply_to(message, welcome_text)
        send_random_fact(chat_id)
        update_schedule_for_user(chat_id)  # Обновляем расписание для пользователя
    else:
        bot.send_message(chat_id, "Вы уже использовали команду /start сегодня. Пожалуйста, попробуйте снова завтра.")

@bot.message_handler(commands=['fact'])
def send_fact_command(message):
    chat_id = message.chat.id
    if user_requests[chat_id]['count'] < 2 or datetime.now() - user_requests[chat_id]['time'] > timedelta(minutes=120):
        if datetime.now() - user_requests[chat_id]['time'] > timedelta(minutes=120):
            user_requests[chat_id]['count'] = 0
        user_requests[chat_id]['count'] += 1
        user_requests[chat_id]['time'] = datetime.now()
        send_random_fact(chat_id)
    else:
        bot.send_message(chat_id, "Вы уже много узнали сегодня...")

@bot.message_handler(commands=['ask'])
def ask_command(message):
    chat_id = message.chat.id
    if is_command_available(ask_requests[chat_id]):
        ask_requests[chat_id] = datetime.now()
        sent = bot.send_message(chat_id, "Задайте свой вопрос:")
        bot.register_next_step_handler(sent, handle_question)
    else:
        bot.send_message(chat_id, "Вы уже использовали команду /ask сегодня. Пожалуйста, попробуйте снова завтра.")

def handle_question(message):
    response = get_fact_with_topic(message.chat.id, message.text)
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['factsedit'])
def edit_topics(message):
    chat_id = message.chat.id
    if not user_editing_topics[chat_id]:
        user_editing_topics[chat_id] = True
        sent = bot.send_message(chat_id, "Введите темы, которые вас интересуют (через запятую):")
        bot.register_next_step_handler(sent, save_topics, chat_id)
    else:
        bot.send_message(chat_id, "Вы уже в процессе редактирования тем. Введите новые темы или используйте /cancel для выхода.")

def save_topics(message, chat_id):
    topics = [topic.strip() for topic in message.text.split(',')]
    user_topics[chat_id] = topics
    user_editing_topics[chat_id] = False
    update_schedule_for_user(chat_id)  # Обновляем расписание для этого пользователя
    bot.send_message(chat_id, f"Темы фактов обновлены: {', '.join(topics)}")

@bot.message_handler(commands=['factslist'])
def list_topics(message):
    chat_id = message.chat.id
    topics = user_topics[chat_id]
    if topics:
        topic_list = ", ".join(topics)
        bot.send_message(chat_id, f"Ваши темы интересных фактов: {topic_list}")
    else:
        bot.send_message(chat_id, "Вы пока не добавили темы для интересных фактов. Используйте /factsedit, чтобы добавить темы.")

@bot.message_handler(commands=['help'])
def display_help(message):
    chat_id = message.chat.id
    help_text = "Доступные команды:\n"
    help_text += "/start - Начать использование бота\n"
    help_text += "/fact - Получить интересный факт\n"
    help_text += "/ask - Задать вопрос и получить ответ\n"
    help_text += "/factsedit - Редактировать темы интересных фактов\n"
    help_text += "/factslist - Просмотреть ваши темы интересных фактов\n"
    help_text += "/help - Показать список доступных команд\n"
    bot.send_message(chat_id, help_text)

# Расписание отправки сообщений
def send_scheduled_message(chat_id):
    if chat_id in user_topics and user_topics[chat_id]:
        random_topic = random.choice(user_topics[chat_id])
        fact = get_fact_with_topic(chat_id, random_topic)
        bot.send_message(chat_id, fact)
        user_last_fact_time[chat_id] = datetime.now()
        schedule.every(60).minutes.do(send_scheduled_message, chat_id).tag(str(chat_id))

def update_schedule_for_user(chat_id):
    schedule.clear(str(chat_id))
    schedule.every(120).minutes.do(send_scheduled_message, chat_id).tag(str(chat_id))

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск расписания в отдельном потоке
threading.Thread(target=run_schedule, daemon=True).start()

# Запуск бота
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        log(f"An error occurred in the bot loop: {e}")
        time.sleep(15)
