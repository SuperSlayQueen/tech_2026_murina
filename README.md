# Dating Bot

> Telegram-бот для знакомств с анкетами, лайками, взаимными мэтчами и системой рейтинга.

Dating Bot — асинхронное Telegram-приложение, в котором пользователи создают анкеты, находят потенциальных партнёров, ставят лайки и получают мэтчи при взаимной симпатии.

Проект построен как полноценное backend-приложение с PostgreSQL, Redis, RabbitMQ и Celery. Запуск всей инфраструктуры выполняется через Docker Compose.

## ✨ Возможности

* 👤 регистрация пользователя через Telegram;
* 📝 создание и редактирование анкеты;
* 🔎 поиск анкет;
* ❤️ система лайков;
* 💕 автоматическое создание мэтча при взаимном лайке;
* ⭐ рейтинг пользователей;
* 🏙️ фильтрация анкет по городу;
* ⚧️ фильтрация по полу;
* ⚙️ фоновые и периодические задачи;
* 📨 обработка событий через очередь сообщений;
* 🗄️ PostgreSQL для хранения данных;
* ⚡ Redis для кэширования и Celery result backend;
* 🐇 RabbitMQ для очереди задач;
* 🐳 запуск всех компонентов через Docker Compose;
* 🧪 тесты ключевой бизнес-логики.

---

## 🏗️ Архитектура

Проект разделяет пользовательский интерфейс Telegram-бота, backend-логику и фоновые задачи.

```text
                    ┌──────────────────┐
                    │     Telegram     │
                    │      User        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Telegram Bot   │
                    │     aiogram      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     Backend      │
                    │ SQLAlchemy 2.x   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    PostgreSQL    │
                    │      Data        │
                    └──────────────────┘

                             │
                    events / background
                             │
                             ▼
                    ┌──────────────────┐
                    │    RabbitMQ      │
                    │   Message Queue  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │      Celery      │
                    │      Worker      │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    ▼                  ▼
             Rating recalculation   Like/Match events

                    ┌──────────────────┐
                    │      Redis       │
                    │ Cache / Results   │
                    └──────────────────┘
```

Основная инфраструктура поднимается через Docker Compose и включает PostgreSQL, Redis, RabbitMQ, Telegram Bot, Celery Worker и Celery Beat.

---

## 🧩 Основные компоненты

### Telegram Bot

Пользовательский интерфейс приложения реализован как Telegram-бот на **aiogram 3.x**.

Основная логика разделена на handlers:

```text
bot/
├── handlers/
│   ├── start.py
│   └── menu.py
├── keyboards.py
├── middleware.py
└── main.py
```

`start.py` отвечает за `/start` и регистрацию пользователя, а `menu.py` — за основное меню и пользовательские сценарии.

### Backend

Backend содержит модели и работу с базой данных.

Основные сущности:

```text
User
  │
  └── Profile
       │
       ├── Like
       │
       ├── Match
       │
       └── Rating
```

Для работы с PostgreSQL используется **SQLAlchemy 2.x** и асинхронный драйвер **asyncpg**.

### Celery

Фоновые операции вынесены из основного bot flow.

Celery используется для:

* периодического пересчёта рейтингов;
* обработки событий лайков;
* обработки событий мэтчей;
* выполнения фоновых задач.

Для периодических задач используется **Celery Beat**.

### RabbitMQ

RabbitMQ используется как message broker для фоновых задач и обработки событий.

```text
Bot
 │
 └── Like / Match event
          │
          ▼
      RabbitMQ
          │
          ▼
     Celery Worker
          │
          ▼
       Database
```

Это позволяет не выполнять потенциально долгие операции непосредственно в обработчике Telegram-сообщения.

### Redis

Redis используется как:

* cache;
* backend результатов Celery-задач.

Таким образом, Redis отделён от основной persistent database PostgreSQL.

---

## 👤 Пользовательский сценарий

После запуска пользователь отправляет боту:

```text
/start
```

Далее:

```text
Start
  ↓
Registration
  ↓
Create Profile
  ↓
Main Menu
  ├── Моя анкета
  ├── Поиск пары
  ├── Мои лайки
  └── Мои мэтчи
```

Такой пользовательский flow реализован непосредственно в текущей версии проекта.

---

## ❤️ Лайки и мэтчи

Основная механика знакомств строится вокруг взаимных лайков.

```text
User A
  │
  │ ❤️ Like
  ▼
User B
  │
  │ ❤️ Like
  ▼
Match
```

Если пользователь B уже поставил лайк пользователю A, повторный лайк создаёт взаимный `Match`.

На уровне базы данных предусмотрены ограничения, которые не позволяют создавать дублирующиеся лайки и одинаковые пары мэтчей.

---

## ⭐ Rating System

В проекте реализована система рейтинга пользователей.

Пересчёт рейтингов выполняется как фоновая периодическая задача через Celery Beat.

```text
Users
  │
  ▼
Rating calculation
  │
  ▼
Celery Worker
  │
  ▼
Updated ratings
```

Такой подход позволяет не выполнять массовый пересчёт рейтингов во время обычного пользовательского запроса.

---

## 🔎 Поиск анкет

Поиск поддерживает фильтрацию по:

* полу;
* городу.

Для часто используемых полей поиска в PostgreSQL добавлен индекс:

```text
(gender, city)
```

Это позволяет базе эффективнее выполнять запросы по основным фильтрам каталога анкет.

---

## 🛡️ Ограничения данных

На уровне базы данных и валидации предусмотрены ограничения для повышения целостности данных.

В частности:

* возраст анкеты ограничен диапазоном `16–100`;
* лайк между двумя пользователями должен быть уникальным;
* пара пользователей в `Match` должна быть уникальной;
* для полей поиска используются индексы.

Таким образом, часть бизнес-инвариантов защищена не только кодом приложения, но и структурой данных.

---

## 🛠️ Tech Stack

### Application

* **Python 3.10+**
* **aiogram 3.x**
* **SQLAlchemy 2.x**
* **asyncpg**
* **Pydantic**

### Background Processing

* **Celery**
* **Celery Beat**
* **RabbitMQ**

### Storage

* **PostgreSQL**
* **Redis**

### Infrastructure

* **Docker**
* **Docker Compose**

### Testing

* **pytest**

Все основные технологии перечислены в текущей документации проекта.

---

## 📁 Project Structure

```text
tech_2026_murina/
│
├── dating_bot/
│   │
│   ├── src/
│   │   │
│   │   ├── bot/
│   │   │   ├── handlers/
│   │   │   │   ├── start.py
│   │   │   │   └── menu.py
│   │   │   │
│   │   │   ├── keyboards.py
│   │   │   ├── middleware.py
│   │   │   └── main.py
│   │   │
│   │   ├── backend/
│   │   │   ├── models/
│   │   │   │   └── models.py
│   │   │   └── database.py
│   │   │
│   │   └── config/
│   │       ├── settings.py
│   │       └── __init__.py
│   │
│   ├── .env.example
│   ├── requirements.txt
│   └── ...
│
├── practice_tasks/
├── architecture.md
└── README.md
```

Основная рабочая директория приложения — `dating_bot`. В репозитории также находятся `practice_tasks` и отдельный документ `architecture.md`.

---

## 🚀 Запуск

### Requirements

Для запуска потребуются:

* Python 3.10+;
* Docker;
* Docker Compose;
* Telegram Bot Token.

### 1. Клонирование

```bash
git clone https://github.com/SuperSlayQueen/tech_2026_murina.git
cd tech_2026_murina
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

Команда соответствует текущей инструкции запуска проекта.

### 3. Настройка окружения

Создайте `.env` на основе:

```bash
cp .env.example .env
```

Заполните необходимые environment variables, включая Telegram Bot Token.

### 4. Запуск инфраструктуры

```bash
docker compose up -d --build
```

Docker Compose поднимет:

```text
PostgreSQL
Redis
RabbitMQ
Telegram Bot
Celery Worker
Celery Beat
```

### 5. Проверка

```bash
docker compose ps
```

Убедитесь, что необходимые контейнеры находятся в рабочем состоянии.

---

## 🧪 Testing

В проекте предусмотрены тесты для ключевой логики рейтинга.

Запуск:

```bash
pytest
```

Тестирование особенно важно для бизнес-правил, связанных с рейтингом, лайками и мэтчами.

---

## 🔄 Background Processing

Одна из ключевых архитектурных особенностей проекта — перенос фоновых операций в отдельный worker.

Вместо:

```text
Telegram Handler
      │
      ├── calculate rating
      ├── update database
      └── process events
```

используется:

```text
Telegram Handler
      │
      ▼
   RabbitMQ
      │
      ▼
Celery Worker
      │
      ├── process event
      ├── update rating
      └── update database
```

Это уменьшает нагрузку на основной bot process и позволяет обрабатывать задачи асинхронно.

---

## 🐳 Docker

Все ключевые компоненты запускаются в контейнерах.

```text
Docker Compose
│
├── PostgreSQL
├── Redis
├── RabbitMQ
├── Bot
├── Celery Worker
└── Celery Beat
```

Также для сервисов настроен автоматический restart с политикой:

```text
restart: unless-stopped
```

Это позволяет сервисам автоматически подниматься после перезапуска Docker-хоста.

---

## 🔐 Configuration

Конфигурация приложения вынесена в environment variables.

В репозитории предусмотрен:

```text
.env.example
```

Секреты и токены не должны храниться непосредственно в исходном коде.

Минимально необходимая конфигурация включает Telegram Bot Token и параметры подключения к инфраструктуре.

---

## 📐 Architecture Decisions

Проект использует несколько инфраструктурных компонентов не ради усложнения, а для разделения разных типов нагрузки.

| Component     | Responsibility                  |
| ------------- | ------------------------------- |
| Telegram Bot  | пользовательские взаимодействия |
| PostgreSQL    | persistent data                 |
| Redis         | cache / task results            |
| RabbitMQ      | message broker                  |
| Celery Worker | background jobs                 |
| Celery Beat   | scheduled jobs                  |

Такое разделение позволяет независимо масштабировать пользовательский процесс и фоновые операции.

---

## 📊 Что демонстрирует проект

Проект показывает практическую работу с backend-системой, построенной вокруг асинхронного Telegram-приложения.

Ключевые инженерные задачи:

* асинхронное программирование на Python;
* Telegram Bot API;
* SQLAlchemy 2.x;
* PostgreSQL;
* database constraints;
* индексация;
* Redis;
* message broker;
* background workers;
* scheduled tasks;
* Docker Compose;
* automated tests;
* configuration через environment variables.

---

## 🔮 Возможное развитие

Следующим этапом проект можно расширить:

### Product features

* фотографии пользователей;
* расширенные фильтры;
* геолокация;
* рекомендации;
* блокировка пользователей;
* жалобы;
* уведомления о новых мэтчах;
* личный чат после мэтча.

### Backend

* полноценный REST API;
* JWT authentication для внешних клиентов;
* pagination;
* rate limiting;
* structured logging;
* централизованный error handling.

### Infrastructure

* Prometheus + Grafana;
* distributed tracing;
* CI/CD;
* health checks;
* graceful shutdown;
* горизонтальное масштабирование workers.

### Testing

* unit tests для всех бизнес-правил;
* integration tests с PostgreSQL;
* tests для Celery tasks;
* tests для Telegram handlers;
* end-to-end сценарии.

---

## 📌 Project Status

**In development**

Основной пользовательский flow, система анкет, лайков и мэтчей реализованы. В проект также добавлены фоновые задачи, рейтинг, ограничения целостности данных, индексация и тесты ключевой логики.

---

## 🤖 Demo

Telegram-бот доступен по ссылке:

**LalaDateBot** — [t.me/LalaDateBot](https://t.me/LalaDateBot)

Используйте `/start`, чтобы начать регистрацию и создать анкету.

---

## 👤 Author

**SuperSlayQueen**

GitHub: [@SuperSlayQueen](https://github.com/SuperSlayQueen)


