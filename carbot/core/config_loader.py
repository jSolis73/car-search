import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BASE = Path(__file__).parent.parent  # carbot/


@dataclass
class Settings:
    telegram_bot_token: str
    owner_chat_id: int
    profile: str
    db_path: str
    proxy_url: str | None
    telegram_proxy_url: str | None
    avito_enabled: bool
    poll_interval_min: int
    poll_jitter_min: int
    config_gap_sec_min: int
    config_gap_sec_max: int
    action_delay_sec_min: float
    action_delay_sec_max: float
    http_delay_sec_min: float
    http_delay_sec_max: float
    max_pages_per_poll: int
    max_listing_age_days: int
    digest_hour_msk: int


def load_settings() -> Settings:
    profile = os.environ.get("PROFILE", "")
    if profile == "local":
        load_dotenv(_BASE / "config" / ".env.local", override=False)
    elif profile == "server":
        load_dotenv(_BASE / "config" / ".env.server", override=False)
    else:
        raise ValueError(f"PROFILE must be 'local' or 'server', got: {profile!r}")

    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        owner_chat_id=int(os.environ["OWNER_CHAT_ID"]),
        profile=profile,
        db_path=os.environ["DB_PATH"],
        proxy_url=os.environ.get("PROXY_URL") or None,
        telegram_proxy_url=os.environ.get("TELEGRAM_PROXY_URL") or None,
        avito_enabled=os.environ.get("AVITO_ENABLED", "false").lower() == "true",
        poll_interval_min=int(os.environ.get("POLL_INTERVAL_MIN", "30")),
        poll_jitter_min=int(os.environ.get("POLL_JITTER_MIN", "7")),
        config_gap_sec_min=int(os.environ.get("CONFIG_GAP_SEC_MIN", "30")),
        config_gap_sec_max=int(os.environ.get("CONFIG_GAP_SEC_MAX", "90")),
        action_delay_sec_min=float(os.environ.get("ACTION_DELAY_SEC_MIN", "1.5")),
        action_delay_sec_max=float(os.environ.get("ACTION_DELAY_SEC_MAX", "4")),
        http_delay_sec_min=float(os.environ.get("HTTP_DELAY_SEC_MIN", "2")),
        http_delay_sec_max=float(os.environ.get("HTTP_DELAY_SEC_MAX", "5")),
        max_pages_per_poll=int(os.environ.get("MAX_PAGES_PER_POLL", "2")),
        max_listing_age_days=int(os.environ.get("MAX_LISTING_AGE_DAYS", "7")),
        digest_hour_msk=int(os.environ.get("DIGEST_HOUR_MSK", "10")),
    )
