# Запуск CarWatch Bot

## Требования

- Python 3.12+
- SSH-доступ к VPS (для туннеля Telegram)

## Первый запуск

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Настроить переменные окружения

Файл `carbot/config/.env.local` уже создан. Проверь, что заполнены:

```
TELEGRAM_BOT_TOKEN=...     # токен от @BotFather
OWNER_CHAT_ID=...          # твой chat_id (узнать через @userinfobot)
PROFILE=local
DB_PATH=carbot.db
TELEGRAM_PROXY_URL=socks5://localhost:1080
```

### 3. Получить OWNER_CHAT_ID

Напиши боту [@userinfobot](https://t.me/userinfobot) — он пришлёт твой `id`.

---

## Каждый запуск

### Шаг 1 — Открыть SSH-туннель (для Telegram)

Telegram заблокирован провайдером, поэтому нужен SOCKS5-туннель через VPS.

В **отдельном** окне PowerShell:

```powershell
ssh -D 1080 -N user@<IP_VPS>
```

- `-D 1080` — локальный SOCKS5 на порту 1080
- `-N` — не запускать команды, только туннель
- Окно должно оставаться **открытым** пока работает бот

> Проверить туннель: `curl --socks5 localhost:1080 https://api.telegram.org`

### Шаг 2 — Запустить бота

В рабочей папке `f:\Нейросети\Проекты\tg-car-bot`:

```powershell
$env:PROFILE="local"; python main.py
```

---

## Управление ботом в Telegram

| Команда      | Описание                        |
|--------------|---------------------------------|
| `/add`       | Добавить конфигурацию поиска    |
| `/list`      | Список конфигураций             |
| `/del N`     | Удалить конфигурацию №N         |
| `/pause N`   | Поставить на паузу №N           |
| `/resume N`  | Возобновить №N                  |
| `/status`    | Состояние бота                  |

---

## Остановка

`Ctrl+C` в окне с ботом, затем закрыть окно с SSH-туннелем.

---

## Переменные окружения (справка)

| Переменная              | По умолчанию | Описание                             |
|-------------------------|--------------|--------------------------------------|
| `TELEGRAM_BOT_TOKEN`    | —            | обязательно                          |
| `OWNER_CHAT_ID`         | —            | обязательно                          |
| `PROFILE`               | —            | `local` или `server`                 |
| `DB_PATH`               | —            | путь к `carbot.db`                   |
| `TELEGRAM_PROXY_URL`    | —            | SOCKS5 для Telegram (`local`)        |
| `AVITO_ENABLED`         | `false`      | включить Avito                       |
| `POLL_INTERVAL_MIN`     | `30`         | интервал опроса (минуты)             |
| `POLL_JITTER_MIN`       | `7`          | случайное отклонение (минуты)        |
| `MAX_PAGES_PER_POLL`    | `2`          | страниц за один опрос                |
| `MAX_LISTING_AGE_DAYS`  | `7`          | макс. возраст объявления (дней)      |
| `DIGEST_HOUR_MSK`       | `10`         | час отправки дневного дайджеста (МСК)|
