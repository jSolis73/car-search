import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from carbot.storage.configs import get_configs, set_config_status, delete_config, get_config
from carbot.storage.state import get_state

log = logging.getLogger(__name__)
router = Router()


def _status_line(status: str) -> str:
    return "▶️ активна" if status == "active" else "⏸ пауза"


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 CarWatch Bot запущен.\n\n"
        "Команды:\n"
        "/add — добавить конфигурацию поиска\n"
        "/list — список конфигураций\n"
        "/del N — удалить конфигурацию\n"
        "/pause N — поставить на паузу\n"
        "/resume N — возобновить\n"
        "/status — состояние бота"
    )


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    configs = await get_configs()
    if not configs:
        await message.answer("Конфигураций нет. Добавьте через /add")
        return

    lines = []
    for cfg in configs:
        name = cfg.name or f"{cfg.brand} {cfg.model}"
        opts = cfg.optional_filters
        details = [
            f"  Год: {cfg.year_from}–{cfg.year_to}",
            f"  Пробег: {cfg.mileage_from:,}–{cfg.mileage_to:,} км".replace(",", " "),
        ]
        if opts.get("price_from") or opts.get("price_to"):
            pf = opts.get("price_from", "")
            pt = opts.get("price_to", "")
            details.append(f"  Цена: {pf}–{pt} ₽")
        if opts.get("geo_city"):
            radius = opts.get("geo_radius")
            geo_str = f"  📍 {opts['geo_city']}"
            if radius:
                geo_str += f" +{radius} км"
            details.append(geo_str)
        lines.append(f"<b>#{cfg.id} {name}</b> {_status_line(cfg.status)}")
        lines.extend(details)

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("del"))
async def cmd_del(message: Message) -> None:
    arg = (message.text or "").removeprefix("/del").strip()
    if not arg.isdigit():
        await message.answer("Укажите номер: /del N")
        return
    config_id = int(arg)
    cfg = await get_config(config_id)
    if not cfg:
        await message.answer(f"Конфигурация #{config_id} не найдена")
        return
    await delete_config(config_id)
    await message.answer(f"Конфигурация #{config_id} удалена")


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    arg = (message.text or "").removeprefix("/pause").strip()
    if not arg.isdigit():
        await message.answer("Укажите номер: /pause N")
        return
    config_id = int(arg)
    ok = await set_config_status(config_id, "paused")
    if ok:
        await message.answer(f"Конфигурация #{config_id} поставлена на паузу")
    else:
        await message.answer(f"Конфигурация #{config_id} не найдена")


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    arg = (message.text or "").removeprefix("/resume").strip()
    if not arg.isdigit():
        await message.answer("Укажите номер: /resume N")
        return
    config_id = int(arg)
    ok = await set_config_status(config_id, "active")
    if ok:
        await message.answer(f"Конфигурация #{config_id} возобновлена")
    else:
        await message.answer(f"Конфигурация #{config_id} не найдена")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    configs = await get_configs()
    active = sum(1 for c in configs if c.status == "active")
    paused = sum(1 for c in configs if c.status == "paused")

    last_autoru = await get_state("last_poll_autoru") or "—"
    last_avito = await get_state("last_poll_avito") or "—"
    autoru_status = await get_state("status_autoru") or "ok"
    avito_status = await get_state("status_avito") or "—"

    def _icon(s: str) -> str:
        return "✅" if s == "ok" else "⚠️"

    text = (
        f"<b>CarWatch Bot</b>\n\n"
        f"auto.ru {_icon(autoru_status)} {autoru_status}\n"
        f"  последний опрос: {last_autoru}\n\n"
        f"Avito {_icon(avito_status)} {avito_status}\n"
        f"  последний опрос: {last_avito}\n\n"
        f"Конфигураций: {len(configs)} (активных: {active}, пауза: {paused})"
    )
    await message.answer(text, parse_mode="HTML")
