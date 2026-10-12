import logging
import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.api.websocket import push_progress
from app.ingestion.edgar_client import get_edgar_client, resolve_cik
from app.ingestion.scraper import SmartScraper
from app.ingestion.twelvedata_client import get_twelvedata_client
from app.ingestion.yfinance_client import get_yfinance_client
from app.services.confidence_service import calculate_confidence_summary
from app.services.document_ingestion import discover_documents
from app.services.guidance_service import extract_guidance_from_documents
from app.services.valuation_service import calculate_valuation, calculate_valuation_from_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analysis"])


class AnalysisRequest(BaseModel):
    ticker: str
    force_refresh: bool = False

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        ticker = v.strip().upper()
        if not re.match(r"^[A-Z0-9.\-]{1,20}$", ticker):
            raise ValueError("Invalid ticker format")
        return ticker


@router.post("")
async def start_analysis(request: AnalysisRequest):
    ticker = request.ticker
    job_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    degradation_flags: list[str] = []

    push_progress(job_id, "progress", stage="validating", message="Validating ticker", pct=5)

    yf_client = get_yfinance_client()
    td_client = get_twelvedata_client()
    validation = yf_client.validate_ticker(ticker)
    data_source = "yfinance"
    pe_client = yf_client

    if validation is None and yf_client.is_rate_limited():
        td_validation = td_client.validate_ticker(ticker)
        if td_validation:
            validation = td_validation
            data_source = "twelvedata"
            pe_client = None
            degradation_flags.append("yfinance_rate_limited_using_twelvedata")

    if validation is None:
        push_progress(job_id, "error", stage="error", message=f"Ticker '{ticker}' not found")
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

    company_name = validation.get("company_name", "")
    cik = validation.get("cik")
    if not cik:
        cik = await resolve_cik(ticker)

    push_progress(job_id, "progress", stage="fetching_data", message=f"Fetching financial data ({data_source})", pct=15)

    try:
        if data_source == "twelvedata":
            td_info = td_client.get_stock_info(ticker)
            valuation = calculate_valuation_from_data(ticker, td_info, client=None)
        else:
            valuation = calculate_valuation(ticker, yf_client)
    except Exception as e:
        logger.error(f"Valuation failed for {ticker}: {e}")
        degradation_flags.append("valuation_failed")
        push_progress(job_id, "error", stage="error", message=f"Valuation failed: {e}")
        raise HTTPException(status_code=502, detail=f"Valuation failed: {str(e)}")

    if valuation["insufficient_data_flag"]:
        push_progress(job_id, "error", stage="error", message="Insufficient financial data")
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient financial data for '{ticker}'. The data source may be temporarily unavailable.",
        )

    push_progress(job_id, "progress", stage="fetching_documents", message="Fetching SEC filings and documents", pct=30)

    edgar = await get_edgar_client()
    scraper = SmartScraper()
    docs = []
    try:
        docs = await discover_documents(ticker, company_name, cik, edgar, scraper)
    except Exception as e:
        logger.warning(f"Document discovery failed for {ticker}: {e}")
        degradation_flags.append("document_fetch_partial")
    finally:
        await scraper.close()

    if not docs:
        degradation_flags.append("no_documents_found")
        push_progress(job_id, "progress", stage="extracting_guidance", message="No documents found; using analyst consensus", pct=50)
    else:
        push_progress(job_id, "progress", stage="extracting_guidance", message=f"Extracting guidance from {len(docs)} documents", pct=50)

    guidance_summary = None
    guidance_used = "analyst_consensus"
    if docs:
        try:
            guidance_summary = await extract_guidance_from_documents(
                ticker=ticker,
                company_name=company_name,
                documents=docs,
                current_eps_ttm=valuation.get("current_eps_ttm"),
                current_revenue_ttm=valuation.get("current_revenue_ttm"),
            )
            if guidance_summary.eps_guidance and guidance_summary.eps_guidance.value_midpoint:
                guidance_used = "extracted"
                degradation_flags.append("llm_extraction_succeeded")
        except Exception as e:
            logger.warning(f"Guidance extraction failed for {ticker}: {e}")
            degradation_flags.append("llm_extraction_failed_using_fallback")

    push_progress(job_id, "progress", stage="calculating_valuation", message="Calculating final valuation", pct=75)

    if guidance_used == "extracted" and guidance_summary:
        valuation["guidance_eps"] = guidance_summary.eps_guidance.value_midpoint
        valuation["guidance_revenue"] = (
            guidance_summary.revenue_guidance.value_midpoint
            if guidance_summary.revenue_guidance
            else None
        )
        valuation["guidance_period"] = guidance_summary.guidance_period
        valuation["guidance_source"] = "extracted"

        if guidance_summary.eps_guidance.value_midpoint and pe_client is not None:
            _recalculate_with_extracted_eps(valuation, guidance_summary, pe_client, ticker)
    else:
        valuation["guidance_source"] = "analyst_consensus"
        valuation["guidance_period"] = _analyst_consensus_period(validation)
        degradation_flags.append("no_extracted_guidance")

    confidence = calculate_confidence_summary(
        guidance=guidance_summary,
        pe_observations=valuation.get("pe_observations"),
        negative_eps=valuation["negative_eps_flag"],
    )
    valuation["confidence_score"] = confidence["valuation_confidence"]

    sources = []
    for doc in docs:
        sources.append({
            "url": doc["source_url"],
            "source_type": doc["source_type"],
            "document_date": str(doc["document_date"]) if doc["document_date"] else None,
            "document_title": doc["document_title"],
            "word_count": doc["word_count"],
        })

    completed = datetime.now(timezone.utc)

    response_data = {
        "job_id": job_id,
        "status": "complete",
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "result": valuation,
        "guidance": {
            "overall_confidence": guidance_summary.overall_confidence if guidance_summary else 0.0,
            "guidance_period": guidance_summary.guidance_period if guidance_summary else "",
            "conflict_detected": guidance_summary.conflict_detected if guidance_summary else False,
            "eps_guidance": _serialize_item(guidance_summary.eps_guidance) if guidance_summary else None,
            "revenue_guidance": _serialize_item(guidance_summary.revenue_guidance) if guidance_summary else None,
            "gross_margin_guidance": _serialize_item(guidance_summary.gross_margin_guidance) if guidance_summary else None,
            "items_found": len(guidance_summary.all_items) if guidance_summary else 0,
            "source": guidance_used,
        },
        "confidence": confidence,
        "sources": sources,
        "source_count": len(sources),
        "degradation": {
            "flags": degradation_flags,
            "is_degraded": any("failed" in f or "no_" in f for f in degradation_flags),
        },
    }

    push_progress(job_id, "complete", pct=100, result=response_data)
    return response_data


def _recalculate_with_extracted_eps(valuation: dict, guidance_summary, client, ticker: str):
    from app.services.pe_calculator import calculate_historical_median_pe
    extracted_eps = guidance_summary.eps_guidance.value_midpoint
    pe_result = calculate_historical_median_pe(ticker, client)
    if not pe_result or extracted_eps <= 0:
        return

    median_pe = pe_result["median_pe"]
    current_price = valuation.get("current_price")

    estimated = extracted_eps * median_pe
    bull = extracted_eps * pe_result["p75_pe"]
    bear = extracted_eps * pe_result["p25_pe"]
    upside = ((estimated - current_price) / current_price * 100) if current_price else None

    valuation.update({
        "median_pe": median_pe,
        "pe_p25": pe_result["p25_pe"],
        "pe_p75": pe_result["p75_pe"],
        "pe_observations": pe_result["observations"],
        "estimated_price": round(estimated, 2),
        "bull_price": round(bull, 2),
        "bear_price": round(bear, 2),
        "upside_pct": round(upside, 2) if upside else None,
        "valuation_method": "extracted_eps_x_median_pe",
    })


def _analyst_consensus_period(validation: dict) -> str:
    fy_end = validation.get("fiscal_year_end")
    if not fy_end:
        return "Forward estimate"
    try:
        month, day = fy_end.split("-")
        fy_month, fy_day = int(month), int(day)
        today = datetime.now(timezone.utc).date()
        # The fiscal year whose end date is the next occurrence of fy_end
        fy_end_this_year = date(today.year, fy_month, fy_day)
        if fy_end_this_year >= today:
            fy = today.year
        else:
            fy = today.year + 1
        return f"FY{fy} (analyst consensus)"
    except (ValueError, TypeError):
        return "Forward estimate"


def _serialize_item(item) -> dict | None:
    if item is None:
        return None
    return {
        "metric": item.metric,
        "value_low": item.value_low,
        "value_high": item.value_high,
        "value_midpoint": item.value_midpoint,
        "unit": item.unit,
        "period_label": item.period_label,
        "fiscal_year": item.fiscal_year,
        "fiscal_quarter": item.fiscal_quarter,
        "is_official_guidance": item.is_official_guidance,
        "source_quote": item.source_quote,
        "confidence": item.confidence,
        "guidance_type": item.guidance_type,
        "source_type": item.source_type,
    }
