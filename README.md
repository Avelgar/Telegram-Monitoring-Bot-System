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
