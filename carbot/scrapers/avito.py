"""
Avito scraper — Playwright Chromium, best-effort behind AVITO_ENABLED=true.

Selectors discovered 2026-06-24 via tools/avito_discovery.py:
  Card     : [data-marker='item']        data-item-id = listing ID
  Title    : [data-marker='item-title']  text = "Brand Trans, Year, Mileage km"
                                         href = relative URL
  Price    : [itemprop='price']          content = integer string
  Params   : [data-marker='item-specific-params']
             text = "N km, Vol TRANS (hp), body, drive, engine"
  Location : [data-marker='item-location']
  Photo    : first <img> src (absolute URL)
  Next page: [data-marker='pagination-button/next']

Search URL is stored per-config in optional_filters['avito_url'].
User constructs it manually on avito.ru and pastes it during /add.
Cards are server-side rendered — domcontentloaded is sufficient.
"""

import asyncio
import logging
import random
import re
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from carbot.scrapers.base import Listing, Scraper
from carbot.storage.configs import Config

log = logging.getLogger(__name__)

_BASE_URL = "https://www.avito.ru"

_TRANS_MAP = {
    "AMT": "ROBOT", "РОБОТ": "ROBOT",
    "AT": "AUTOMATIC", "АВТОМАТ": "AUTOMATIC",
    "MT": "MANUAL", "МЕХАНИКА": "MANUAL",
    "CVT": "VARIATOR", "ВАРИАТОР": "VARIATOR",
}
_ENGINE_MAP = {
    "бензин": "GASOLINE",
    "дизель": "DIESEL",
    "гибрид": "HYBRID",
    "электро": "ELECTRO",
}
_GEAR_MAP = {
    "полный": "ALL_WHEEL_DRIVE",
    "передний": "FORWARD_CONTROL",
    "задний": "REAR_DRIVE",
}

_EXTRACT_JS = """
() => Array.from(document.querySelectorAll('[data-marker="item"]')).map(card => {
    const t = card.querySelector('[data-marker="item-title"]');
    const p = card.querySelector('[itemprop="price"]');
    const s = card.querySelector('[data-marker="item-specific-params"]');
    const l = card.querySelector('[data-marker="item-location"]');
    const img = card.querySelector('img');
    return {
        id: card.getAttribute('data-item-id'),
        title: t ? t.innerText.trim() : '',
        href: t ? t.getAttribute('href') : '',
        price: p ? p.getAttribute('content') : null,
        params: s ? s.innerText.trim() : '',
        location: l ? l.innerText.trim() : '',
        photo: img ? img.getAttribute('src') : null,
    };
})
"""

_HAS_NEXT_JS = """
() => !!document.querySelector('[data-marker="pagination-button/next"]')
"""

_STEALTH_JS = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Fake Chrome runtime (absent in headless)
if (!window.chrome) window.chrome = {};
if (!window.chrome.runtime) window.chrome.runtime = {};

// Realistic plugin list
const pluginData = [
    {name: 'Chrome PDF Plugin',   filename: 'internal-pdf-viewer',                description: 'Portable Document Format'},
    {name: 'Chrome PDF Viewer',   filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',  description: ''},
    {name: 'Native Client',       filename: 'internal-nacl-plugin',               description: ''},
];
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const arr = pluginData.map(p => {
            const plugin = Object.create(Plugin.prototype);
            Object.defineProperty(plugin, 'name',        {get: () => p.name});
            Object.defineProperty(plugin, 'filename',    {get: () => p.filename});
            Object.defineProperty(plugin, 'description', {get: () => p.description});
            return plugin;
        });
        arr.__proto__ = PluginArray.prototype;
        return arr;
    }
});

// Languages
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});

// Permissions
const _origPermQuery = window.navigator.permissions.query.bind(navigator.permissions);
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : _origPermQuery(params);

// Hide headless in user-agent hints (if supported)
if (navigator.userAgentData) {
    Object.defineProperty(navigator.userAgentData, 'mobile', {get: () => false});
}
"""


class AvitoBlockedError(Exception):
    pass


class AvitoScraper(Scraper):
    source = "avito"

    def __init__(
        self,
        proxy_url: Optional[str],
        action_delay: tuple[float, float],
        max_pages: int,
    ):
        self._proxy_url = proxy_url
        self._delay_min, self._delay_max = action_delay
        self._max_pages = max_pages
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        launch_args: dict = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        if self._proxy_url:
            launch_args["proxy"] = {"server": self._proxy_url}
        self._browser = await self._playwright.chromium.launch(**launch_args)
        log.info("Avito browser started")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def search(self, config: Config) -> list[Listing]:
        if not self._browser:
            raise RuntimeError("AvitoScraper.start() not called")

        base_url = config.optional_filters.get("avito_url")
        if not base_url:
            log.debug("Avito: no avito_url in config #%d, skipping", config.id)
            return []

        listings: list[Listing] = []
        context: Optional[BrowserContext] = None
        try:
            context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
                viewport={"width": 1280, "height": 800},
                extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9"},
            )
            await context.add_init_script(_STEALTH_JS)
            page = await context.new_page()

            for pg in range(1, self._max_pages + 1):
                url = _paginate(base_url, pg)
                log.debug("Avito: page %d → %s", pg, url[:100])

                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await self._human_delay(page)

                if await self._is_blocked(page):
                    raise AvitoBlockedError("Captcha/block detected")

                # Wait up to 8 s for cards to appear (React hydration)
                try:
                    await page.wait_for_selector('[data-marker="item"]', timeout=8_000)
                except Exception:
                    title = await page.title()
                    log.warning(
                        "Avito page %d: no cards after wait. title=%r url=%s",
                        pg, title, page.url,
                    )

                cards_raw: list[dict] = await page.evaluate(_EXTRACT_JS)
                log.debug("Avito page %d: %d cards", pg, len(cards_raw))

                if not cards_raw:
                    break

                for raw in cards_raw:
                    lst = self._parse_card(raw)
                    if lst:
                        listings.append(lst)

                has_next: bool = await page.evaluate(_HAS_NEXT_JS)
                if not has_next:
                    break

                if pg < self._max_pages:
                    await asyncio.sleep(random.uniform(self._delay_min, self._delay_max))

        except AvitoBlockedError:
            raise
        except Exception as exc:
            log.error("Avito search failed: %s", exc)
            raise
        finally:
            if context:
                await context.close()

        return listings

    async def _is_blocked(self, page: Page) -> bool:
        title = (await page.title()).lower()
        url = page.url
        return (
            "captcha" in title
            or "robot" in title
            or "/blocked" in url
            or "/captcha" in url
        )

    async def _human_delay(self, page: Page) -> None:
        delay = random.uniform(self._delay_min, self._delay_max)
        await asyncio.sleep(delay)
        scroll_y = random.randint(300, 700)
        await page.evaluate(f"window.scrollBy(0, {scroll_y})")
        await asyncio.sleep(random.uniform(0.5, 1.2))

    def _parse_card(self, raw: dict) -> Optional[Listing]:
        try:
            listing_id = raw.get("id") or ""
            if not listing_id:
                return None

            title = raw.get("title", "")
            href = raw.get("href", "")
            url = f"{_BASE_URL}{href}" if href and href.startswith("/") else href or ""

            price_raw = raw.get("price")
            price = int(float(price_raw)) if price_raw else None

            year = _parse_year(title)

            params = raw.get("params", "")
            parsed = _parse_params(params)

            location = raw.get("location") or None
            photo_url = raw.get("photo") or None

            return Listing(
                source="avito",
                listing_id=listing_id,
                title=title,
                price=price,
                year=year,
                mileage=parsed.get("mileage"),
                url=url,
                transmission=parsed.get("transmission"),
                engine_type=parsed.get("engine_type"),
                displacement=parsed.get("displacement"),
                gear_type=parsed.get("gear_type"),
                location=location,
                photo_url=photo_url,
            )
        except Exception as exc:
            log.warning("Avito: failed to parse card %s: %s", raw.get("id"), exc)
            return None


# ── helpers ───────────────────────────────────────────────────────────────────

def _paginate(base_url: str, page: int) -> str:
    clean = re.sub(r"[&?]p=\d+", "", base_url)
    if page <= 1:
        return clean
    sep = "&" if "?" in clean else "?"
    return f"{clean}{sep}p={page}"


def _parse_year(title: str) -> Optional[int]:
    m = re.search(r",\s*(20\d{2})\s*,", title)
    return int(m.group(1)) if m else None


def _parse_params(params: str) -> dict:
    """Parse '108 000 км, 2.0 AMT (190 л.с.), внедорожник, полный, дизель'"""
    result: dict = {}

    m = re.search(r"([\d\s\xa0]+)\s*км", params)
    if m:
        result["mileage"] = int(re.sub(r"[\s\xa0]", "", m.group(1)))

    m = re.search(r"(\d+[.,]\d+)\s+(\w+)\s*\(", params)
    if m:
        result["displacement"] = float(m.group(1).replace(",", "."))
        trans_key = m.group(2).upper()
        trans = _TRANS_MAP.get(trans_key)
        if trans:
            result["transmission"] = trans

    params_lower = params.lower()
    for ru, code in _ENGINE_MAP.items():
        if ru in params_lower:
            result["engine_type"] = code
            break

    for ru, code in _GEAR_MAP.items():
        if ru in params_lower:
            result["gear_type"] = code
            break

    return result
