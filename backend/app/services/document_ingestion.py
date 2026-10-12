import logging
from datetime import date

from app.ingestion.edgar_client import EDGARClient
from app.ingestion.scraper import SmartScraper, search_guidance_news
from app.services.content_filter import content_quality_check, compute_checksum

logger = logging.getLogger(__name__)


async def discover_documents(
    ticker: str,
    company_name: str,
    cik: str | None,
    edgar: EDGARClient,
    scraper: SmartScraper,
    days_back: int = 180,
) -> list[dict]:
    documents: list[dict] = []
    seen_checksums: set[str] = set()

    if cik:
        edgar_docs = await _fetch_edgar_filings(edgar, ticker, cik, days_back)
        for doc in edgar_docs:
            if doc["checksum"] and doc["checksum"] not in seen_checksums:
                seen_checksums.add(doc["checksum"])
                documents.append(doc)

    news_docs = await _fetch_news_articles(scraper, ticker, company_name)
    for doc in news_docs:
        if doc["checksum"] and doc["checksum"] not in seen_checksums:
            seen_checksums.add(doc["checksum"])
            documents.append(doc)

    documents.sort(key=lambda d: _source_priority(d["source_type"]))
    return documents


def _source_priority(source_type: str) -> int:
    priorities = {
        "SEC_8K": 0,
        "SEC_10Q": 1,
        "SEC_10K": 2,
        "press_release": 3,
        "news_article": 4,
    }
    return priorities.get(source_type, 5)


async def _fetch_edgar_filings(
    edgar: EDGARClient,
    ticker: str,
    cik: str,
    days_back: int,
) -> list[dict]:
    documents: list[dict] = []
    try:
        subs = await edgar.get_company_submissions(cik)
        filings = subs.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

        from datetime import datetime, timedelta
        cutoff = datetime.today() - timedelta(days=days_back)

        max_docs = 2
        for i in range(min(len(forms), 50)):
            if len(documents) >= max_docs:
                break
            if forms[i] not in ("8-K", "10-Q"):
                continue
            filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
            if filing_date < cutoff:
                continue
            accession = accessions[i]
            text = await edgar.get_filing_text(cik, accession)
            if not text:
                continue

            # Skip filings without guidance content (EX-99 exhibits contain earnings releases)
            has_ex99 = "ex-99" in text.lower()[:2000] or "EX-99" in text[:2000]
            if forms[i] == "8-K" and not has_ex99:
                continue
            if not text:
                continue

            quality = content_quality_check(text)
            if not quality["passed"]:
                continue

            documents.append({
                "source_url": f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession.replace('-', '')}/{accession}.txt",
                "source_type": f"SEC_{forms[i].replace('-', '')}",
                "document_title": f"{ticker} {forms[i]} Filing ({dates[i]})",
                "document_date": date.fromisoformat(dates[i]),
                "raw_text": text,
                "word_count": quality["word_count"],
                "fetch_status": "success",
                "checksum": quality["checksum"],
            })
    except Exception as e:
        logger.warning(f"EDGAR fetch failed for {ticker}: {e}")

    return documents


async def _fetch_news_articles(
    scraper: SmartScraper,
    ticker: str,
    company_name: str,
) -> list[dict]:
    documents: list[dict] = []
    entries = await search_guidance_news(ticker, company_name)
    for entry in entries[:5]:
        try:
            content = await scraper.scrape(entry["link"])
            if not content:
                continue
            quality = content_quality_check(content.text)
            if not quality["passed"]:
                continue
            documents.append({
                "source_url": entry["link"],
                "source_type": "news_article",
                "document_title": entry["title"],
                "document_date": date.today(),
                "raw_text": content.text,
                "word_count": quality["word_count"],
                "fetch_status": "success",
                "checksum": quality["checksum"],
            })
        except Exception:
            continue
    return documents
