from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

from astanahub_connector.github_login import ACCOUNT_URL, _login

HOME_URL = "https://astanahub.com/ru/"
OUTPUT_PATH = Path("quest-inspection.json")
KEYWORDS = ("квест", "прочитать", "пост", "лайк", "коммент", "quest", "read", "like", "comment")


def scan_page(page: Page) -> dict[str, object]:
    matches = page.locator("a, button, [role='button'], section, article, li, div").evaluate_all(
        r"""(elements, keywords) => {
            const seen = new Set();
            return elements
                .filter((el) => {
                    const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
                    if (!text || text.length > 1200 || el.offsetParent === null) return false;
                    return keywords.some((word) => text.toLowerCase().includes(word));
                })
                .map((el) => {
                    const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
                    const href = el.href || el.closest('a')?.href || '';
                    return {
                        tag: el.tagName.toLowerCase(),
                        text,
                        href,
                        classes: String(el.className || '').slice(0, 300)
                    };
                })
                .sort((a, b) => a.text.length - b.text.length)
                .filter((item) => {
                    const key = item.text + '|' + item.href;
                    if (seen.has(key)) return false;
                    seen.add(key);
                    return true;
                })
                .slice(0, 100);
        }""",
        list(KEYWORDS),
    )
    links = page.locator("a[href]").evaluate_all(
        r"""(anchors, keywords) => anchors
            .map((a) => ({text: (a.innerText || '').replace(/\s+/g, ' ').trim(), href: a.href}))
            .filter((item) => keywords.some((word) =>
                (item.text + ' ' + item.href).toLowerCase().includes(word)
            ))""",
        list(KEYWORDS),
    )
    return {"url": page.url, "title": page.title(), "matches": matches, "links": links}


def main() -> int:
    email = os.environ.get("ASTANAHUB_EMAIL", "").strip()
    password = os.environ.get("ASTANAHUB_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("GitHub Secrets are missing")

    response_urls: set[str] = set()
    pages: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU", timezone_id="Asia/Qyzylorda")
        try:
            page = context.new_page()
            page.on(
                "response",
                lambda response: response_urls.add(response.url)
                if any(word in response.url.lower() for word in KEYWORDS)
                else None,
            )
            _login(page, email, password)

            for url in (ACCOUNT_URL, HOME_URL):
                page.goto(url, wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(3000)
                pages.append(scan_page(page))

            discovered = {
                urljoin(HOME_URL, str(link["href"]))
                for page_data in pages
                for link in page_data["links"]  # type: ignore[index]
                if link.get("href")
            }
            for url in sorted(discovered):
                parsed = urlparse(url)
                if parsed.netloc != "astanahub.com" or url in (ACCOUNT_URL, HOME_URL):
                    continue
                page.goto(url, wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(2500)
                pages.append(scan_page(page))

            result = {"pages": pages, "response_urls": sorted(response_urls)}
            OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Quest inspection saved: {len(pages)} pages")
            return 0
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
