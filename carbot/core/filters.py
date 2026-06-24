from carbot.scrapers.base import Listing
from carbot.storage.configs import Config

_COLOR_MAP = {
    "белый": "FAFAF0",
    "чёрный": "040001",
    "черный": "040001",
    "серый": "97948F",
    "серебристый": "C0C0C0",
    "синий": "0000CC",
    "красный": "EE1D19",
    "зелёный": "007F00",
    "зеленый": "007F00",
    "коричневый": "4A2197",
    "золотой": "FFD600",
    "оранжевый": "FF8649",
    "пурпурный": "200204",
    "фиолетовый": "8A00D3",
    "бежевый": "DEA522",
    "желтый": "FFE400",
    "жёлтый": "FFE400",
}


def apply_optional_filters(listings: list[Listing], config: Config) -> list[Listing]:
    opts = config.optional_filters
    if not opts:
        return listings

    result = []
    for lst in listings:
        if "price_from" in opts and lst.price is not None and lst.price < opts["price_from"]:
            continue
        if "price_to" in opts and lst.price is not None and lst.price > opts["price_to"]:
            continue
        if "owners_count" in opts and lst.owners_count is not None and lst.owners_count > opts["owners_count"]:
            continue
        if "displacement_from" in opts and lst.displacement is not None and lst.displacement < opts["displacement_from"]:
            continue
        if "displacement_to" in opts and lst.displacement is not None and lst.displacement > opts["displacement_to"]:
            continue
        if "geo_city_text" in opts and lst.location is not None:
            if opts["geo_city_text"].lower() not in lst.location.lower():
                continue
        if "color" in opts and lst.color is not None:
            expected = _COLOR_MAP.get(opts["color"].lower(), opts["color"].upper())
            if expected.upper() not in lst.color.upper():
                continue
        result.append(lst)
    return result
