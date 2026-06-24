# CarWatch Bot

Персональный Telegram-бот для мониторинга объявлений о продаже б/у автомобилей на **auto.ru** и **Avito**. Присылает новые подходящие объявления сразу после появления — без дублей, без лишнего шума.

## Возможности

- Мониторинг auto.ru через HTTP с имитацией браузерного TLS
- Мониторинг Avito через Playwright Chromium (при наличии российского IP)
- До 3 поисковых конфигураций одновременно
- Фильтры: марка, модель, год, пробег, цена, владельцы, коробка, топливо, привод, объём, город/регион
- Дедупликация: каждое объявление приходит ровно один раз
- Фильтрация по свежести: только объявления не старше N дней
- Человекоподобные задержки и джиттер интервала — снижение риска блокировок
- Ежедневный дайджест в заданное время (по умолчанию 10:00 МСК)
- Единственный пользователь — все чужие сообщения игнорируются

## Требования

- Python 3.12+
- SSH-туннель к VPS с российским IP (для доступа к Telegram в заблокированных сетях)

## Установка

```bash
git clone <repo>
cd tg-car-bot
pip install -r requirements.txt
python -m playwright install chromium
```

## Настройка

Отредактируй `carbot/config/.env.local`:

```env
TELEGRAM_BOT_TOKEN=...        # токен от @BotFather
OWNER_CHAT_ID=...             # твой chat_id (узнать через @userinfobot)
PROFILE=local
DB_PATH=carbot.db
TELEGRAM_PROXY_URL=socks5://localhost:1080
```

## Запуск

**Шаг 1.** Открой SSH-туннель (в отдельном окне):

```powershell
ssh -D 1080 -N user@<IP_VPS>
```

Окно должно оставаться открытым пока работает бот.

**Шаг 2.** Запусти бота:

```powershell
$env:PROFILE="local"; python main.py
```

Остановка: `Ctrl+C`, затем закрыть окно с туннелем.

## Команды

| Команда | Описание |
|---|---|
| `/add` | Создать поисковую конфигурацию (пошаговый диалог) |
| `/list` | Список конфигураций и их статус |
| `/del N` | Удалить конфигурацию №N |
| `/pause N` | Поставить конфигурацию №N на паузу |
| `/resume N` | Возобновить конфигурацию №N |
| `/status` | Состояние каналов и время последнего опроса |

## Структура проекта

```
carbot/
  bot/        # aiogram-хендлеры, FSM-диалог /add, форматирование карточек
  scheduler/  # APScheduler: цикл опроса + ежедневный дайджест
  scrapers/   # base.py (интерфейс Scraper + модель Listing), autoru.py, avito.py
  storage/    # SQLite: схема, CRUD конфигов, дедупликация, состояние
  core/       # пост-фильтрация, загрузчик настроек, геолокация
  config/     # .env.local, .env.server (не коммитить)
main.py
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | обязательно |
| `OWNER_CHAT_ID` | — | обязательно |
| `PROFILE` | — | `local` или `server` |
| `DB_PATH` | — | путь к `carbot.db` |
| `TELEGRAM_PROXY_URL` | — | SOCKS5 для Telegram (нужен при `local`) |
| `AVITO_ENABLED` | `false` | включить Avito (требует российский IP) |
| `PROXY_URL` | — | прокси для скраперов (российский residential) |
| `POLL_INTERVAL_MIN` | `30` | базовый интервал опроса, мин |
| `POLL_JITTER_MIN` | `7` | случайное отклонение интервала, мин |
| `CONFIG_GAP_SEC_MIN` | `30` | мин. пауза между конфигами, сек |
| `CONFIG_GAP_SEC_MAX` | `90` | макс. пауза между конфигами, сек |
| `HTTP_DELAY_SEC_MIN` | `2` | мин. задержка между HTTP-запросами, сек |
| `HTTP_DELAY_SEC_MAX` | `5` | макс. задержка между HTTP-запросами, сек |
| `ACTION_DELAY_SEC_MIN` | `1.5` | мин. задержка браузерных действий, сек |
| `ACTION_DELAY_SEC_MAX` | `4` | макс. задержка браузерных действий, сек |
| `MAX_PAGES_PER_POLL` | `2` | страниц за один опрос |
| `MAX_LISTING_AGE_DAYS` | `7` | макс. возраст объявления (только auto.ru) |
| `DIGEST_HOUR_MSK` | `10` | час дайджеста по МСК |

## Примечания по Avito

Avito требует российский IP и блокирует запросы из-за рубежа на уровне сети. При запуске локально с нероссийским IP установи `AVITO_ENABLED=false`. Для включения нужен российский residential proxy (`PROXY_URL=http://user:pass@host:port`) или деплой на российский VPS.

## Деплой на сервер

Скопируй `carbot/config/.env.server`, заполни переменные (без `TELEGRAM_PROXY_URL` и `PROXY_URL` — российский IP не требует прокси). Создай systemd-сервис:

```ini
[Unit]
Description=CarWatch Bot
After=network.target

[Service]
WorkingDirectory=/opt/tg-car-bot
ExecStart=/usr/bin/python main.py
Environment=PROFILE=server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now carwatch
```
