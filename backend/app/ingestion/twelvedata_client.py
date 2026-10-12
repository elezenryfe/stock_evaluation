import time
from functools import lru_cache

import httpx

from app.core.config import settings

TD_BASE = "https://api.twelvedata.com"
TD_DEMO_KEY = "demo"


class TwelveDataClient:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or settings.twelvedata_api_key or TD_DEMO_KEY
        self.client = httpx.Client(timeout=30)
        self._rate_limited = False

    def is_rate_limited(self) -> bool:
        return self._rate_limited

    def _get(self, endpoint: str, **params) -> dict:
        params["apikey"] = self.api_key
        self._rate_limited = False
        for attempt in range(3):
            try:
                resp = self.client.get(f"{TD_BASE}/{endpoint}", params=params)
                if resp.status_code == 429:
                    self._rate_limited = True
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                    continue
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 429:
                        self._rate_limited = True
                        if attempt < 2:
                            time.sleep(5 * (attempt + 1))
                        continue
                    return data
                return {}
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        self._rate_limited = True
        return {}

    def get_quote(self, ticker: str) -> dict:
        return self._get("quote", symbol=ticker)

    def get_statistics(self, ticker: str) -> dict:
        return self._get("statistics", symbol=ticker)

    def get_time_series(self, ticker: str, interval: str = "1day", outputsize: int = 5000) -> dict:
        return self._get("time_series", symbol=ticker, interval=interval, outputsize=outputsize)

    def validate_ticker(self, ticker: str) -> dict | None:
        quote = self.get_quote(ticker)
        if not quote or not quote.get("symbol"):
            return None
        return {
            "ticker": quote.get("symbol", ticker).upper(),
            "company_name": quote.get("name", ""),
            "exchange": quote.get("exchange"),
            "sector": None,
            "industry": None,
            "cik": None,
            "fiscal_year_end": None,
        }

    def get_stock_info(self, ticker: str) -> dict:
        quote = self.get_quote(ticker)
        stats = self.get_statistics(ticker)

        valuations = stats.get("statistics", {}).get("valuations_metrics", {})
        financials = stats.get("statistics", {}).get("financials", {})
        income = financials.get("income_statement", {})

        return {
            "current_price": _float(quote.get("close")),
            "eps_ttm": _float(income.get("diluted_eps_ttm")),
            "forward_eps": _float(valuations.get("forward_pe_diluted_eps_ttm")),
            "pe_ttm": _float(valuations.get("trailing_pe")),
            "forward_pe": _float(valuations.get("forward_pe")),
            "revenue_ttm": _float(income.get("revenue_ttm")),
            "market_cap": _float(valuations.get("market_capitalization")),
            "company_name": quote.get("name", ""),
            "sector": None,
            "industry": None,
            "analyst_target_price": _float(quote.get("fifty_two_week", {}).get("high")),
            "recommendation": None,
        }


def _float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@lru_cache(maxsize=1)
def get_twelvedata_client() -> TwelveDataClient:
    return TwelveDataClient()
