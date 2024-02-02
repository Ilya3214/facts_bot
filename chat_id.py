import telebot

bot_token = '6758207571:AAHJWyIwAOfM4LnG0uIRaJ8fM9C4cCFMHl8'
bot = telebot.TeleBot(bot_token)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print("Chat ID:", message.chat.id)
    bot.reply_to(message, "Your chat ID is: " + str(message.chat.id))

bot.polling()
