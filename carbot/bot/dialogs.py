"""
/add dialog — step-by-step FSM for creating a search config.

Mandatory steps: brand → model → year_from → year_to → mileage_from → mileage_to
Optional steps (each accepts /skip): price → owners → transmission → engine_type → gear_type → displacement → city → radius
"""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from carbot.core.geo import resolve_city, popular_cities_hint
from carbot.storage.configs import create_config, count_configs, MAX_CONFIGS

log = logging.getLogger(__name__)
router = Router()

_CURRENT_YEAR = datetime.now().year


class AddStates(StatesGroup):
    brand = State()
    model = State()
    year_from = State()
    year_to = State()
    mileage_from = State()
    mileage_to = State()
    confirm_optional = State()
    opt_price = State()
    opt_owners = State()
    opt_transmission = State()
    opt_engine_type = State()
    opt_gear_type = State()
    opt_displacement = State()
    opt_city = State()
    opt_radius = State()
    opt_avito_url = State()


def _skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip")]]
    )


def _yes_no_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="opt_yes"),
                InlineKeyboardButton(text="Нет, сохранить", callback_data="opt_no"),
            ]
        ]
    )


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    if await count_configs() >= MAX_CONFIGS:
        await message.answer(f"Достигнут лимит ({MAX_CONFIGS} конфигурации). Удалите одну через /del N.")
        return
    await state.clear()
    await state.set_state(AddStates.brand)
    await message.answer("Марка автомобиля (например: BMW, Toyota, Volkswagen):")


@router.message(Command("cancel"), AddStates)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Создание конфигурации отменено.")


# ── Mandatory fields ──────────────────────────────────────────────────────────

@router.message(AddStates.brand)
async def step_brand(message: Message, state: FSMContext) -> None:
    brand = (message.text or "").strip()
    if not brand:
        await message.answer("Введите марку:")
        return
    await state.update_data(brand=brand)
    await state.set_state(AddStates.model)
    await message.answer(
        f"Модель для <b>{brand}</b> (используйте код из URL auto.ru, "
        "например: 3ER для BMW 3 серии, CAMRY для Camry):",
        parse_mode="HTML",
    )


@router.message(AddStates.model)
async def step_model(message: Message, state: FSMContext) -> None:
    model = (message.text or "").strip()
    if not model:
        await message.answer("Введите модель:")
        return
    await state.update_data(model=model)
    await state.set_state(AddStates.year_from)
    await message.answer("Год выпуска ОТ (например: 2018):")


@router.message(AddStates.year_from)
async def step_year_from(message: Message, state: FSMContext) -> None:
    val = (message.text or "").strip()
    if not val.isdigit() or not (2000 <= int(val) <= _CURRENT_YEAR):
        await message.answer(f"Введите корректный год (2000–{_CURRENT_YEAR}):")
        return
    await state.update_data(year_from=int(val))
    await state.set_state(AddStates.year_to)
    await message.answer("Год выпуска ДО:")


@router.message(AddStates.year_to)
async def step_year_to(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    val = (message.text or "").strip()
    if not val.isdigit() or not (data["year_from"] <= int(val) <= _CURRENT_YEAR):
        await message.answer(f"Год ДО должен быть ≥ {data['year_from']} и ≤ {_CURRENT_YEAR}:")
        return
    await state.update_data(year_to=int(val))
    await state.set_state(AddStates.mileage_from)
    await message.answer("Пробег ОТ (км, например: 0):")


@router.message(AddStates.mileage_from)
async def step_mileage_from(message: Message, state: FSMContext) -> None:
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < 0:
        await message.answer("Введите пробег ОТ (целое число ≥ 0):")
        return
    await state.update_data(mileage_from=int(val))
    await state.set_state(AddStates.mileage_to)
    await message.answer("Пробег ДО (км, например: 100000):")


@router.message(AddStates.mileage_to)
async def step_mileage_to(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < data["mileage_from"]:
        await message.answer(f"Пробег ДО должен быть ≥ {data['mileage_from']}:")
        return
    await state.update_data(mileage_to=int(val))
    await state.set_state(AddStates.confirm_optional)
    await message.answer(
        "Обязательные поля заполнены. Добавить опциональные фильтры?\n"
        "(цена, владельцы, коробка, топливо, привод, объём, регион)",
        reply_markup=_yes_no_kb(),
    )


# ── Optional filters gate ─────────────────────────────────────────────────────

@router.callback_query(F.data == "opt_no", AddStates.confirm_optional)
async def opt_skip_all(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_avito_url(callback.message, state)


@router.callback_query(F.data == "opt_yes", AddStates.confirm_optional)
async def opt_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(AddStates.opt_price)
    await callback.message.answer(
        "Цена (введите диапазон через дефис, например: 500000-2000000, или нажмите Пропустить):",
        reply_markup=_skip_kb(),
    )


# ── Optional steps ────────────────────────────────────────────────────────────

async def _next_opt(message: Message, state: FSMContext, next_state: State, prompt: str) -> None:
    await state.set_state(next_state)
    await message.answer(prompt, reply_markup=_skip_kb())


@router.callback_query(F.data == "skip", AddStates.opt_price)
@router.message(AddStates.opt_price)
async def step_opt_price(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text != "/skip":
            parts = text.replace(" ", "").split("-")
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                pf, pt = int(parts[0]), int(parts[1])
                if pf <= pt:
                    data = await state.get_data()
                    opts = data.get("optional_filters", {})
                    opts["price_from"] = pf
                    opts["price_to"] = pt
                    await state.update_data(optional_filters=opts)
            else:
                await msg.answer("Формат: 500000-2000000 или нажмите Пропустить:")
                return

    await _next_opt(msg, state, AddStates.opt_owners, "Максимум владельцев (цифра, например: 2):")


@router.callback_query(F.data == "skip", AddStates.opt_owners)
@router.message(AddStates.opt_owners)
async def step_opt_owners(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text != "/skip" and text.isdigit():
            data = await state.get_data()
            opts = data.get("optional_filters", {})
            opts["owners_count"] = int(text)
            await state.update_data(optional_filters=opts)

    await _next_opt(
        msg, state, AddStates.opt_transmission,
        "Коробка передач (AUTOMATIC / MANUAL / ROBOT / VARIATOR):"
    )


@router.callback_query(F.data == "skip", AddStates.opt_transmission)
@router.message(AddStates.opt_transmission)
async def step_opt_transmission(event, state: FSMContext) -> None:
    _VALID = {"AUTOMATIC", "MANUAL", "ROBOT", "VARIATOR"}
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip().upper()
        if text != "/SKIP":
            if text in _VALID:
                data = await state.get_data()
                opts = data.get("optional_filters", {})
                opts["transmission"] = text
                await state.update_data(optional_filters=opts)
            else:
                await msg.answer(f"Допустимые значения: {', '.join(_VALID)}. Или нажмите Пропустить:")
                return

    await _next_opt(
        msg, state, AddStates.opt_engine_type,
        "Тип топлива (GASOLINE / DIESEL / ELECTRO / HYBRID):"
    )


@router.callback_query(F.data == "skip", AddStates.opt_engine_type)
@router.message(AddStates.opt_engine_type)
async def step_opt_engine_type(event, state: FSMContext) -> None:
    _VALID = {"GASOLINE", "DIESEL", "ELECTRO", "HYBRID"}
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip().upper()
        if text != "/SKIP":
            if text in _VALID:
                data = await state.get_data()
                opts = data.get("optional_filters", {})
                opts["engine_type"] = text
                await state.update_data(optional_filters=opts)
            else:
                await msg.answer(f"Допустимые значения: {', '.join(_VALID)}. Или нажмите Пропустить:")
                return

    await _next_opt(
        msg, state, AddStates.opt_gear_type,
        "Привод (ALL_WHEEL_DRIVE / FORWARD_CONTROL / REAR_DRIVE):"
    )


@router.callback_query(F.data == "skip", AddStates.opt_gear_type)
@router.message(AddStates.opt_gear_type)
async def step_opt_gear_type(event, state: FSMContext) -> None:
    _VALID = {"ALL_WHEEL_DRIVE", "FORWARD_CONTROL", "REAR_DRIVE"}
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip().upper()
        if text != "/SKIP":
            if text in _VALID:
                data = await state.get_data()
                opts = data.get("optional_filters", {})
                opts["gear_type"] = text
                await state.update_data(optional_filters=opts)
            else:
                await msg.answer(f"Допустимые значения: {', '.join(_VALID)}. Или нажмите Пропустить:")
                return

    await _next_opt(
        msg, state, AddStates.opt_displacement,
        "Объём двигателя (л, диапазон через дефис, например: 1.5-2.0):"
    )


@router.callback_query(F.data == "skip", AddStates.opt_displacement)
@router.message(AddStates.opt_displacement)
async def step_opt_displacement(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text != "/skip":
            parts = text.replace(",", ".").split("-")
            try:
                df, dt = float(parts[0]), float(parts[1])
                if df <= dt:
                    data = await state.get_data()
                    opts = data.get("optional_filters", {})
                    opts["displacement_from"] = df
                    opts["displacement_to"] = dt
                    await state.update_data(optional_filters=opts)
                else:
                    raise ValueError
            except (ValueError, IndexError):
                await msg.answer("Формат: 1.5-2.0. Или нажмите Пропустить:")
                return

    await _next_opt(
        msg, state, AddStates.opt_city,
        f"Город поиска (например: {popular_cities_hint()}):"
    )


@router.callback_query(F.data == "skip", AddStates.opt_city)
@router.message(AddStates.opt_city)
async def step_opt_city(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text and text != "/skip":
            data = await state.get_data()
            opts = data.get("optional_filters", {})
            result = resolve_city(text)
            if result is not None:
                geo_id, canonical = result
                opts["geo_id"] = geo_id
                opts["geo_city"] = canonical
                note = f"Город: {canonical} (API-фильтр)\nРадиус поиска (км, например: 100, 200, 500):"
            else:
                # small city — store as text post-filter, skip radius step
                opts["geo_city"] = text
                opts["geo_city_text"] = text
                await state.update_data(optional_filters=opts)
                await msg.answer(
                    f"Город «{text}» не найден в справочнике — "
                    f"будет применён текстовый фильтр по результатам."
                )
                await _ask_avito_url(msg, state)
                return
            await state.update_data(optional_filters=opts)
            await state.set_state(AddStates.opt_radius)
            await msg.answer(note, reply_markup=_skip_kb())
            return

    await _ask_avito_url(msg, state)


@router.callback_query(F.data == "skip", AddStates.opt_radius)
@router.message(AddStates.opt_radius)
async def step_opt_radius(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text and text != "/skip":
            if text.isdigit() and 0 < int(text) <= 1500:
                data = await state.get_data()
                opts = data.get("optional_filters", {})
                opts["geo_radius"] = int(text)
                await state.update_data(optional_filters=opts)
            else:
                await msg.answer("Введите число от 1 до 1500 км. Или нажмите Пропустить:")
                return

    await _ask_avito_url(msg, state)


# ── Avito URL ─────────────────────────────────────────────────────────────────

async def _ask_avito_url(message: Message, state: FSMContext) -> None:
    await state.set_state(AddStates.opt_avito_url)
    await message.answer(
        "🔍 <b>Авито (необязательно)</b>\n\n"
        "Вставьте URL поиска с Авито — или нажмите Пропустить:\n\n"
        "Как получить URL:\n"
        "1. Откройте avito.ru → Транспорт → Автомобили\n"
        "2. Выберите марку, модель, год, пробег, регион\n"
        "3. Скопируйте URL страницы с результатами",
        parse_mode="HTML",
        reply_markup=_skip_kb(),
    )


@router.callback_query(F.data == "skip", AddStates.opt_avito_url)
@router.message(AddStates.opt_avito_url)
async def step_opt_avito_url(event, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        msg = event.message
    else:
        msg = event
        text = (event.text or "").strip()
        if text and text != "/skip":
            if text.startswith("https://www.avito.ru") or text.startswith("http://www.avito.ru"):
                data = await state.get_data()
                opts = data.get("optional_filters", {})
                opts["avito_url"] = text
                await state.update_data(optional_filters=opts)
            else:
                await msg.answer("Должен быть URL вида https://www.avito.ru/... Или нажмите Пропустить:")
                return

    await _save_config(msg, state)


# ── Save ──────────────────────────────────────────────────────────────────────

async def _save_config(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        cfg = await create_config(
            brand=data["brand"],
            model=data["model"],
            year_from=data["year_from"],
            year_to=data["year_to"],
            mileage_from=data["mileage_from"],
            mileage_to=data["mileage_to"],
            optional_filters=data.get("optional_filters", {}),
        )
        opts = cfg.optional_filters
        opt_desc = ""
        if opts:
            items = []
            if "price_from" in opts:
                items.append(f"цена {opts['price_from']:,}–{opts.get('price_to', '∞')} ₽".replace(",", " "))
            if "owners_count" in opts:
                items.append(f"владельцев ≤ {opts['owners_count']}")
            if "transmission" in opts:
                items.append(opts["transmission"])
            if "engine_type" in opts:
                items.append(opts["engine_type"])
            if "gear_type" in opts:
                items.append(opts["gear_type"])
            if "displacement_from" in opts:
                items.append(f"{opts['displacement_from']}–{opts.get('displacement_to', '∞')} л")
            if "geo_city" in opts:
                radius = opts.get("geo_radius")
                city_str = opts["geo_city"]
                if radius:
                    city_str += f" +{radius} км"
                items.append(city_str)
            if "avito_url" in opts:
                items.append("Авито ✅")
            opt_desc = "\nФильтры: " + ", ".join(items)

        await message.answer(
            f"✅ Конфигурация #{cfg.id} сохранена\n"
            f"<b>{cfg.brand} {cfg.model}</b>\n"
            f"Год: {cfg.year_from}–{cfg.year_to}\n"
            f"Пробег: {cfg.mileage_from:,}–{cfg.mileage_to:,} км{opt_desc}".replace(",", " "),
            parse_mode="HTML",
        )
    except ValueError as exc:
        await message.answer(str(exc))
    except Exception as exc:
        log.error("Failed to save config: %s", exc)
        await message.answer("Ошибка при сохранении. Попробуйте /add снова.")
