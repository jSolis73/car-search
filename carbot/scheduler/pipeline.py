import asyncio
import logging
import random
from datetime import datetime, timezone

from aiogram import Bot

from carbot.bot.formatter import send_listing_card
from carbot.core.filters import apply_optional_filters
from carbot.scrapers.avito import AvitoBlockedError
from carbot.scrapers.base import Scraper
from carbot.storage.configs import Config, get_active_configs
from carbot.storage.seen import is_seen, mark_seen
from carbot.storage.state import increment_digest_count, set_state

log = logging.getLogger(__name__)


async def poll_config(
    config: Config,
    scrapers: list[Scraper],
    bot: Bot,
    owner_chat_id: int,
) -> None:
    for scraper in scrapers:
        source = scraper.source
        try:
            raw = await scraper.search(config)
            listings = apply_optional_filters(raw, config)
            log.info("[%s] config #%d: %d total, %d after filter", source, config.id, len(raw), len(listings))

            new_count = 0
            for lst in listings:
                if await is_seen(source, lst.listing_id):
                    continue
                try:
                    await send_listing_card(bot, owner_chat_id, lst)
                    await mark_seen(source, lst.listing_id, config.id)
                    await increment_digest_count(config.id)
                    new_count += 1
                except Exception as exc:
                    log.error("[%s] Failed to send card %s: %s", source, lst.listing_id, exc)

            log.info("[%s] config #%d: %d new notifications sent", source, config.id, new_count)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            await set_state(f"last_poll_{source}", now)
            await set_state(f"status_{source}", "ok")

        except AvitoBlockedError as exc:
            log.warning("Avito blocked: %s", exc)
            await set_state("status_avito", "degraded")
        except Exception as exc:
            log.error("[%s] poll failed for config #%d: %s", source, config.id, exc)
            await set_state(f"status_{source}", "degraded")


async def run_poll_cycle(
    scrapers: list[Scraper],
    bot: Bot,
    owner_chat_id: int,
    config_gap_min: float,
    config_gap_max: float,
) -> None:
    configs = await get_active_configs()
    log.info("Poll cycle started: %d active configs", len(configs))
    for i, config in enumerate(configs):
        await poll_config(config, scrapers, bot, owner_chat_id)
        if i < len(configs) - 1:
            gap = random.uniform(config_gap_min, config_gap_max)
            log.debug("Config gap: %.1f s", gap)
            await asyncio.sleep(gap)
    log.info("Poll cycle done")
