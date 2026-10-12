from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.ingestion.yfinance_client import YFinanceClient


def calculate_historical_median_pe(
    ticker: str,
    client: YFinanceClient,
    years: int = 5,
) -> dict | None:
    prices = client.get_price_history(ticker, period=f"{years}y")
    if prices.empty:
        return None

    quarterly_eps = client.get_quarterly_eps(ticker)
    if quarterly_eps.empty:
        return None

    eps_by_date = _parse_quarterly_eps_dates(quarterly_eps)
    monthly_prices = prices["Close"].resample("ME").last()
    monthly_prices.index = monthly_prices.index.map(_normalize_ts)

    pe_series = []
    for dt_val, price in monthly_prices.items():
        ttm_eps = _sum_ttm_eps(dt_val, eps_by_date)
        if ttm_eps and ttm_eps > 0:
            pe_series.append(float(price) / ttm_eps)

    if len(pe_series) < 5:
        return None

    return {
        "median_pe": round(float(np.median(pe_series)), 2),
        "mean_pe": round(float(np.mean(pe_series)), 2),
        "p25_pe": round(float(np.percentile(pe_series, 25)), 2),
        "p75_pe": round(float(np.percentile(pe_series, 75)), 2),
        "min_pe": round(float(np.min(pe_series)), 2),
        "max_pe": round(float(np.max(pe_series)), 2),
        "observations": len(pe_series),
        "years_used": years,
    }


def _normalize_ts(ts: pd.Timestamp) -> pd.Timestamp:
    if ts.tz is not None:
        return ts.tz_localize(None)
    return ts


def _parse_quarterly_eps_dates(eps_series: pd.Series) -> list[tuple[pd.Timestamp, float]]:
    entries = []
    for dt_val, value in eps_series.items():
        if isinstance(dt_val, pd.Timestamp) and not pd.isna(value):
            entries.append((_normalize_ts(dt_val), float(value)))
    entries.sort(key=lambda x: x[0])
    return entries


def _sum_ttm_eps(as_of: pd.Timestamp, eps_entries: list[tuple[pd.Timestamp, float]]) -> float | None:
    as_of = _normalize_ts(as_of)
    past = [(dt, val) for dt, val in eps_entries if dt <= as_of]
    if len(past) < 4:
        return None
    last_four = past[-4:]
    max_gap = timedelta(days=150)
    for i in range(1, len(last_four)):
        if last_four[i][0] - last_four[i - 1][0] > max_gap:
            return None
    return sum(val for _, val in last_four)


def build_pe_history(
    ticker: str,
    stock_id: str,
    client: YFinanceClient,
    years: int = 5,
) -> list[dict]:
    prices = client.get_price_history(ticker, period=f"{years}y")
    if prices.empty:
        return []

    quarterly_eps = client.get_quarterly_eps(ticker)
    if quarterly_eps.empty:
        return []

    eps_by_date = _parse_quarterly_eps_dates(quarterly_eps)
    monthly_prices = prices["Close"].resample("ME").last()
    monthly_prices.index = monthly_prices.index.map(_normalize_ts)

    records = []
    for dt_val, price in monthly_prices.items():
        ttm_eps = _sum_ttm_eps(dt_val, eps_by_date)
        if ttm_eps and ttm_eps > 0:
            pe = float(price) / ttm_eps
            records.append({
                "stock_id": stock_id,
                "date": dt_val.date(),
                "price": round(float(price), 4),
                "eps_ttm": round(ttm_eps, 4),
                "pe_ratio": round(pe, 4),
                "data_source": "yfinance",
            })

    return records
