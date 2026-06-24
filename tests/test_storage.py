import asyncio
import pytest

from carbot.storage.db import init_db
from carbot.storage.configs import create_config, get_configs, delete_config, count_configs, MAX_CONFIGS
from carbot.storage.seen import is_seen, mark_seen


@pytest.fixture
async def db(tmp_path):
    path = str(tmp_path / "test.db")
    await init_db(path)
    return path


@pytest.mark.asyncio
async def test_create_and_list_config(db):
    cfg = await create_config("BMW", "3ER", 2018, 2023, 0, 100_000)
    assert cfg.id is not None
    configs = await get_configs()
    assert len(configs) == 1
    assert configs[0].brand == "BMW"


@pytest.mark.asyncio
async def test_config_limit(db):
    for i in range(MAX_CONFIGS):
        await create_config("Toyota", "CAMRY", 2015, 2023, 0, 200_000)
    with pytest.raises(ValueError, match="Лимит"):
        await create_config("Honda", "CIVIC", 2015, 2023, 0, 150_000)


@pytest.mark.asyncio
async def test_delete_config(db):
    cfg = await create_config("Kia", "RIO", 2019, 2023, 10_000, 80_000)
    deleted = await delete_config(cfg.id)
    assert deleted is True
    assert await count_configs() == 0


@pytest.mark.asyncio
async def test_dedup(db):
    cfg = await create_config("Lada", "VESTA", 2020, 2023, 0, 50_000)
    assert not await is_seen("autoru", "abc123")
    await mark_seen("autoru", "abc123", cfg.id)
    assert await is_seen("autoru", "abc123")


@pytest.mark.asyncio
async def test_dedup_idempotent(db):
    cfg = await create_config("Lada", "GRANTA", 2021, 2023, 0, 30_000)
    await mark_seen("autoru", "dup1", cfg.id)
    await mark_seen("autoru", "dup1", cfg.id)  # second call must not raise
    assert await is_seen("autoru", "dup1")


@pytest.mark.asyncio
async def test_dedup_different_sources(db):
    cfg = await create_config("Hyundai", "SOLARIS", 2020, 2023, 0, 60_000)
    await mark_seen("autoru", "x1", cfg.id)
    assert not await is_seen("avito", "x1")  # different source
