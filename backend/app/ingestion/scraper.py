import asyncio
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

STATIC_DOMAINS = [
    "sec.gov", "edgar.sec.gov", "reuters.com",
    "businesswire.com", "prnewswire.com",
]
JS_DOMAINS = [
    "seekingalpha.com", "fool.com",
]
BOT_USER_AGENT = "StockGuidanceBot/1.0 (contact@stockguidance.app)"


@dataclass
class ScrapedContent:
    url: str
    text: str
    method: str  # "httpx" or "playwright"
    word_count: int


class DomainRateLimiter:
    DOMAIN_LIMITS: dict[str, tuple[float, float]] = {
        "sec.gov": (10, 1.0),
        "reuters.com": (2, 1.0),
        "seekingalpha.com": (1, 2.0),
    }

    def __init__(self):
        self._last_request: dict[str, float] = {}

    async def acquire(self, domain: str):
        rate, period = self.DOMAIN_LIMITS.get(domain, (2, 1.0))
        now = time.monotonic()
        if domain in self._last_request:
            elapsed = now - self._last_request[domain]
            min_wait = period / rate
            if elapsed < min_wait:
                await asyncio.sleep(min_wait - elapsed)
        self._last_request[domain] = time.monotonic()


class SmartScraper:
    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": BOT_USER_AGENT},
        )
        self.rate_limiter = DomainRateLimiter()

    async def close(self):
        await self.http_client.aclose()

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.replace("www.", "")

    async def scrape(self, url: str) -> ScrapedContent | None:
        domain = self._domain(url)

        if any(d in domain for d in STATIC_DOMAINS):
            return await self._httpx_scrape(url)

        if any(d in domain for d in JS_DOMAINS):
            return await self._playwright_scrape(url)

        try:
            result = await self._httpx_scrape(url)
            if result and result.word_count < 100:
                return await self._playwright_scrape(url)
            return result
        except Exception:
            return await self._playwright_scrape(url)

    async def _httpx_scrape(self, url: str) -> ScrapedContent | None:
        domain = self._domain(url)
        for attempt in range(3):
            try:
                await self.rate_limiter.acquire(domain)
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    text = _html_to_text(response.text)
                    return ScrapedContent(
                        url=url, text=text, method="httpx",
                        word_count=len(text.split()),
                    )
                elif response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
            except httpx.TimeoutException:
                await asyncio.sleep(1)
        return None

    async def _playwright_scrape(self, url: str) -> ScrapedContent | None:
        text = await _playwright_fetch(url)
        if text is None:
            return None
        return ScrapedContent(
            url=url, text=text, method="playwright",
            word_count=len(text.split()),
        )


async def _playwright_fetch(url: str) -> str | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            await page.route("**/*.{png,jpg,gif,svg,woff,woff2}", lambda r: r.abort())
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()
            return _html_to_text(html)
    except Exception:
        return None


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    body = soup.find("body")
    if body is None:
        return soup.get_text(separator="\n")
    text = body.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


async def search_guidance_news(ticker: str, company_name: str) -> list[dict]:
    import feedparser
    query = f"{company_name} earnings guidance EPS revenue forecast"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        return [
            {"title": e.title, "link": e.link, "published": e.get("published", "")}
            for e in feed.entries[:10]
        ]
    except Exception:
        return []
