from aiogram import Bot

from carbot.scrapers.base import Listing

_TRANSMISSION_RU = {
    "AUTOMATIC": "Автомат",
    "MANUAL": "Механика",
    "ROBOT": "Робот",
    "VARIATOR": "Вариатор",
}

_ENGINE_RU = {
    "GASOLINE": "Бензин",
    "DIESEL": "Дизель",
    "ELECTRO": "Электро",
    "HYBRID": "Гибрид",
}

_GEAR_RU = {
    "ALL_WHEEL_DRIVE": "Полный",
    "FORWARD_CONTROL": "Передний",
    "REAR_DRIVE": "Задний",
}

_SOURCE_LABEL = {
    "autoru": "auto.ru",
    "avito": "Avito",
}


def format_listing(lst: Listing) -> str:
    lines = [f"<b>{lst.title}</b>"]

    parts = []
    if lst.price:
        parts.append(f"💰 {lst.price:,} ₽".replace(",", " "))
    if lst.year:
        parts.append(f"📅 {lst.year} г.")
    if lst.mileage is not None:
        parts.append(f"🛣 {lst.mileage:,} км".replace(",", " "))
    if parts:
        lines.append("  ".join(parts))

    tech_parts = []
    if lst.displacement:
        tech_parts.append(f"{lst.displacement:.1f}л")
    if lst.engine_type:
        tech_parts.append(_ENGINE_RU.get(lst.engine_type, lst.engine_type))
    if lst.transmission:
        tech_parts.append(_TRANSMISSION_RU.get(lst.transmission, lst.transmission))
    if lst.gear_type:
        tech_parts.append(_GEAR_RU.get(lst.gear_type, lst.gear_type))
    if tech_parts:
        lines.append(" · ".join(tech_parts))

    if lst.owners_count:
        lines.append(f"👤 Владельцев: {lst.owners_count}")
    if lst.location:
        lines.append(f"📍 {lst.location}")

    source_label = _SOURCE_LABEL.get(lst.source, lst.source)
    lines.append(f'\n<a href="{lst.url}">{source_label} →</a>')

    return "\n".join(lines)


async def send_listing_card(bot: Bot, chat_id: int, lst: Listing) -> None:
    text = format_listing(lst)
    if lst.photo_url:
        try:
            await bot.send_photo(
                chat_id,
                photo=lst.photo_url,
                caption=text,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass  # fallback to text if photo fails
    await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
