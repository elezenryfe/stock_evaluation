import numpy as np

from app.ingestion.yfinance_client import YFinanceClient
from app.services.pe_calculator import calculate_historical_median_pe


def calculate_valuation(ticker: str, client: YFinanceClient, pe_years: int = 5) -> dict:
    info = client.get_stock_info(ticker)
    return calculate_valuation_from_data(ticker, info, client, pe_years)


def calculate_valuation_from_data(
    ticker: str,
    info: dict,
    client: YFinanceClient | None = None,
    pe_years: int = 5,
) -> dict:
    current_price = info.get("current_price")
    eps_ttm = info.get("eps_ttm")
    forward_eps = info.get("forward_eps")
    revenue_ttm = info.get("revenue_ttm")
    market_cap = info.get("market_cap")
    pe_ttm = info.get("pe_ttm")

    negative_eps = eps_ttm is not None and eps_ttm < 0
    insufficient = current_price is None and eps_ttm is None and forward_eps is None

    guidance_eps = forward_eps

    pe_result = None
    if client is not None:
        pe_result = calculate_historical_median_pe(ticker, client, years=pe_years)

    result = {
        "ticker": ticker.upper(),
        "company_name": info.get("company_name"),
        "current_price": current_price,
        "current_eps_ttm": eps_ttm,
        "current_revenue_ttm": revenue_ttm,
        "market_cap": market_cap,
        "current_pe_ttm": pe_ttm,
        "guidance_eps": guidance_eps,
        "guidance_revenue": None,
        "guidance_period": None,
        "median_pe": None,
        "pe_years_used": pe_years,
        "pe_observations": None,
        "pe_p25": None,
        "pe_p75": None,
        "estimated_price": None,
        "bull_price": None,
        "bear_price": None,
        "upside_pct": None,
        "confidence_score": None,
        "valuation_method": "forward_eps_x_median_pe",
        "negative_eps_flag": negative_eps,
        "low_confidence_flag": False,
        "insufficient_data_flag": insufficient,
        "alternative_valuations": {},
        "peg_health": None,
    }

    if pe_result:
        result["pe_p25"] = pe_result["p25_pe"]
        result["pe_p75"] = pe_result["p75_pe"]

    if negative_eps and pe_result:
        _apply_ps_ratio_valuation(result, revenue_ttm, market_cap, pe_result)
    elif pe_result and guidance_eps and guidance_eps > 0:
        _apply_pe_valuation(result, guidance_eps, current_price, pe_result)
    elif guidance_eps and guidance_eps > 0 and pe_ttm and pe_ttm > 0:
        estimated = guidance_eps * pe_ttm
        upside = ((estimated - current_price) / current_price * 100) if current_price else None
        result.update({
            "median_pe": pe_ttm,
            "pe_observations": 1,
            "estimated_price": round(estimated, 2),
            "bull_price": round(estimated * 1.3, 2),
            "bear_price": round(estimated * 0.7, 2),
            "upside_pct": round(upside, 2) if upside else None,
            "valuation_method": "forward_eps_x_current_pe",
            "low_confidence_flag": True,
        })

    result["peg_health"] = _peg_sanity_check(pe_ttm, eps_ttm, forward_eps, client, ticker)

    return result


def _apply_pe_valuation(result: dict, guidance_eps: float, current_price: float | None, pe_result: dict):
    median_pe = pe_result["median_pe"]
    estimated = guidance_eps * median_pe
    bull = guidance_eps * pe_result["p75_pe"]
    bear = guidance_eps * pe_result["p25_pe"]
    upside = ((estimated - current_price) / current_price * 100) if current_price else None

    result.update({
        "median_pe": median_pe,
        "pe_observations": pe_result["observations"],
        "estimated_price": round(estimated, 2),
        "bull_price": round(bull, 2),
        "bear_price": round(bear, 2),
        "upside_pct": round(upside, 2) if upside else None,
        "valuation_method": "guided_eps_x_median_pe",
    })


def _apply_ps_ratio_valuation(result: dict, revenue_ttm: float | None, market_cap: float | None, pe_result: dict):
    result["valuation_method"] = "ps_ratio_fallback"
    result["low_confidence_flag"] = True

    if not revenue_ttm or not market_cap or revenue_ttm <= 0:
        result["alternative_valuations"]["ps_ratio"] = {"error": "Insufficient data for P/S valuation"}
        return

    ps_current = float(market_cap) / float(revenue_ttm)
    result["alternative_valuations"]["ps_ratio"] = {
        "current_ps_ratio": round(ps_current, 2),
        "estimated_ps_ratio": round(ps_current * 0.8, 2),
        "revenue_ttm": revenue_ttm,
        "market_cap": market_cap,
        "note": "EPS is negative; PE-based valuation inapplicable. Using P/S ratio.",
    }


def _peg_sanity_check(pe_ttm, eps_ttm, forward_eps, client, ticker):
    if not pe_ttm or pe_ttm <= 0:
        return None
    growth_rate = _estimate_eps_growth(eps_ttm, forward_eps, client, ticker)
    if growth_rate is None or growth_rate <= 0:
        return {"error": "Cannot compute PEG (negative or unavailable growth rate)"}
    peg = pe_ttm / (growth_rate * 100)
    if peg < 1:
        assessment = "potentially undervalued"
    elif peg < 2:
        assessment = "fairly valued"
    elif peg < 3:
        assessment = "somewhat overvalued"
    else:
        assessment = "potentially overvalued"
    return {"peg_ratio": round(peg, 2), "pe_ttm": pe_ttm, "eps_growth_rate_pct": round(growth_rate * 100, 1), "assessment": f"PEG={peg:.2f}: {assessment}"}


def _estimate_eps_growth(eps_ttm, forward_eps, client, ticker):
    if eps_ttm and forward_eps and eps_ttm > 0:
        return (forward_eps - eps_ttm) / eps_ttm
    if client is not None:
        try:
            quarterly = client.get_quarterly_eps(ticker)
            if not quarterly.empty and len(quarterly) >= 6:
                recent = quarterly.head(4)
                older = quarterly.head(8).tail(4)
                if recent.sum() > 0 and older.sum() > 0:
                    return (float(recent.sum()) - float(older.sum())) / abs(float(older.sum()))
        except Exception:
            pass
    return None
