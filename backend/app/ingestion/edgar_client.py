import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx

SEC_BASE_URL = "https://data.sec.gov"
SEC_SEARCH_URL = "https://efts.sec.gov"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data"

SEC_HEADERS = {
    "User-Agent": "StockGuidanceBot/1.0 (contact@stockguidance.app)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}


class TokenBucket:
    def __init__(self, rate: float, capacity: int = 10):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    async def acquire(self):
        while True:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            await asyncio.sleep(0.1)


_cik_cache: dict[str, str] = {}


async def resolve_cik(ticker: str) -> str | None:
    ticker_upper = ticker.upper()
    if ticker_upper in _cik_cache:
        return _cik_cache[ticker_upper]

    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": SEC_HEADERS["User-Agent"], "Host": "www.sec.gov"})
            if resp.status_code == 200:
                data = resp.json()
                for entry in data.values():
                    tkr = entry.get("ticker", "").upper()
                    cik = str(entry.get("cik_str", ""))
                    _cik_cache[tkr] = cik
    except Exception:
        pass

    return _cik_cache.get(ticker_upper)


class EDGARClient:
    def __init__(self):
        self.client = httpx.AsyncClient(headers=SEC_HEADERS, timeout=30.0)
        self.rate_limiter = TokenBucket(rate=10, capacity=10)

    async def close(self):
        await self.client.aclose()

    async def _get(self, url: str, headers: dict | None = None) -> httpx.Response:
        await self.rate_limiter.acquire()
        return await self.client.get(url, headers=headers)

    async def get_company_submissions(self, cik: str) -> dict:
        cik_padded = cik.zfill(10)
        url = f"{SEC_BASE_URL}/submissions/CIK{cik_padded}.json"
        resp = await self._get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_company_facts(self, cik: str) -> dict:
        cik_padded = cik.zfill(10)
        url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        resp = await self._get(url)
        resp.raise_for_status()
        return resp.json()

    async def get_eps_history(self, cik: str) -> list[dict]:
        facts = await self.get_company_facts(cik)
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        eps_data = us_gaap.get("EarningsPerShareDiluted", {})
        units = eps_data.get("units", {}).get("USD-per-shares", [])
        return [
            {"date": item["end"], "eps": item["val"], "form": item.get("form", "")}
            for item in units
            if item.get("form") in ("10-K", "10-Q")
        ]

    async def search_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        days_back: int = 90,
        max_results: int = 10,
    ) -> list[dict]:
        if form_types is None:
            form_types = ["8-K", "10-Q"]
        start_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        forms_param = ",".join(form_types)
        url = (
            f"{SEC_SEARCH_URL}/LATEST/search-index"
            f"?q=%22{ticker}%22&forms={forms_param}"
            f"&dateRange=custom&startdt={start_date}"
            f"&from=0&size={max_results}"
        )
        resp = await self._get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        results = []
        for h in hits:
            source = h.get("_source", {})
            display_name = source.get("display_names", {})
            results.append({
                "accession_number": source.get("id", ""),
                "filing_type": source.get("file_type", ""),
                "form": source.get("file_type", ""),
                "company_name": display_name.get("entity_name") or source.get("entity_name", ""),
                "filing_date": source.get("file_date", ""),
                "cik": str(source.get("cik", "")),
            })
        return results

    async def get_filing_text(self, cik: str, accession_number: str) -> str | None:
        cik_stripped = cik.lstrip("0")
        acc_formatted = accession_number.replace("-", "")
        url = f"{SEC_ARCHIVE_URL}/{cik_stripped}/{acc_formatted}/{accession_number}.txt"
        try:
            resp = await self._get(url, headers={"Host": "www.sec.gov"})
            if resp.status_code != 200:
                return None
            return _extract_text_from_filing(resp.text)
        except Exception:
            return None

    def get_filing_page_url(self, accession_number: str) -> str:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={accession_number}&type=8-K&dateb=&owner=include&count=10"


def _extract_text_from_filing(raw: str) -> str:
    import re
    from bs4 import BeautifulSoup

    # SEC filings are multi-document: find the EX-99 exhibit (earnings press release).
    # Pattern: <DOCUMENT> ... <TYPE>EX-99 ... </DOCUMENT>
    doc_pattern = re.compile(
        r"<DOCUMENT>\s*<TYPE>([^\n<]+).*?</DOCUMENT>",
        re.DOTALL | re.IGNORECASE,
    )
    exhibits = []
    for match in doc_pattern.finditer(raw):
        doc_type = match.group(1).strip().upper()
        doc_body = match.group(0)
        if doc_type.startswith("EX-99"):
            exhibits.append(doc_body)

    # Use the EX-99 content if found, otherwise use the full filing.
    if exhibits:
        content = "\n".join(exhibits)
    else:
        content = raw

    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = "\n".join(lines)

    if len(result) < 200 and exhibits:
        soup2 = BeautifulSoup(raw, "lxml")
        for tag in soup2(["script", "style"]):
            tag.decompose()
        result = "\n".join(
            line.strip()
            for line in soup2.get_text(separator="\n").splitlines()
            if line.strip()
        )

    return result


_edgar_client: EDGARClient | None = None


async def get_edgar_client() -> EDGARClient:
    global _edgar_client
    if _edgar_client is None:
        _edgar_client = EDGARClient()
    return _edgar_client
