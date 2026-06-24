"""
auto.ru scraper — HTTP + curl_cffi (browser TLS impersonation).

Empirical discovery notes (T4.3):
  Endpoint : POST https://auto.ru/-/ajax/desktop/listing/
  Session  : GET https://auto.ru/ first (sets cookies incl. _csrf_token)
  CSRF     : cookie '_csrf_token' → header 'x-csrf-token'
  Brand    : uppercase string as-is (e.g. "BMW", "TOYOTA", "VOLKSWAGEN")
  Model    : auto.ru internal code (e.g. BMW "3 серии" → "3ER"); user must use
             the code that appears in auto.ru URLs.  Save a response fixture in
             tests/fixtures/autoru_response.json after first successful run.
"""

import asyncio
import logging
import random
from typing import Optional

from curl_cffi.requests import AsyncSession

from carbot.scrapers.base import Listing, Scraper
from carbot.storage.configs import Config

log = logging.getLogger(__name__)

_BASE_URL = "https://auto.ru"
_SEARCH_URL = "https://auto.ru/-/ajax/desktop/listing/"
_IMPERSONATE = "chrome110"

_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Origin": "https://auto.ru",
    "Referer": "https://auto.ru/cars/used/",
    "Sec-Ch-Ua": '"Chromium";v="110", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class AutoRuScraper(Scraper):
    source = "autoru"

    def __init__(self, proxy_url: Optional[str], http_delay: tuple[float, float], max_pages: int, max_listing_age_days: int = 7):
        self._proxy_url = proxy_url
        self._delay_min, self._delay_max = http_delay
        self._max_pages = max_pages
        self._max_listing_age_days = max_listing_age_days
        self._proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    async def search(self, config: Config) -> list[Listing]:
        listings: list[Listing] = []
        try:
            async with AsyncSession(impersonate=_IMPERSONATE) as session:
                await self._init_session(session)
                csrf = session.cookies.get("_csrf_token") or ""

                for page in range(1, self._max_pages + 1):
                    body = self._build_body(config, page)
                    headers = {**_HEADERS, "x-csrf-token": csrf}

                    resp = await session.post(
                        _SEARCH_URL,
                        json=body,
                        headers=headers,
                        proxies=self._proxies,
                        timeout=30,
                    )
                    if resp.status_code != 200:
                        log.warning("auto.ru returned %s on page %d", resp.status_code, page)
                        break

                    data = resp.json()
                    offers = data.get("offers", [])
                    log.debug("auto.ru page %d: %d offers", page, len(offers))

                    if not offers:
                        break

                    for offer in offers:
                        lst = self._parse_offer(offer)
                        if lst:
                            listings.append(lst)

                    if page < self._max_pages:
                        await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))

        except Exception as exc:
            log.error("auto.ru search failed: %s", exc)
            raise

        return listings

    async def _init_session(self, session: AsyncSession) -> None:
        await session.get(
            f"{_BASE_URL}/cars/used/",
            proxies=self._proxies,
            timeout=30,
        )
        await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))

    def _build_body(self, config: Config, page: int) -> dict:
        opts = config.optional_filters
        body: dict = {
            "catalog_filter": [{"mark": config.brand.upper(), "model": config.model.upper()}],
            "section": "used",
            "category": "cars",
            "sort": "fresh_relevance_1-desc",
            "page": page,
            "page_size": 20,
            "year_from": config.year_from,
            "year_to": config.year_to,
            "km_age_from": config.mileage_from,
            "km_age_to": config.mileage_to,
        }
        if "price_from" in opts:
            body["price_from"] = opts["price_from"]
        if "price_to" in opts:
            body["price_to"] = opts["price_to"]
        if "transmission" in opts:
            body["transmission"] = [opts["transmission"]]
        if "engine_type" in opts:
            body["engine_type"] = [opts["engine_type"]]
        if "gear_type" in opts:
            body["gear_type"] = [opts["gear_type"]]
        if "geo_id" in opts:
            body["geo_id"] = [opts["geo_id"]]
            if "geo_radius" in opts:
                body["geo_radius"] = opts["geo_radius"]
        return body

    def _parse_offer(self, offer: dict) -> Optional[Listing]:
        try:
            listing_id = offer.get("id", "")
            if not listing_id:
                return None

            price_info = offer.get("price_info", {})
            price = price_info.get("price")

            vehicle = offer.get("vehicle_info", {})
            tech = vehicle.get("tech_param", {})
            docs = offer.get("documents", {})
            year = tech.get("year") or vehicle.get("configuration", {}).get("year") or docs.get("year")

            add_info = offer.get("additional_info", {})
            days_on_sale = add_info.get("days_on_sale")
            if days_on_sale is not None and days_on_sale > self._max_listing_age_days:
                return None

            displacement_cc = tech.get("displacement")
            displacement = round(displacement_cc / 1000, 1) if displacement_cc else None

            state = offer.get("state", {})
            mileage = state.get("mileage")

            owners_count = docs.get("owners_number")

            mark_name = vehicle.get("mark_info", {}).get("name", "")
            model_name = vehicle.get("model_info", {}).get("name", "")
            tech_name = tech.get("human_name", "")
            title = f"{mark_name} {model_name} {tech_name}".strip()

            color_hex = offer.get("color_hex", "")
            location = offer.get("seller", {}).get("location", {}).get("region_info", {}).get("name")

            url = offer.get("url", "") or f"https://auto.ru/cars/used/sale/{listing_id}/"

            photo_url: Optional[str] = None
            image_urls = state.get("image_urls", [])
            if image_urls:
                sizes = image_urls[0].get("sizes", {})
                raw = (
                    sizes.get("1200x900n")
                    or sizes.get("1200x900")
                    or sizes.get("832x624n")
                    or sizes.get("456x342n")
                    or sizes.get("small")
                )
                if raw:
                    photo_url = raw if raw.startswith("http") else f"https:{raw}"

            return Listing(
                source="autoru",
                listing_id=str(listing_id),
                title=title,
                price=int(price) if price else None,
                year=year,
                mileage=mileage,
                url=url,
                transmission=tech.get("transmission"),
                engine_type=tech.get("engine_type"),
                displacement=displacement,
                color=color_hex,
                owners_count=owners_count,
                gear_type=tech.get("gear_type"),
                location=location,
                photo_url=photo_url,
            )
        except Exception as exc:
            log.warning("Failed to parse offer %s: %s", offer.get("id"), exc)
            return None
