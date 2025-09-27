# Telegram Monitoring Bot System

Система из двух ботов для мониторинга Telegram сообщений:
- **UserBot** - отслеживает сообщения в Telegram на основе заданных критериев
- **ConfigBot** - принимает уведомления и предоставляет интерфейс для настройки

## Функциональность

### UserBot
- Мониторинг сообщений от заданных пользователей
- Фильтрация по ключевым словам (точное совпадение)
- Отправка уведомлений на сервер ConfigBot
- Автоматическая очистка кэша обработанных сообщений

### ConfigBot
- Web API для приема сообщений от UserBot
- Telegram бот с меню управления настройками
- Рассылка уведомлений подписчикам
- Управление списком отслеживаемых пользователей и ключевых слов

## Установка и настройка

### Предварительные требования
- Python 3.8+
- MySQL сервер
- Telegram API ключи (получить на [my.telegram.org](https://my.telegram.org))
- Bot Token (получить у [@BotFather](https://t.me/BotFather))

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/telegram-monitoring-bot.git
cd telegram-monitoring-bot
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка базы данных
Создайте базу данных MySQL и выполните инициализацию через ConfigBot (таблицы создаются автоматически).

### 4. Настройка конфигурации
**Для UserBot (userbot.py):**
```bash
DB_CONFIG = {
    'host': 'your-mysql-host',
    'port': 3306,
    'user': 'your-username',
    'password': 'your-password',
    'database': 'your-database'
}

API_ID = 'your-api-id'
API_HASH = 'your-api-hash'
PHONE_NUMBER = 'your-phone-number'

BOT_SERVER_URL = 'http://your-server:port/api/messages'
API_KEY = 'your-secret-api-key'
```

**Для ConfigBot (config_bot.py):**
```bash
DB_CONFIG = {
    'host': 'your-mysql-host',
    'port': 3306,
    'user': 'your-username',
    'password': 'your-password',
    'database': 'your-database'
}

BOT_TOKEN = 'your-bot-token'
API_KEY = 'your-secret-api-key'  # Должен совпадать с API_KEY в UserBot
```

### 5. Запуск системы
**Запуск ConfigBot:**
```bash
python config_bot.py
```

**Запуск UserBot:**
```bash
python userbot.py
```

## Использование

### Настройка мониторинга через Telegram бота
1. Найдите вашего бота в Telegram
2. Используйте команду /start для подписки на уведомления
3. Используйте меню для управления настройками:
* Добавление/удаление отслеживаемых пользователей
* Добавление/удаление ключевых слов
* Просмотр текущих настроек

### Структура базы данных
* ```bot_config``` - настройки мониторинга
* ```subscribers``` - подписчики на уведомления
* ```processed_messages``` - кэш обработанных сообщений

## API Endpoints

### Прием сообщений (ConfigBot)
* URL: ```/api/messages```
* Method: ```POST```
* Authentication: Bearer token
* Content-Type: ```application/json```
Пример тела запроса:
```json
{
    "message_hash": "hash_value",
    "sender_id": 123456789,
    "sender_username": "username",
    "message_text": "Текст сообщения",
    "chat_title": "Название чата",
    "message_date": "2024-01-01T12:00:00"
}
```

### Безопасность
* Используйте сложные API ключи
* Настройте брандмауэр для ограничения доступа к портам
* Регулярно обновляйте зависимости
* Используйте виртуальное окружение Python
