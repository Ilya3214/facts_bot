import telebot
import random
import json
import os
import logging
import openai

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токенов из переменных окружения
TOKEN = os.getenv('TELEBOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Имя файла с темами и фактами
TOPICS_FILE = 'topics.json'

# Функция для инициализации или загрузки данных из JSON файла
def initialize_data():
    if not os.path.exists(TOPICS_FILE) or os.stat(TOPICS_FILE).st_size == 0:
        with open(TOPICS_FILE, 'w', encoding='utf-8') as file:
            json.dump({}, file, ensure_ascii=False)
    
    try:
        with open(TOPICS_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error reading {TOPICS_FILE}: {e}")
        return {}

# Инициализация данных
topics_data = initialize_data()

# Инициализация словаря user_topics
user_topics = topics_data

# Функция для получения случайного факта по теме
def get_random_fact(user_id):
    user_id_str = str(user_id)
    if user_id_str in user_topics:
        facts_list = user_topics[user_id_str]
        if facts_list:
            # Выбор случайного факта из списка фактов пользователя
            return random.choice(facts_list)
        else:
            return "У вас нет фактов. Пожалуйста, добавьте факты с помощью команды /addtopic."
    else:
        return "У вас нет фактов. Используйте /addtopic для добавления фактов."


@bot.message_handler(commands=['fact'])
def send_random_fact(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    # user_name = message.from_user.first_name

    random_fact = get_random_fact(user_id)

    # Проверка, был ли получен факт
    if not random_fact:
        bot.send_message(chat_id, "Не удалось получить случайный факт.")
        return

    # Взаимодействие с ChatGPT
    openai.api_key = OPENAI_API_KEY
    prompt = f"Расскажи интересный факт о: '{random_fact}'"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    # Отправка ответа в Telegram
    if response.choices:
        bot.send_message(chat_id, f"{response.choices[0].message['content']}")
        # bot.send_message(chat_id, f"Вот интересный факт:\n{random_fact}" {response.choices[0].message['content']}")
    else:
        bot.send_message(chat_id, "Что-то пошло не так. Попробуйте ещё раз.")


# Обработчик команды /factsedit
@bot.message_handler(commands=['factsedit'])
def edit_facts(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Проверка, существует ли информация о темах пользователя в JSON файле
    if str(user_id) in user_topics:
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('/addtopic', '/deletetopic')
        bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "У вас нет тем для редактирования. Используйте /addtopic для создания новой темы.")

# Обработчик команды /addtopic
@bot.message_handler(commands=['addtopic'])
def add_topic(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    bot.send_message(chat_id, "Введите ваш новый факт:")
    bot.register_next_step_handler(message, save_new_fact, user_id)

# Обработчик для сохранения нового факта для пользователя
def save_new_fact(message, user_id):
    chat_id = message.chat.id
    new_facts_input = message.text.strip()

    # Разделение ввода пользователя на отдельные факты, используя запятую как разделитель
    new_facts = [fact.strip() for fact in new_facts_input.split(',')]

    user_id_str = str(user_id)
    # Проверка, существует ли информация о фактах пользователя в JSON файле
    if user_id_str not in user_topics:
        user_topics[user_id_str] = []

    # Добавление каждого нового факта в список фактов пользователя
    user_topics[user_id_str].extend(new_facts)

    # Сохранение обновленных данных в JSON файле
    with open(TOPICS_FILE, 'w', encoding='utf-8') as file:
        json.dump(user_topics, file, ensure_ascii=False, indent=4)

    bot.send_message(chat_id, f"Факт(ы) успешно добавлен(ы).")

# Обработчик команды /deletetopic
@bot.message_handler(commands=['deletetopic'])
def delete_topic(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Проверка, существует ли информация о фактах пользователя в JSON файле
    if str(user_id) in user_topics and user_topics[str(user_id)]:
        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for fact in user_topics[str(user_id)]:
            markup.add(fact)
        markup.add('Завершить удаление', 'Отменить редактирование')
        bot.send_message(chat_id, "Выберите факт для удаления:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "У вас нет фактов для удаления.")


@bot.message_handler(func=lambda message: message.text in user_topics.get(str(message.from_user.id), []))
def confirm_delete_topic(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    fact_to_delete = message.text

    # Удаление выбранного факта
    user_topics[str(user_id)].remove(fact_to_delete)

    # Сохранение обновленных данных в JSON файле
    with open(TOPICS_FILE, 'w', encoding='utf-8') as file:
        json.dump(user_topics, file, ensure_ascii=False, indent=4)

    bot.send_message(chat_id, f"Факт '{fact_to_delete}' успешно удален.")
    # Удаление клавиатуры после удаления
    bot.send_message(chat_id, "Факт удален.", reply_markup=telebot.types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda message: message.text in ['Завершить удаление', 'Отменить редактирование'])
def finish_or_cancel_deletion(message):
    chat_id = message.chat.id
    if message.text == 'Завершить удаление':
        bot.send_message(chat_id, "Удаление завершено.")
    else:
        bot.send_message(chat_id, "Редактирование отменено.")
    bot.send_message(chat_id, "Что вы хотите сделать дальше?", reply_markup=telebot.types.ReplyKeyboardRemove())


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = ("Доступные команды:\n"
                 "/fact - Получить случайный факт\n"
                 "/addtopic - Добавить новый факт\n"
                 "/deletetopic - Удалить факт\n"
                 "/factsedit - Редактировать факты\n"
                 "/help - Показать эту справку")
    bot.send_message(message.chat.id, help_text)

# ... (остальная часть кода) ...

# Запуск бота
bot.polling(none_stop=True)
