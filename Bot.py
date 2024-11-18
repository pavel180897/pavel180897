from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import NetworkError, TelegramError, TimedOut, RetryAfter
import re
from datetime import datetime
import logging
import asyncio
import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import wraps
import time

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = '7642974557:AAFQCBKKQFf6rTwz4aAe0v9l5cmccZyIvSo'
# ID администратора
ADMIN_ID = '385474644'
# ID консультанта
CONSULTANT_ID = '385474644'

# Настройки повторных попыток
MAX_RETRIES = 3
RETRY_DELAY = 2
CONVERSATION_TIMEOUT = 300  # 5 минут

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

# Функция для сохранения состояния
def save_state(user_id, state_data):
    try:
        os.makedirs('states', exist_ok=True)
        with open(f'states/{user_id}.json', 'w') as f:
            json.dump(state_data, f)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

# Функция для загрузки состояния
def load_state(user_id):
    try:
        with open(f'states/{user_id}.json', 'r') as f:
            return json.load(f)
    except:
        return None

# Декоратор для повторных попыток
def retry_on_error(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (NetworkError, TimedOut) as e:
                    if i == max_retries - 1:
                        logger.error(f"Failed after {max_retries} retries: {e}")
                        raise
                    logger.warning(f"Retry {i + 1}/{max_retries} after error: {e}")
                    await asyncio.sleep(delay * (i + 1))
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    raise
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Функция мониторинга здоровья
async def health_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Проверяем подключение к Telegram
        await context.bot.get_me()
        logger.info("Health check passed")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        # Уведомляем администратора
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❗️ Проблема с ботом: {e}"
            )
        except:
            pass

# Запуск HTTP сервера для render.com
def run_dummy_server():
    try:
        port = int(os.environ.get("PORT", 5000))
        server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
        logger.info(f"Starting HTTP server on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Error starting HTTP server: {e}")

# Запускаем сервер в отдельном потоке
threading.Thread(target=run_dummy_server, daemon=True).start()

@retry_on_error()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Загружаем сохраненное состояние
    user_id = str(update.effective_user.id)
    saved_state = load_state(user_id)
    if saved_state:
        context.user_data.update(saved_state)
    
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

@retry_on_error()
async def consultation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Администратор получил ваше сообщение и скоро свяжется с вами.")
    await context.bot.send_message(
        chat_id=CONSULTANT_ID,
        text=f"Новый запрос на консультацию от @{update.message.from_user.username}"
    )
    return ConversationHandler.END

@retry_on_error()
async def register_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип регистрации:",
        reply_markup=get_registration_type_keyboard()
    )
    return CHOOSING_REGISTRATION_TYPE

@retry_on_error()
async def registration_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['is_distributor'] = text == "Дистрибьютор"
    await update.message.reply_text(
        "Введите ваше ФИО:",
        reply_markup=get_back_keyboard()
    )
    return FULLNAME

# Добавим функцию проверки отмены регистрации
@retry_on_error()
async def check_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Отменить регистрацию":
        await cancel(update, context)
        return True
    return False

@retry_on_error()
async def fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['fullname'] = update.message.text
    await update.message.reply_text(
        "Введите дату рождения (формат DD.MM.YYYY):",
        reply_markup=get_back_keyboard()
    )
    return BIRTHDATE

@retry_on_error()
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

@retry_on_error()
async def address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_cancel(update, context):
        return ConversationHandler.END
    context.user_data['address'] = update.message.text
    await update.message.reply_text(
        "Введите номер телефона:",
        reply_markup=get_back_keyboard()
    )
    return PHONE

@retry_on_error()
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

@retry_on_error()
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

@retry_on_error()
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

@retry_on_error()
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

@retry_on_error()
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

@retry_on_error()
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Регистрация отменена.",
        reply_markup=get_start_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def main():
    try:
        # Инициализация бота с правильными таймаутами
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .get_updates_read_timeout(30)
            .get_updates_write_timeout(30)
            .get_updates_connection_pool_size(100)
            .build()
        )

        # Добавляем проверку здоровья каждые 5 минут
        try:
            application.job_queue.run_repeating(health_check, interval=300)
        except Exception as e:
            logger.warning(f"Could not setup health check: {e}")

        # Добавление обработчиков с таймаутом
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', start),
                MessageHandler(filters.Regex('^Получить консультацию$'), consultation),
                MessageHandler(filters.Regex('^Зарегистрироваться$'), register_choice),
            ],
            states={
                CHOOSING_REGISTRATION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration_type_chosen)],
                FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname)],
                BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, birthdate)],
                ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email)],
                SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, source)],
                INN: [MessageHandler(filters.TEXT & ~filters.COMMAND, inn)],
            },
            fallbacks=[MessageHandler(filters.Regex('^Отменить регистрацию$'), cancel)],
            conversation_timeout=CONVERSATION_TIMEOUT
        )

        application.add_handler(conv_handler)

        try:
            # Запускаем бота
            await application.initialize()
            await application.start()
            logger.info("Bot started successfully")
            
            # Запускаем polling в бесконечном цикле
            while True:
                try:
                    await application.run_polling(
                        allowed_updates=Update.ALL_TYPES,
                        drop_pending_updates=True
                    )
                except NetworkError as e:
                    logger.error(f"Network error occurred: {e}")
                    await asyncio.sleep(1)
                except TimedOut as e:
                    logger.error(f"Timeout error occurred: {e}")
                    await asyncio.sleep(2)
                except RetryAfter as e:
                    logger.error(f"Rate limit error occurred: {e}")
                    await asyncio.sleep(e.retry_after)
                except TelegramError as e:
                    logger.error(f"Telegram error occurred: {e}")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Unexpected error occurred: {e}")
                    await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Fatal error occurred: {e}")
        finally:
            try:
                await application.stop()
            except Exception as e:
                logger.error(f"Error stopping application: {e}")

    except Exception as e:
        logger.error(f"Fatal error occurred: {e}")

def run_bot():
    """Запускает бота с правильной обработкой event loop"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")

if __name__ == '__main__':
    run_bot()
