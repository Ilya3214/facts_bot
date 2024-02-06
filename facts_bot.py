import telebot
import openai
import schedule
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
import random
import logging
import traceback
from openai.error import OpenAIError, RateLimitError, InvalidRequestError
import json
# Настройка логирования
logging.basicConfig(filename='bot.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def log_exception(e):
    logging.error(f"Exception: {type(e).__name__}, {e}, Traceback: {traceback.format_exc()}")

def load_user_data():
    try:
        with open('user_data.json', 'r') as file:
            data = file.read()
            # Возвращаем пустой словарь, если файл пуст
            loaded_data = json.loads(data) if data else {}
            print("Loaded user_data from JSON:", loaded_data)
            return loaded_data
    except FileNotFoundError:
        return {}  # Возвращает пустой словарь, если файл не найден


# Конфигурация бота и API
bot_token = '6758207571:AAHJWyIwAOfM4LnG0uIRaJ8fM9C4cCFMHl8'
openai_api_key = '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'
bot = telebot.TeleBot(bot_token)
openai.api_key = openai_api_key

# Структуры данных для управления состоянием
user_requests = defaultdict(lambda: {'count': 0, 'time': datetime.now()})
start_requests = defaultdict(lambda: datetime.now() - timedelta(days=1))
ask_requests = defaultdict(lambda: datetime.now() - timedelta(days=1))
user_topics = defaultdict(list)
user_last_fact_time = defaultdict(lambda: datetime.now() - timedelta(days=1))
user_editing_topics = defaultdict(lambda: False)
user_data = load_user_data()

# Вспомогательные функции
def log(message):
    logging.info(message)

def is_command_available(last_used):
    return datetime.now().date() > last_used.date()

def get_fact_with_topic(chat_id, user_id, topic):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "вы - полезный помощник."},
                {"role": "user", "content": f"Расскажите мне интересный факт о: {topic}"}
            ]
        )
        return response['choices'][0]['message']['content']
    except RateLimitError as e:
        log_exception(e)
        return "Извините, превышен лимит запросов. Пожалуйста, попробуйте позже."
    except InvalidRequestError as e:
        log_exception(e)
        return "Некорректный запрос. Пожалуйста, проверьте введенные данные."
    except OpenAIError as e:
        log_exception(e)
        return "Проблема со связью с OpenAI. Пожалуйста, попробуйте позже."
    except Exception as e:
        log_exception(e)
        return "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."

def send_random_fact(user_id, chat_id):
    user_id_str = str(user_id)
    topics = user_data.get(user_id_str, [])  # Получаем текущие темы пользователя

    logging.debug(f"send_random_fact called for user {user_id} in chat {chat_id}")

    if topics:
        random_topic = random.choice(topics)
        fact = get_fact_with_topic(chat_id, user_id, random_topic)

        # Отправляем факт пользователю
        bot.send_message(chat_id, fact)

        # Обновляем user_data с выбранной темой пользователя
        if random_topic not in topics:
            topics.append(random_topic)
            user_data[user_id_str] = topics
            save_user_data(user_data)
    else:
        bot.send_message(chat_id, "Вы не указали темы для интересных фактов. Используйте /factsedit, чтобы добавить темы.")

# Обработчики команд
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    if is_command_available(start_requests[user_id]):
        start_requests[user_id] = datetime.now()
        welcome_text = "Привет! Я, Sheldon, который расскажет тебе интересные факты. Напиши /fact чтобы получить факт."
        bot.reply_to(message, welcome_text)
        send_random_fact(user_id)
        update_schedule_for_user(user_id)  # Обновляем расписание для пользователя
    else:
        bot.send_message(user_id, "Вы уже использовали команду /start сегодня. Пожалуйста, попробуйте снова завтра.")

@bot.message_handler(commands=['fact'])
def send_fact_command(message):
    logging.debug(f"Command /fact called by user {message.from_user.id} in chat {message.chat.id}")
    user_id = message.from_user.id
    chat_id = message.chat.id
    if user_requests[user_id]['count'] < 10 or datetime.now() - user_requests[user_id]['time'] > timedelta(minutes=120):
        if datetime.now() - user_requests[user_id]['time'] > timedelta(minutes=120):
            user_requests[user_id]['count'] = 0
        user_requests[user_id]['count'] += 1
        user_requests[user_id]['time'] = datetime.now()
        send_random_fact(user_id, chat_id)  # Передача user_id и chat_id
    else:
        bot.send_message(chat_id, "Вы уже много узнали сегодня...")

@bot.message_handler(commands=['ask'])
def ask_command(message):
    user_id = message.chat.id
    if is_command_available(ask_requests[user_id]):
        ask_requests[user_id] = datetime.now()
        sent = bot.send_message(user_id, "Задайте свой вопрос:")
        bot.register_next_step_handler(sent, handle_question)
    else:
        bot.send_message(user_id, "Вы уже использовали команду /ask сегодня. Пожалуйста, попробуйте снова завтра.")

def handle_question(message):
    response = get_fact_with_topic(message.chat.id, message.text)
    bot.send_message(message.chat.id, response)

def process_topics_edit(message, user_id):
    if message.text == "/cancel":
        cancel_editing(message)
    else:
        save_topics(message, user_id)

@bot.message_handler(commands=['factsedit'])
def edit_topics(message):
    user_id = message.from_user.id  # Используем user_id для работы с темами
    chat_id = message.chat.id  # chat_id используется для отправки сообщений

    if not user_editing_topics[user_id]:
        user_editing_topics[user_id] = True
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="Добавить темы", callback_data="add_topics"))
        markup.add(telebot.types.InlineKeyboardButton(text="Удалить темы", callback_data="delete_topics"))
        bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "Вы уже в процессе редактирования тем.")

@bot.callback_query_handler(func=lambda call: call.data == "add_topics")
def handle_add_topics(call):
    user_id = call.from_user.id  # Используем from_user.id для идентификации пользователя
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Введите новые темы, которые вас интересуют (через запятую):")
    bot.register_next_step_handler_by_chat_id(chat_id, process_topics_edit, user_id)

def process_topics_edit(message, user_id):
    if message.text == "/cancel":
        cancel_editing(message)
    else:
        save_topics(message, user_id)

def show_current_topics(chat_id, user_id):
    chat_id_str = str(chat_id)
    user_id_str = str(user_id)

    # Извлекаем темы пользователя из структуры данных
    user_topics = user_data.get(chat_id_str, {}).get(user_id_str, [])
    markup = telebot.types.InlineKeyboardMarkup()

    if user_topics:
        for topic in user_topics:
            markup.add(telebot.types.InlineKeyboardButton(text=f"Удалить '{topic}'", callback_data=f"delete:{topic}"))
        bot.send_message(chat_id_str, "Ваши темы:", reply_markup=markup)
    else:
        bot.send_message(chat_id_str, "Ваш список тем пуст.")

    # Добавляем кнопку для завершения удаления
    markup.add(telebot.types.InlineKeyboardButton(text="Завершить удаление", callback_data="finish_deleting"))
    bot.send_message(user_id, "Выберите тему для удаления или завершите удаление:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "finish_deleting")
def finish_deleting(call):
    user_id = call.message.chat.id
    user_editing_topics[user_id] = False  # Сбрасываем флаг редактирования
    bot.send_message(user_id, "Удаление тем завершено.")


@bot.callback_query_handler(func=lambda call: call.data == "delete_topics")
def handle_delete_topics(call):
    user_id = call.message.chat.id
    show_current_topics(user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete:"))
def handle_delete_topic(call):
    user_id = call.message.chat.id
    topic_to_delete = call.data.split(':')[1]
    logging.debug(f"Saving topics for user {user_id}: {user_data[str(user_id)]}")

    if topic_to_delete in user_data.get(str(user_id), []):
        user_data[str(user_id)].remove(topic_to_delete)
        save_user_data(user_data)  # Сохранение обновленных данных в JSON
        bot.answer_callback_query(call.id, f"Тема '{topic_to_delete}' удалена.")
        show_current_topics(user_id)
    else:
        bot.answer_callback_query(call.id, "Эта тема уже была удалена.", show_alert=True)

def save_topics(message, user_id):
    chat_id_str = str(message.chat.id)
    user_id_str = str(user_id)

    # Разделение введенного текста на отдельные темы и удаление лишних пробелов
    new_topics = [topic.strip() for topic in message.text.split(',')]

    # Проверка, существует ли уже запись для этого chat_id
    if chat_id_str not in user_data:
        user_data[chat_id_str] = {}

    # Проверка, существуют ли уже темы для этого user_id в данном chat_id
    if user_id_str in user_data[chat_id_str]:
        # Обновление существующих тем
        current_topics = user_data[chat_id_str][user_id_str]
        updated_topics = list(set(current_topics + new_topics))
    else:
        # Создание новой записи для user_id
        updated_topics = new_topics

    # Сохранение обновлённых тем
    user_data[chat_id_str][user_id_str] = updated_topics
    save_user_data(user_data)

    # Отправка подтверждающего сообщения
    bot.send_message(chat_id_str, f"Темы фактов для пользователя {user_id} обновлены: {', '.join(updated_topics)}")


@bot.message_handler(commands=['cancel'])
def cancel_editing(message):
    user_id = message.chat.id
    if user_editing_topics[user_id]:
        user_editing_topics[user_id] = False  # Убедитесь, что этот флаг сбрасывается
        bot.send_message(user_id, "Редактирование тем отменено.")
    else:
        bot.send_message(user_id, "Вы не находитесь в процессе редактирования.")

# @bot.message_handler(commands=['cancel'])
# def cancel_editing(message):
#     user_id = message.chat.id
#     if user_editing_topics[user_id]:
#         user_editing_topics[user_id] = False
#         bot.send_message(user_id, "Редактирование тем отменено.")
#     else:
#         bot.send_message(user_id, "Вы не находитесь в процессе редактирования.")


@bot.message_handler(commands=['factslist'])
def list_topics(message):
    user_id = message.chat.id
    topics = user_topics[user_id]
    if topics:
        topic_list = ", ".join(topics)
        bot.send_message(user_id, f"Ваши темы интересных фактов: {topic_list}")
    else:
        bot.send_message(user_id, "Вы пока не добавили темы для интересных фактов. Используйте /factsedit, чтобы добавить темы.")

@bot.message_handler(commands=['help'])
def display_help(message):
    user_id = message.chat.id
    help_text = "Доступные команды:\n"
    help_text += "/start - Начать использование бота\n"
    help_text += "/fact - Получить интересный факт\n"
    help_text += "/ask - Задать вопрос и получить ответ\n"
    help_text += "/factsedit - Редактировать темы интересных фактов\n"
    help_text += "/factslist - Просмотреть ваши темы интересных фактов\n"
    help_text += "/help - Показать список доступных команд\n"
    bot.send_message(user_id, help_text)

# Расписание отправки сообщений
def send_scheduled_message(user_id):
    if user_id in user_topics and user_topics[user_id]:
        random_topic = random.choice(user_topics[user_id])
        fact = get_fact_with_topic(user_id, random_topic)
        bot.send_message(user_id, fact)
        user_last_fact_time[user_id] = datetime.now()
        schedule.every(60).minutes.do(send_scheduled_message, user_id).tag(str(user_id))

def update_schedule_for_user(user_id):
    schedule.clear(str(user_id))
    schedule.every(120).minutes.do(send_scheduled_message, user_id).tag(str(user_id))

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