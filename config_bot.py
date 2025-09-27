import logging
import mysql.connector
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread
import json
from datetime import datetime
import asyncio
import html

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('ConfigBot')

# Конфигурация (заменить на свои значения)
DB_CONFIG = {
    'host': 'your-mysql-host',
    'port': 3306,
    'user': 'your-username',
    'password': 'your-password',
    'database': 'your-database'
}

FLASK_HOST = '0.0.0.0'
FLASK_PORT = 25539
API_KEY = 'your-secret-api-key'

BOT_TOKEN = 'your-bot-token'  # Получить у @BotFather

app = Flask(__name__)
CORS(app, origins=["http://your-frontend-domain:port"])

application = None
bot_instance = None
main_loop = None
# Инициализация базы данных
def init_database():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Проверяем существование таблиц и создаем если нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                monitored_users TEXT,
                keywords TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_hash VARCHAR(64) NOT NULL UNIQUE,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Проверяем есть ли начальная конфигурация
        cursor.execute("SELECT COUNT(*) FROM bot_config")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO bot_config (monitored_users, keywords) VALUES ('[]', '[]')")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("База данных инициализирована")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")

# Загрузка конфигурации
def load_config():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT monitored_users, keywords FROM bot_config ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            monitored_users = json.loads(result['monitored_users']) if result['monitored_users'] else []
            keywords = json.loads(result['keywords']) if result['keywords'] else []
            return {'monitored_users': monitored_users, 'keywords': keywords}
        else:
            return {'monitored_users': [], 'keywords': []}
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return {'monitored_users': [], 'keywords': []}

# Сохранение конфигурации
def save_config(config):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Используем ensure_ascii=False для читаемых символов
        monitored_users_str = json.dumps(config['monitored_users'], ensure_ascii=False)
        keywords_str = json.dumps(config['keywords'], ensure_ascii=False)
        
        cursor.execute("UPDATE bot_config SET monitored_users = %s, keywords = %s", 
                      (monitored_users_str, keywords_str))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Конфигурация сохранена в базу данных")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {e}")
        return False

# Обработка CORS preflight запросов
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify()
        response.headers.add("Access-Control-Allow-Origin", "http://blue.fnode.me:25550")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

# Отправка сообщения подписчикам

async def send_to_subscribers(message_data):
    try:
        # Получаем всех пользователей из базы
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM subscribers")
        subscribers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Экранируем специальные символы HTML
        sender_username = html.escape(message_data.get('sender_username', 'Unknown'))
        message_text = html.escape(message_data.get('message_text', ''))
        chat_title = html.escape(message_data.get('chat_title', ''))
        
        # Формируем сообщение с HTML разметкой
        text = f"👤 <b>Пользователь:</b> @{sender_username}\n"
        text += f"💬 <b>Сообщение:</b> {message_text}\n"
        text += f"📱 <b>Чат:</b> {chat_title}\n"
        text += f"⏰ <b>Время:</b> {datetime.fromisoformat(message_data['message_date']).strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Убираем кнопку "Написать" полностью, чтобы избежать ошибки Button_user_invalid
        reply_markup = None
        
        # Отправляем всем подписчикам
        for (user_id,) in subscribers:
            try:
                await bot_instance.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode='HTML',
                    reply_markup=reply_markup  # Без кнопки
                )
                logger.info(f"Сообщение отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка отправки подписчикам: {e}")

# API endpoint для приёма сообщений от userbot
@app.route('/api/messages', methods=['POST', 'OPTIONS'])
def receive_message():
    try:
        # Обработка preflight запроса
        if request.method == "OPTIONS":
            response = jsonify()
            response.headers.add("Access-Control-Allow-Origin", "http://blue.fnode.me:25550")
            response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
            response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
            return response
        
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f'Bearer {API_KEY}':
            response = jsonify({'error': 'Unauthorized'})
            response.headers.add("Access-Control-Allow-Origin", "http://blue.fnode.me:25550")
            return response, 401
        
        data = request.get_json()
        logger.info(f"Получено сообщение: {data['message_hash']}")
        
        # Отправляем сообщение всем подписчикам
        if application and bot_instance and main_loop:
            # Запускаем асинхронную задачу правильно
            asyncio.run_coroutine_threadsafe(
                send_to_subscribers(data), 
                main_loop
            )
        
        response = jsonify({'status': 'success', 'message': 'Сообщение обработано'})
        response.headers.add("Access-Control-Allow-Origin", "http://blue.fnode.me:25550")
        return response, 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки API запроса: {e}")
        response = jsonify({'error': str(e)})
        response.headers.add("Access-Control-Allow-Origin", "http://blue.fnode.me:25550")
        return response, 500

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Добавляем пользователя в подписчики
    user_id = update.effective_user.id
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO subscribers (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Пользователь {user_id} добавлен в подписчики")
    except Exception as e:
        logger.error(f"Ошибка добавления подписчика: {e}")
    
    keyboard = [['Добавить пользователя', 'Удалить пользователя'],
                ['Добавить ключевое слово', 'Удалить ключевое слово'],
                ['Показать текущие настройки']]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        'Выберите действие:',
        reply_markup=reply_markup
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    item_type = data[1]
    item = '_'.join(data[2:])  # Объединяем обратно, так как item может содержать underscores
    
    config = load_config()
    
    if action == 'remove':
        if item_type == 'user':
            if item in config['monitored_users']:
                config['monitored_users'].remove(item)
                await query.edit_message_text(f'Пользователь @{item} удален из списка отслеживаемых.')
            else:
                await query.edit_message_text('Этот пользователь не найден в списке.')
        elif item_type == 'keyword':
            if item in config['keywords']:
                config['keywords'].remove(item)
                await query.edit_message_text(f'Ключевое слово "{item}" удалено.')
            else:
                await query.edit_message_text('Это ключевое слово не найдено в списке.')
        
        save_config(config)

    
# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    text = update.message.text
    
    if text == 'Добавить пользователя':
        await update.message.reply_text('Введите username пользователя для добавления (без @):')
        context.user_data['action'] = 'add_user'
    elif text == 'Удалить пользователя':
        if not config['monitored_users']:
            await update.message.reply_text('Список отслеживаемых пользователей пуст.')
            return
            
        keyboard = []
        for user in config['monitored_users']:
            keyboard.append([InlineKeyboardButton(f"@{user}", callback_data=f"remove_user_{user}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите пользователя для удаления:', reply_markup=reply_markup)
    elif text == 'Добавить ключевое слово':
        await update.message.reply_text('Введите ключевое слово для добавления:')
        context.user_data['action'] = 'add_keyword'
    elif text == 'Удалить ключевое слово':
        if not config['keywords']:
            await update.message.reply_text('Список ключевых слов пуст.')
            return
            
        keyboard = []
        for keyword in config['keywords']:
            keyboard.append([InlineKeyboardButton(keyword, callback_data=f"remove_keyword_{keyword}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите ключевое слово для удаления:', reply_markup=reply_markup)
    elif text == 'Показать текущие настройки':
        users = ', '.join(f"@{user}" for user in config['monitored_users']) if config['monitored_users'] else 'нет'
        keywords = ', '.join(config['keywords']) if config['keywords'] else 'нет'
        
        await update.message.reply_text(
            f"Отслеживаемые пользователи: {users}\nКлючевые слова: {keywords}"
        )
    elif 'action' in context.user_data:
        action = context.user_data['action']
        
        if action == 'add_user':
            if text not in config['monitored_users']:
                config['monitored_users'].append(text)
                if save_config(config):
                    await update.message.reply_text(f'Пользователь @{text} добавлен в список отслеживаемых.')
                else:
                    await update.message.reply_text('Ошибка сохранения конфигурации.')
            else:
                await update.message.reply_text('Этот пользователь уже в списке.')
                
        elif action == 'remove_user':
            if text in config['monitored_users']:
                config['monitored_users'].remove(text)
                if save_config(config):
                    await update.message.reply_text(f'Пользователь @{text} удален из списка отслеживаемых.')
                else:
                    await update.message.reply_text('Ошибка сохранения конфигурации.')
            else:
                await update.message.reply_text('Этот пользователь не найден в списке.')
                
        elif action == 'add_keyword':
            if text not in config['keywords']:
                config['keywords'].append(text)
                if save_config(config):
                    await update.message.reply_text(f'Ключевое слово "{text}" добавлено.')
                else:
                    await update.message.reply_text('Ошибка сохранения конфигурации.')
            else:
                await update.message.reply_text('Это ключевое слово уже в списке.')
                
        elif action == 'remove_keyword':
            if text in config['keywords']:
                config['keywords'].remove(text)
                if save_config(config):
                    await update.message.reply_text(f'Ключевое слово "{text}" удалено.')
                else:
                    await update.message.reply_text('Ошибка сохранения конфигурации.')
            else:
                await update.message.reply_text('Это ключевое слово не найдено в списке.')
        
        del context.user_data['action']

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")

# Запуск Flask сервера
def run_flask():
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)

# Запуск бота
def main():
    global application, bot_instance, main_loop
    
    # Инициализируем базу данных
    init_database()
    
    # Получаем текущий event loop
    main_loop = asyncio.get_event_loop()
    
    # Создаем приложение бота
    application = Application.builder().token(BOT_TOKEN).build()
    bot_instance = application
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_error_handler(error_handler)
    
    # Запускаем Flask сервер в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask сервер запущен на {FLASK_HOST}:{FLASK_PORT}")
    
    logger.info("Config Bot запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()