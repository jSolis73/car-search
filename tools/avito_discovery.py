"""
Avito discovery — финальная фаза: извлекает структуру карточки объявления.

Запуск:
    python tools/avito_discovery.py "https://www.avito.ru/..."
"""

import asyncio
import json
import sys
from pathlib import Path


async def main(url: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = await browser.new_context(
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print(f"Открываю: {url}")
        await page.goto(url, wait_until="load", timeout=60_000)
        await asyncio.sleep(10)

        out_dir = Path("tests/fixtures")
        out_dir.mkdir(parents=True, exist_ok=True)

        # Извлекаем полную структуру первых 3 карточек
        cards_data = await page.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[data-marker="item"]')).slice(0, 3);
                return cards.map(card => {
                    // Все data-marker внутри карточки
                    const markers = {};
                    card.querySelectorAll('[data-marker]').forEach(el => {
                        const m = el.getAttribute('data-marker');
                        markers[m] = {
                            tag: el.tagName,
                            text: el.innerText?.trim().slice(0, 150),
                            href: el.getAttribute('href'),
                            src: el.getAttribute('src'),
                            content: el.getAttribute('content'),
                            attrs: Array.from(el.attributes).reduce((a, x) => {
                                a[x.name] = x.value.slice(0, 100);
                                return a;
                            }, {}),
                        };
                    });

                    // Schema.org microdata
                    const microdata = {};
                    card.querySelectorAll('[itemprop]').forEach(el => {
                        const prop = el.getAttribute('itemprop');
                        microdata[prop] = el.getAttribute('content') || el.innerText?.trim().slice(0, 100);
                    });

                    // Фото
                    const imgs = Array.from(card.querySelectorAll('img')).map(img => ({
                        src: img.getAttribute('src'),
                        srcset: img.getAttribute('srcset')?.slice(0, 200),
                        alt: img.getAttribute('alt'),
                    }));

                    return {
                        listing_id: card.getAttribute('data-item-id'),
                        markers,
                        microdata,
                        imgs: imgs.slice(0, 3),
                        full_text: card.innerText?.trim().slice(0, 500),
                    };
                });
            }
        """)

        # Сохраняем полную структуру
        path = out_dir / "avito_card_structure.json"
        path.write_text(json.dumps(cards_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Сохранено: {path}\n")

        # Выводим анализ
        for i, card in enumerate(cards_data):
            print(f"=== Карточка #{i+1} (id={card['listing_id']}) ===")
            print(f"Полный текст: {repr(card['full_text'][:200])}\n")

            print("data-marker элементы:")
            for marker, data in card["markers"].items():
                info = f"<{data['tag']}>"
                if data.get("href"):
                    info += f" href={data['href'][:80]}"
                if data.get("text"):
                    info += f" text={repr(data['text'][:80])}"
                if data.get("content"):
                    info += f" content={data['content'][:40]}"
                print(f"  [{marker}] {info}")

            print("\nSchema.org microdata:")
            for prop, val in card["microdata"].items():
                print(f"  {prop}: {val}")

            print("\nФото:")
            for img in card["imgs"]:
                print(f"  src={img['src']}")
                if img.get("srcset"):
                    print(f"  srcset={img['srcset'][:100]}")
            print()

        # Также проверяем пагинацию
        pagination = await page.evaluate("""
            () => {
                const next = document.querySelector('[data-marker="pagination-button/next"]');
                const pages = Array.from(document.querySelectorAll('[data-marker^="pagination-button"]'))
                    .map(el => ({marker: el.getAttribute('data-marker'), href: el.getAttribute('href'), text: el.innerText}));
                return {next_href: next?.getAttribute('href'), pages};
            }
        """)
        print("Пагинация:")
        print(f"  next: {pagination['next_href']}")
        for p_btn in pagination["pages"][:5]:
            print(f"  {p_btn['marker']}: href={p_btn['href']} text={p_btn['text']}")

        await browser.close()
        print("\nГотово.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python tools/avito_discovery.py <URL>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
