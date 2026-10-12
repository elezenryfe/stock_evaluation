from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class GuidanceItem(BaseModel):
    metric: str  # "EPS", "Revenue", "GrossMargin", "OperatingIncome", "Other"
    value_low: Optional[float] = None
    value_high: Optional[float] = None
    value_midpoint: Optional[float] = None
    unit: str  # "USD", "USD_billions", "percent", "USD_millions"
    period_label: str
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    calendar_year: Optional[int] = None
    is_official_guidance: bool = False
    source_quote: str = ""
    confidence: str = "medium"  # "high", "medium", "low"
    guidance_type: str = "initial"  # initial, raised, lowered, reiterated, withdrawn
    source_type: str = ""  # SEC_8K, SEC_10Q, earnings_call, news_article
    source_url: str = ""
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    guidance_items: list[GuidanceItem] = []
    document_type: str = ""  # earnings_call, 8-K, 10-Q, press_release, news_article
    company_name: str = ""
    reporting_period: str = ""
    extraction_notes: str = ""


class GuidanceSummary(BaseModel):
    ticker: str
    company_name: str
    analysis_date: date
    eps_guidance: Optional[GuidanceItem] = None
    revenue_guidance: Optional[GuidanceItem] = None
    gross_margin_guidance: Optional[GuidanceItem] = None
    guidance_period: str = ""
    source_count: int = 0
    overall_confidence: float = 0.0
    conflict_detected: bool = False
    all_items: list[GuidanceItem] = []


class ValidationResult(BaseModel):
    valid: bool
    reason: str = ""
    flags: list[str] = []
