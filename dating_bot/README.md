# Dating Bot - Этап 2: Базовый функционал

Telegram-бот для знакомств с системой анкет, лайков и мэтчей.

## Инструкция по запуску

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```
### 2. Запуск PostgreSQL

**Windows (через Docker):**
```bash
docker run -d --name postgres-dating \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=dating_bot \
  -p 5432:5432 \
  postgres:15
```

### 3. Запуск бота

```bash
python -m src.bot.main
```

---

## 📁 Структура проекта

```
dating_bot/
├── src/
│   ├── bot/                    # Bot Service
│   │   ├── handlers/           # Обработчики команд
│   │   │   ├── start.py        # /start и регистрация
│   │   │   └── menu.py         # Главное меню
│   │   ├── keyboards.py        # Inline-клавиатуры
│   │   ├── middleware.py       # Middleware для БД
│   │   └── main.py             # Точка входа бота
│   ├── backend/                # Backend (API)
│   │   ├── models/             # SQLAlchemy модели
│   │   │   └── models.py       # User, Profile, Like, Match, Rating
│   │   └── database.py         # Подключение к БД
│   └── config/                 # Конфигурация
│       ├── settings.py         # Pydantic settings
│       └── __init__.py
├── .env.example                # Пример переменных окружения
├── requirements.txt            # Зависимости
├── architecture.md             # Архитектура системы
└── README.md                   # Этот файл
```

---

## 🤖 Как пользоваться ботом

1. **Запуск:** Отправьте `/start` боту
2. **Регистрация:** Заполните анкету (имя, возраст, пол, город, о себе)
3. **Меню:** Используйте кнопки для навигации:
   - 👤 **Моя анкета** - просмотр/Edit своего профиля
   - 🔍 **Поиск пары** - просмотр анкет других пользователей
   - ❤️ **Мои лайки** - история лайков
   - 💕 **Мои мэтчи** - взаимные симпатии


---

## 🛠️ Технологии

- **Python 3.10+**
- **aiogram 3.x** - Telegram Bot API
- **SQLAlchemy 2.x** - ORM
- **asyncpg** - асинхронный драйвер PostgreSQL
- **Pydantic** - валидация настроек

