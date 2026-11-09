
import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "PSP Games"
LINKS_FILE = BASE_DIR / "psp_game_urls.txt"

DOWNLOAD_DIR.mkdir(exist_ok=True)


def load_links():
    if not LINKS_FILE.exists():
        print("Не найден файл links.txt")
        return []

    return [
        line.strip()
        for line in LINKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and line.strip().startswith("http")
    ]


async def main():
    links = load_links()

    if not links:
        print("Список ссылок пуст.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        for index, game_url in enumerate(links, start=1):
            print(f"\n[{index}/{len(links)}] Открываю: {game_url}")

            try:
                await page.goto(
                    game_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await page.wait_for_timeout(2000)

                # Ищем ссылку на скачивание, исключая торрент
                download_links = await page.locator("a").evaluate_all("""
                    elements => elements.map(a => ({
                        text: a.innerText.trim(),
                        href: a.href
                    }))
                """)

                target = next(
                    (
                        item for item in download_links
                        if "скачать" in item["text"].lower()
                        and "торрент" not in item["text"].lower()
                        and "/download/" in item["href"]
                    ),
                    None
                )

                if not target:
                    print("Не найдена ссылка скачивания.")
                    continue

                print(f"Найдена ссылка: {target['href']}")

                async with page.expect_download(timeout=180000) as download_info:
                    await page.goto(
                        target["href"],
                        wait_until="commit",
                        timeout=60000
                    )

                download = await download_info.value

                filename = Path(download.suggested_filename).name
                destination = DOWNLOAD_DIR / filename

                if destination.exists():
                    destination = DOWNLOAD_DIR / f"{index}_{filename}"

                await download.save_as(destination)

                print(f"Успешно: {destination.name}")

            except PlaywrightTimeoutError:
                print("Тайм-аут загрузки. Перехожу к следующей игре.")

            except Exception as error:
                print(f"Ошибка: {error}")

        await browser.close()

    print("\nВсе ссылки обработаны.")


if __name__ == "__main__":
    asyncio.run(main())
