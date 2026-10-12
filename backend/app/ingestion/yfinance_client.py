import time
from functools import lru_cache

import yfinance as yf
import pandas as pd


class YFinanceClient:

    def __init__(self):
        self._rate_limited = False
        self._last_error = ""

    def is_rate_limited(self) -> bool:
        return self._rate_limited

    def _get_info_with_retry(self, ticker: str, max_retries: int = 3) -> dict:
        stock = yf.Ticker(ticker)
        self._rate_limited = False
        for attempt in range(max_retries):
            try:
                info = stock.info
                if info:
                    return info
            except Exception as e:
                err = str(e)
                if "429" in err or "Too Many Requests" in err:
                    self._rate_limited = True
                    self._last_error = err
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        self._rate_limited = True
        return {}

    def validate_ticker(self, ticker: str) -> dict | None:
        try:
            info = self._get_info_with_retry(ticker)
            if not info or (info.get("trailingEps") is None and info.get("currentPrice") is None):
                return None
            return {
                "ticker": ticker.upper(),
                "company_name": info.get("longName") or info.get("shortName", ""),
                "cik": str(info.get("cik", "")).zfill(10) if info.get("cik") else None,
                "exchange": info.get("exchange"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "fiscal_year_end": self._parse_fiscal_year_end(info),
            }
        except Exception:
            return None

    def get_stock_info(self, ticker: str) -> dict:
        info = self._get_info_with_retry(ticker)
        return {
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "eps_ttm": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "pe_ttm": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_ttm": info.get("totalRevenue"),
            "market_cap": info.get("marketCap"),
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "analyst_target_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationMean"),
        }

    def get_price_history(self, ticker: str, period: str = "5y") -> pd.DataFrame:
        for attempt in range(3):
            try:
                return yf.Ticker(ticker).history(period=period, interval="1mo")
            except Exception:
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return pd.DataFrame()

    def get_quarterly_eps(self, ticker: str) -> pd.Series:
        stock = yf.Ticker(ticker)
        df = stock.quarterly_income_stmt
        if "Diluted EPS" in df.index:
            return df.loc["Diluted EPS"]
        return pd.Series(dtype=float)

    def get_quarterly_revenue(self, ticker: str) -> pd.Series:
        stock = yf.Ticker(ticker)
        df = stock.quarterly_income_stmt
        if "Total Revenue" in df.index:
            return df.loc["Total Revenue"]
        return pd.Series(dtype=float)

    def get_earnings_estimates(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        result = {}
        try:
            result["earnings_estimate"] = stock.earnings_estimate.to_dict() if stock.earnings_estimate is not None else {}
        except Exception:
            result["earnings_estimate"] = {}
        try:
            result["revenue_estimate"] = stock.revenue_estimate.to_dict() if stock.revenue_estimate is not None else {}
        except Exception:
            result["revenue_estimate"] = {}
        return result

    def _parse_fiscal_year_end(self, info: dict) -> str | None:
        raw = info.get("lastFiscalYearEnd")
        if raw is None:
            return None
        try:
            dt = pd.Timestamp(raw)
            return dt.strftime("%m-%d")
        except Exception:
            return None


@lru_cache(maxsize=1)
def get_yfinance_client() -> YFinanceClient:
    return YFinanceClient()
