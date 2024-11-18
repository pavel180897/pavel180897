import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

def run_dummy_server():
    port = int(os.environ.get("PORT", 5000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Запускаем сервер в отдельном потоке
threading.Thread(target=run_dummy_server, daemon=True).start()

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import re
from datetime import datetime

# Токен бота
BOT_TOKEN = '7642974557:AAFQCBKKQFf6rTwz4aAe0v9l5cmccZyIvSo'
# ID администратора
ADMIN_ID = '385474644'
# ID консультанта
CONSULTANT_ID = '385474644'

# Состояния разговора
(
    CHOOSING_REGISTRATION_TYPE,
    FULLNAME,
    BIRTHDATE,
    ADDRESS,
    PHONE,
    EMAIL,
    SOURCE,
    INN,
) = range(8)

# Клавиатуры
def get_start_keyboard():
    keyboard = [
        [KeyboardButton("Получить консультацию")],
        [KeyboardButton("Зарегистрироваться")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_registration_type_keyboard():
    keyboard = [
        [KeyboardButton("Покупатель")],
        [KeyboardButton("Дистрибьютор")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_keyboard():
    keyboard = [
        [KeyboardButton("Отменить регистрацию")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"👋 Добро пожаловать, {update.message.from_user.first_name}!\n\n"
        "🛍 С нами вы можете зарегистрироваться в Клубном Интернет Магазине Атоми "
        "и покупать товары на сайте со скидкой до 15%\n\n"
        "✅ Бесплатная и простая регистрация\n"
        "✅ Бесплатный доступ в личный кабинет\n"
        "✅ Акции каждую неделю\n"
        "✅ Нет обязательных ежемесячных закупок\n"
        "✅ Не надо покупать стартовый набор\n\n"
        "Сплошные плюсы!"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_start_keyboard())
    return ConversationHandler.END

async def consultation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Администратор получил ваше сообщение и скоро свяжется с вами.")
    await context.bot.send_message(
        chat_id=CONSULTANT_ID,
        text=f"Новый запрос на консультацию от @{update.message.from_user.username}"
    )
    return ConversationHandler.END

async def register_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип регистрации:",
        reply_markup=get_registration_type_keyboard()
    )
    return CHOOSING_REGISTRATION_TYPE

async def registration_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['is_distributor'] = text == "Дистрибьютор"
    await update.message.reply_text(
        "Введите ваше ФИО:",
        reply_markup=get_back_keyboard()
    )
    return FULLNAME

# Добавим функцию проверки отмены регистрации
async def check_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Отменить регистрацию":
        await cancel(update, context)
        return True
    return False

async def fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['fullname'] = update.message.text
    await update.message.reply_text(
        "Введите дату рождения (формат DD.MM.YYYY):",
        reply_markup=get_back_keyboard()
    )
    return BIRTHDATE

async def birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    try:
        datetime.strptime(update.message.text, '%d.%m.%Y')
        context.user_data['birthdate'] = update.message.text
        await update.message.reply_text(
            "Введите ваш адрес:",
            reply_markup=get_back_keyboard()
        )
        return ADDRESS
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Пожалуйста, используйте формат DD.MM.YYYY",
            reply_markup=get_back_keyboard()
        )
        return BIRTHDATE
      

async def address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['address'] = update.message.text
    await update.message.reply_text(
        "Введите номер телефона:",
        reply_markup=get_back_keyboard()
    )
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    if not update.message.text.isdigit():
        await update.message.reply_text(
            "Пожалуйста, введите только цифры",
            reply_markup=get_back_keyboard()
        )
        return PHONE
    context.user_data['phone'] = update.message.text
    await update.message.reply_text(
        "Введите ваш email:",
        reply_markup=get_back_keyboard()
    )
    return EMAIL

async def email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    if not re.match(r"[^@]+@[^@]+\.[^@]+", update.message.text):
        await update.message.reply_text(
            "Неверный формат email. Попробуйте еще раз",
            reply_markup=get_back_keyboard()
        )
        return EMAIL
    context.user_data['email'] = update.message.text
    await update.message.reply_text(
        "Откуда вы о нас узнали?",
        reply_markup=get_back_keyboard()
    )
    return SOURCE

async def source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['source'] = update.message.text
    if context.user_data.get('is_distributor', False):
        await update.message.reply_text(
            "Введите ваш ИНН:",
            reply_markup=get_back_keyboard()
        )
        return INN
    else:
        return await finish_registration(update, context)

async def inn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    if not update.message.text.isdigit():
        await update.message.reply_text(
            "ИНН должен содержать только цифры",
            reply_markup=get_back_keyboard()
        )
        return INN
    context.user_data['inn'] = update.message.text
    return await finish_registration(update, context)

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.message.from_user
    
    admin_message = (
        f"📝 НОВАЯ РЕГИСТРАЦИЯ!\n\n"
        f"👤 Telegram: @{user.username if user.username else 'Нет username'}\n"
        f"📋 Тип: {'Дистрибьютор' if user_data['is_distributor'] else 'Покупатель'}\n"
        f"ℹ️ Данные пользователя:\n"
        f"👤 ФИО: {user_data['fullname']}\n"
        f"📅 Дата рождения: {user_data['birthdate']}\n"
        f"📍 Адрес: {user_data['address']}\n"
        f"📱 Телефон: {user_data['phone']}\n"
        f"📧 Email: {user_data['email']}\n"
        f"💡 Источник: {user_data['source']}"
    )
    
    if user_data.get('is_distributor', False):
        admin_message += f"\n🔢 ИНН: {user_data['inn']}"
    
    # Добавляем время регистрации
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    admin_message += f"\n\n⏰ Время регистрации: {current_time}"
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message,
        parse_mode='HTML'
    )
    
    await update.message.reply_text(
        "Спасибо! Ожидайте регистрации, с вами в ближайшее время свяжется администратор",
        reply_markup=get_start_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Регистрация отменена.",
        reply_markup=get_start_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END
  

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    
    application.add_handler(MessageHandler(
        filters.Regex(pattern=r'^Получить консультацию$'),
        consultation
    ))
    
    registration_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(pattern=r'^Зарегистрироваться$'), register_choice)],
        states={
            CHOOSING_REGISTRATION_TYPE: [
                MessageHandler(filters.Regex(pattern=r'^(Покупатель|Дистрибьютор)$'), registration_type_chosen)
            ],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname)],
            BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, birthdate)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, source)],
            INN: [MessageHandler(filters.TEXT & ~filters.COMMAND, inn)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex(pattern=r'^Отменить регистрацию$'), cancel)
        ],
    )
    
    application.add_handler(registration_handler)
    
    # Добавляем обработчик для любых других сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    
    print("Бот запущен...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
