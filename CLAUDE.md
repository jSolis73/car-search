# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Общайся со мной на русском языке

## Project

CarWatch Bot — personal Telegram bot that monitors auto.ru and Avito for used car listings and sends new matches to a single owner. Built as a **Modular Monolith** (one Python process). Full spec is in [SPEC.md](SPEC.md).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run (local profile)
PROFILE=local python main.py

# Run tests
pytest

# Run a single test
pytest tests/test_storage.py::test_dedup -v
```

## Directory Structure

```
carbot/
  bot/        # aiogram handlers, /add dialog state machine, card formatting
  scheduler/  # APScheduler setup, jitter logic, per-config poll pipeline
  scrapers/   # base.py (abstract Scraper + Listing model), autoru.py, avito.py
  storage/    # SQLite schema init, CRUD for configs/seen_listings/state
  core/       # post-filtering, dedup API wrappers, config loader
  config/     # .env.local, .env.server (never commit)
main.py
```

## Architecture

**Data flow:** Bot (aiogram long-polling) ↔ Storage (SQLite) ← Scheduler (APScheduler) → Scrapers → Notifier → Bot

**Scraper interface** — both scrapers implement the same contract; the scheduler doesn't know which platform it's calling:

```python
class Scraper:
    source: str  # "autoru" | "avito"
    async def search(self, config: Config) -> list[Listing]: ...
```

**Dedup flow:** `search()` → post-filter → `is_seen(source, listing_id)` → send card → `mark_seen(source, listing_id, config_id)`. The unique index on `(source, listing_id)` in `seen_listings` is the source of truth.

**Configs are polled sequentially**, never in parallel. Playwright concurrency = 1. APScheduler runs one config at a time with a random gap between them (30–90 s).

## Key Constraints

**Single-owner:** every incoming Telegram message where `chat_id != OWNER_CHAT_ID` must be silently ignored — enforced in middleware/handler, not per-command.

**Long-polling only** (no webhook) — must work locally without a public IP.

**Config limit:** max 3 rows in `configs` table, enforced at storage layer before `/add` creates a record.

**Human-like timing (three independent layers):**

1. Poll interval: `POLL_INTERVAL_MIN ± POLL_JITTER_MIN` (default 30 ± 7 min) — jitter is mandatory.
2. Config gap: random 30–90 s between polling different configs.
3. Action/HTTP delay: random per-request pause inside a single scrape session.

**Avito is best-effort** behind `AVITO_ENABLED=true`. A captcha/block must set status to `degraded` and not crash the process; auto.ru continues unaffected.

**PROXY_URL is required when `PROFILE=local` and the local IP is not Russian.** Not needed for `PROFILE=server` (RU IP assumed).

## Environment Variables

| Variable                   | Default | Notes                          |
| -------------------------- | ------- | ------------------------------ |
| `TELEGRAM_BOT_TOKEN`       | —       | required                       |
| `OWNER_CHAT_ID`            | —       | required                       |
| `PROFILE`                  | —       | `local` or `server`            |
| `DB_PATH`                  | —       | path to `carbot.db`            |
| `AVITO_ENABLED`            | `false` | feature flag                   |
| `PROXY_URL`                | —       | required for `local` non-RU IP |
| `POLL_INTERVAL_MIN`        | `30`    |                                |
| `POLL_JITTER_MIN`          | `7`     |                                |
| `CONFIG_GAP_SEC_MIN/MAX`   | `30/90` |                                |
| `ACTION_DELAY_SEC_MIN/MAX` | `1.5/4` | Avito browser actions          |
| `HTTP_DELAY_SEC_MIN/MAX`   | `2/5`   | auto.ru HTTP requests          |
| `MAX_PAGES_PER_POLL`       | `2`     |                                |

## Storage Schema

Three tables, created via `CREATE TABLE IF NOT EXISTS` at startup (no migration framework):

- `configs` — up to 3 rows; `optional_filters` stored as JSON text; `status` is `active` or `paused`.
- `seen_listings` — unique index on `(source, listing_id)`; never deleted.
- `state` — key/value for `last_poll_autoru`, `last_poll_avito`, etc.

## Open Implementation Details

The exact auto.ru internal JSON endpoint and Avito DOM selectors are **not specified** — they must be discovered empirically via DevTools and saved as test fixtures. Keep the repair point isolated inside the respective scraper module.

## Testing

- Unit tests cover: filtering, dedup, request-building, response parsing (against saved fixtures).
- Integration tests use mock HTTP for the full `search → notify` pipeline.
- E2E is manual only (real scrape of both platforms).
