import aiosqlite
from contextlib import asynccontextmanager

_db_path: str = ""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,
    brand           TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    year_from       INTEGER NOT NULL,
    year_to         INTEGER NOT NULL,
    mileage_from    INTEGER NOT NULL,
    mileage_to      INTEGER NOT NULL,
    optional_filters TEXT    NOT NULL DEFAULT '{}',
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_listings (
    source      TEXT    NOT NULL,
    listing_id  TEXT    NOT NULL,
    config_id   INTEGER NOT NULL,
    seen_at     TEXT    NOT NULL,
    PRIMARY KEY (source, listing_id)
);

CREATE TABLE IF NOT EXISTS state (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""


async def init_db(db_path: str) -> None:
    global _db_path
    _db_path = db_path
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
