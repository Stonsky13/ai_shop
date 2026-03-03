## Telegram AI Shop Bot  
Телеграм бот для продажи доступа к ИИ с интеграциями Юкасса для платежей, proxyapi для ИИ и google sheets для истории ивентов.
---

## Стек

- Python 3.12+
- aiogram 3.x
- SQLAlchemy (async)
- SQLite (aiosqlite)
- YooKassa SDK
- httpx (async HTTP client)
- gspread + google-auth
- Docker / Docker Compose

---

## Архитектура

User flow:

1. Юзер отправляет `/buy` чтобы купить подписку
2. Бот создает платеж в юкассе
3. Юзер оплачивает по ссылке 
4. Бот пуллит апи юкассы
5. Когда статус становится `payment.succeeded`:
   - Активируется подписка
   - Событие логгируется в гугл таблицу
6. Юзер может задать вопрос через `/ask <question>`

Слои архитектуры:

- Handlers (Telegram слой)
- Services (бизнес логика)
- External clients (YooKassa / AI / Sheets)

---

## Установка
### 1. Склонируйте проект

```bash
git clone <repo_url>
cd tg_ai_yookassa_sheets_bot
```
### 2. создайте .env
скопируйте переменные из .env.example и заполните свои значения

### 3. Настройте Google Sheets
1. Перейдите в Google Cloud Console, создайте проект и включите Google Sheets API
2. Создайте Service Account 
3. Сгенерируйте JSON ключ 
4. Вставьте полученный JSOn в data/service_account.json
5. Внутри нужной гугл таблицы выдайте доступ по почте Service Account

### 4. Запустите через Docker

```bash
docker compose up --build
```

## Команды бота
1. /start - показ главного менб
2. /buy -  купить доступ к ИИ
3. /status - првоерить статус подписки
4. /ask <question> - вопрос к ИИ
