import logging
import asyncio
import mysql.connector
from telethon import TelegramClient, events
import aiohttp
import json
from datetime import datetime
import hashlib
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('UserBot')

# Конфигурация (заменить на свои значения)
DB_CONFIG = {
    'host': 'your-mysql-host',
    'port': 3306,
    'user': 'your-username',
    'password': 'your-password',
    'database': 'your-database'
}

API_ID = 'your-api-id'  # INT ЗНАЧЕНИЕ Получить на my.telegram.org
API_HASH = 'your-api-hash'  # Получить на my.telegram.org
PHONE_NUMBER = 'your-phone-number'  # Формат: +79123456789

BOT_SERVER_URL = 'http://your-server:port/api/messages'
API_KEY = 'your-secret-api-key'

# Глобальные переменные
client = None
processed_messages = set()

# Загрузка конфигурации из базы данных
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
            
            return {
                'monitored_users': monitored_users,
                'keywords': keywords
            }
        else:
            return {'monitored_users': [], 'keywords': []}
            
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return {'monitored_users': [], 'keywords': []}

# Создание уникального хэша сообщения
def create_message_hash(message, sender_id):
    content = message.text or ''
    return hashlib.md5(f"{sender_id}_{content}".encode()).hexdigest()

# Отправка сообщения на сервер бота
async def send_to_bot_server(message_data):
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            }
            
            async with session.post(BOT_SERVER_URL, json=message_data, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"Сообщение отправлено на сервер бота: {message_data['message_hash']}")
                    return True
                else:
                    logger.error(f"Ошибка отправки на сервер: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Ошибка подключения к серверу: {e}")
        return False

# Проверка точного совпадения ключевых слов
def check_exact_keyword_match(text, keywords):
    # Приводим текст к нижнему регистру и разбиваем на слова
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Проверяем каждое ключевое слово
    for keyword in keywords:
        keyword_lower = keyword.lower()
        # Проверяем точное совпадение
        if keyword_lower in words:
            return True
            
        # Дополнительная проверка для ключевых слов, которые могут быть частью составных слов
        if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text.lower()):
            return True
            
    return False

# Обработчик всех сообщений
@events.register(events.NewMessage)
async def message_handler(event):
    try:
        message = event.message
        if not message.text:  # Пропускаем медиа-сообщения
            return
        
        sender = await message.get_sender()
        if not sender:
            return
        
        sender_id = sender.id
        sender_username = getattr(sender, 'username', None)
        
        # Создаем уникальный хэш сообщения
        message_hash = create_message_hash(message, sender_id)
        
        # Проверяем, не обрабатывали ли уже это сообщение
        if message_hash in processed_messages:
            return
        
        config = load_config()
        should_process = False
        
        # Проверка пользователя
        if sender_username and sender_username.lower() in [u.lower() for u in config['monitored_users']]:
            should_process = True
        
        # Проверка ключевых слов (только точные совпадения)
        if not should_process and config['keywords']:
            should_process = check_exact_keyword_match(message.text, config['keywords'])
        
        if should_process:
            # Добавляем в обработанные
            processed_messages.add(message_hash)
            
            # Получаем информацию о чате
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat.id)
            
            # Формируем данные для отправки
            message_data = {
                'message_hash': message_hash,
                'sender_id': sender_id,
                'sender_username': sender_username,
                'sender_first_name': getattr(sender, 'first_name', ''),
                'sender_last_name': getattr(sender, 'last_name', ''),
                'message_text': message.text,
                'chat_id': message.chat_id,
                'chat_title': chat_title,
                'message_date': message.date.isoformat(),
                'message_id': message.id
            }
            
            # Отправляем на сервер бота
            await send_to_bot_server(message_data)
    
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")

# Очистка старых хэшей
async def cleanup_old_hashes():
    while True:
        await asyncio.sleep(3600)  # Каждый час
        processed_messages.clear()
        logger.info("Кэш хэшей сообщений очищен")

# Основная функция
async def main():
    global client
    
    client = TelegramClient('userbot_session', API_ID, API_HASH)
    client.add_event_handler(message_handler)
    
    await client.start()
    logger.info("User Bot запущен и слушает сообщения...")
    
    asyncio.create_task(cleanup_old_hashes())
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())