from typing import Optional

from .db import get_db


async def get_state(key: str) -> Optional[str]:
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM state WHERE key=?", (key,))
        row = await cursor.fetchone()
    return row["value"] if row else None


async def set_state(key: str, value: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()


async def increment_digest_count(config_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO state (key, value) VALUES (?, '1') "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)",
            (f"digest_count_{config_id}",),
        )
        await db.commit()


async def get_digest_count(config_id: int) -> int:
    row = await get_state(f"digest_count_{config_id}")
    return int(row) if row else 0


async def reset_digest_counts() -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM state WHERE key LIKE 'digest_count_%'")
        await db.commit()
