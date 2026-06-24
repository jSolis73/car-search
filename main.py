import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from carbot.bot.dialogs import router as dialogs_router
from carbot.bot.handlers import router as handlers_router
from carbot.bot.middleware import OwnerMiddleware
from carbot.core.config_loader import load_settings
from carbot.scheduler.scheduler import start_scheduler, stop_scheduler
from carbot.storage.db import init_db


class _SocksSession(AiohttpSession):
    def __init__(self, socks_url: str):
        super().__init__()
        self._socks_url = socks_url

    async def create_session(self):
        import aiohttp
        from aiohttp_socks import ProxyConnector
        if isinstance(getattr(self, "_session", None), aiohttp.ClientSession):
            return self._session
        self._session = aiohttp.ClientSession(
            connector=ProxyConnector.from_url(self._socks_url)
        )
        return self._session


def _make_bot(token: str, telegram_proxy_url: str | None) -> Bot:
    if telegram_proxy_url:
        return Bot(token=token, session=_SocksSession(telegram_proxy_url))
    return Bot(token=token)


async def main() -> None:
    settings = load_settings()

    logging.basicConfig(
        level=logging.DEBUG if settings.profile == "local" else logging.INFO,
        format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
    )
    log = logging.getLogger(__name__)
    log.info("Starting CarWatch Bot (profile=%s)", settings.profile)

    await init_db(settings.db_path)
    log.info("Database ready: %s", settings.db_path)

    bot = _make_bot(settings.telegram_bot_token, settings.telegram_proxy_url)
    if settings.telegram_proxy_url:
        log.info("Telegram → %s", settings.telegram_proxy_url)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(OwnerMiddleware(settings.owner_chat_id))

    # dialogs router first so FSM states take priority
    dp.include_router(dialogs_router)
    dp.include_router(handlers_router)

    await bot.set_my_commands([
        BotCommand(command="add",    description="Добавить конфигурацию поиска"),
        BotCommand(command="list",   description="Список конфигураций"),
        BotCommand(command="del",    description="Удалить конфигурацию (/del N)"),
        BotCommand(command="pause",  description="Поставить на паузу (/pause N)"),
        BotCommand(command="resume", description="Возобновить (/resume N)"),
        BotCommand(command="status", description="Состояние бота"),
    ])

    scheduler = await start_scheduler(bot, settings)

    try:
        log.info("Bot polling started")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await stop_scheduler(scheduler)
        await bot.session.close()
        log.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
