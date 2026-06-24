import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from carbot.core.config_loader import Settings
from carbot.scrapers.autoru import AutoRuScraper
from carbot.scrapers.avito import AvitoScraper
from carbot.scrapers.base import Scraper
from carbot.scheduler.pipeline import run_poll_cycle
from carbot.storage.configs import get_configs
from carbot.storage.state import get_digest_count, get_state, reset_digest_counts

log = logging.getLogger(__name__)


async def start_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scrapers: list[Scraper] = [
        AutoRuScraper(
            proxy_url=settings.proxy_url,
            http_delay=(settings.http_delay_sec_min, settings.http_delay_sec_max),
            max_pages=settings.max_pages_per_poll,
            max_listing_age_days=settings.max_listing_age_days,
        )
    ]

    avito: AvitoScraper | None = None
    if settings.avito_enabled:
        avito = AvitoScraper(
            proxy_url=settings.proxy_url,
            action_delay=(settings.action_delay_sec_min, settings.action_delay_sec_max),
            max_pages=settings.max_pages_per_poll,
        )
        await avito.start()
        scrapers.append(avito)
        log.info("Avito scraper started")

    async def _job():
        await run_poll_cycle(
            scrapers=scrapers,
            bot=bot,
            owner_chat_id=settings.owner_chat_id,
            config_gap_min=settings.config_gap_sec_min,
            config_gap_max=settings.config_gap_sec_max,
        )

    async def _digest_job():
        configs = await get_configs()
        active = [c for c in configs if c.status == "active"]
        if not active:
            return

        lines = ["📊 <b>CarWatch — итоги за сутки</b>\n"]
        total = 0
        for cfg in active:
            count = await get_digest_count(cfg.id)
            total += count
            name = cfg.name or f"{cfg.brand} {cfg.model}"
            icon = "🔔" if count > 0 else "○"
            lines.append(f"{icon} #{cfg.id} {name}: {count} новых")

        last_poll = await get_state("last_poll_autoru") or "—"
        lines.append(f"\nПоследний опрос: {last_poll}")

        await bot.send_message(
            settings.owner_chat_id,
            "\n".join(lines),
            parse_mode="HTML",
        )
        await reset_digest_counts()
        log.info("Daily digest sent: %d total new listings", total)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(
            minutes=settings.poll_interval_min,
            jitter=settings.poll_jitter_min * 60,
        ),
        id="poll_cycle",
        replace_existing=True,
        max_instances=1,
    )

    digest_hour_utc = (settings.digest_hour_msk - 3) % 24
    scheduler.add_job(
        _digest_job,
        trigger=CronTrigger(hour=digest_hour_utc, minute=0, timezone="UTC"),
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.start()
    log.info(
        "Scheduler started: every %d±%d min, digest at %d:00 MSK",
        settings.poll_interval_min,
        settings.poll_jitter_min,
        settings.digest_hour_msk,
    )

    # Store avito reference for cleanup
    scheduler._avito = avito  # type: ignore[attr-defined]
    return scheduler


async def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    scheduler.shutdown(wait=False)
    avito = getattr(scheduler, "_avito", None)
    if avito:
        await avito.stop()
