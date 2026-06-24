from datetime import datetime, timezone

from .db import get_db


async def is_seen(source: str, listing_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT 1 FROM seen_listings WHERE source=? AND listing_id=?",
            (source, listing_id),
        )
        row = await cursor.fetchone()
    return row is not None


async def mark_seen(source: str, listing_id: str, config_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT OR IGNORE INTO seen_listings (source, listing_id, config_id, seen_at)
               VALUES (?, ?, ?, ?)""",
            (source, listing_id, config_id, now),
        )
        await db.commit()
