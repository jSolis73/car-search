import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .db import get_db

MAX_CONFIGS = 3


@dataclass
class Config:
    id: int
    brand: str
    model: str
    year_from: int
    year_to: int
    mileage_from: int
    mileage_to: int
    status: str
    created_at: str
    name: Optional[str] = None
    optional_filters: dict = field(default_factory=dict)


def _row_to_config(row) -> Config:
    return Config(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        model=row["model"],
        year_from=row["year_from"],
        year_to=row["year_to"],
        mileage_from=row["mileage_from"],
        mileage_to=row["mileage_to"],
        optional_filters=json.loads(row["optional_filters"] or "{}"),
        status=row["status"],
        created_at=row["created_at"],
    )


async def get_configs() -> list[Config]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM configs ORDER BY id")
        rows = await cursor.fetchall()
    return [_row_to_config(r) for r in rows]


async def get_active_configs() -> list[Config]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM configs WHERE status='active' ORDER BY id")
        rows = await cursor.fetchall()
    return [_row_to_config(r) for r in rows]


async def get_config(config_id: int) -> Optional[Config]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM configs WHERE id=?", (config_id,))
        row = await cursor.fetchone()
    return _row_to_config(row) if row else None


async def count_configs() -> int:
    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM configs")
        row = await cursor.fetchone()
    return row[0]


async def create_config(
    brand: str,
    model: str,
    year_from: int,
    year_to: int,
    mileage_from: int,
    mileage_to: int,
    optional_filters: dict | None = None,
    name: str | None = None,
) -> Config:
    if await count_configs() >= MAX_CONFIGS:
        raise ValueError(f"Лимит конфигураций достигнут ({MAX_CONFIGS}). Удалите одну через /del.")

    now = datetime.now(timezone.utc).isoformat()
    filters_json = json.dumps(optional_filters or {}, ensure_ascii=False)

    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO configs (name, brand, model, year_from, year_to,
               mileage_from, mileage_to, optional_filters, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (name, brand, model, year_from, year_to, mileage_from, mileage_to, filters_json, now),
        )
        await db.commit()
        config_id = cursor.lastrowid

    return Config(
        id=config_id,
        name=name,
        brand=brand,
        model=model,
        year_from=year_from,
        year_to=year_to,
        mileage_from=mileage_from,
        mileage_to=mileage_to,
        optional_filters=optional_filters or {},
        status="active",
        created_at=now,
    )


async def set_config_status(config_id: int, status: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE configs SET status=? WHERE id=?", (status, config_id)
        )
        await db.commit()
    return cursor.rowcount > 0


async def delete_config(config_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM configs WHERE id=?", (config_id,))
        await db.commit()
    return cursor.rowcount > 0
