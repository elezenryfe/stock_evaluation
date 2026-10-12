import hashlib
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np

from app.ai.hallucination_guard import HallucinationGuard
from app.ai.llm_gateway import get_llm_gateway
from app.ai.prompts import get_prompt_for_source_type
from app.schemas.guidance import (
    ExtractionResult,
    GuidanceItem,
    GuidanceSummary,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / ".llm_cache"

SOURCE_QUALITY_WEIGHTS: dict[str, float] = {
    "SEC_8K": 1.0,
    "SEC_10Q": 1.0,
    "earnings_call_transcript": 0.95,
    "press_release": 0.9,
    "investor_day": 0.85,
    "news_article": 0.5,
    "analyst_estimate": 0.3,
}

# Section boundaries that mark the END of a guidance/outlook section.
SECTION_BOUNDARIES = [
    "about nvidia", "about advanced micro", "about intel",
    "forward-looking statements", "safe harbor", "non-gaap reconciliation",
    "supplemental", "contact", "investor relations", "media contact",
    "conference call", "webcast", "table of contents",
]


def _load_cache(cache_key: str) -> ExtractionResult | None:
    try:
        path = CACHE_DIR / f"{cache_key}.json"
        if path.exists():
            data = json.loads(path.read_text())
            items = [GuidanceItem(**i) for i in data.get("guidance_items", [])]
            return ExtractionResult(
                guidance_items=items,
                document_type=data.get("document_type", ""),
                company_name=data.get("company_name", ""),
                reporting_period=data.get("reporting_period", ""),
                extraction_notes=data.get("extraction_notes", ""),
            )
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    return None


def _save_cache(cache_key: str, result: ExtractionResult):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "guidance_items": [i.model_dump() for i in result.guidance_items],
            "document_type": result.document_type,
            "company_name": result.company_name,
            "reporting_period": result.reporting_period,
            "extraction_notes": result.extraction_notes,
        }
        (CACHE_DIR / f"{cache_key}.json").write_text(json.dumps(data))
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


def _smart_excerpt(raw_text: str) -> str:
    """Find the Outlook/Guidance section and extract just that portion."""
    text_lower = raw_text.lower()
    best_start = None

    # Find the start of the guidance section.
    for marker in ["outlook for the", "financial outlook", "business outlook", "outlook", "guidance"]:
        idx = text_lower.find(marker)
        if idx >= 0:
            # Walk back to find the section header line start.
            pre = raw_text[:idx].rstrip()
            last_nl = pre.rfind("\n")
            best_start = last_nl + 1 if last_nl >= 0 else idx
            break

    if best_start is None:
        # No guidance section found — take from the document's second half.
        return raw_text[len(raw_text) // 2:len(raw_text) // 2 + 4000].strip()

    # Find the end of the guidance section: next major section boundary.
    best_end = best_start + 4000  # default: take 4000 chars
    for boundary in SECTION_BOUNDARIES:
        b_idx = text_lower.find(boundary, best_start + 500)
        if b_idx >= 0 and b_idx < best_end:
            best_end = b_idx
        # Also check for the SECOND occurrence (the first is in the guidance text itself).
        second = text_lower.find(boundary, text_lower.find(boundary, best_start + 500) + 1)
        if best_start + 500 < second < best_end:
            best_end = second

    excerpt = raw_text[best_start:best_end].strip()
    return excerpt if len(excerpt) >= 200 else raw_text[best_start:best_start + 4000].strip()


async def extract_guidance_from_documents(
    ticker: str,
    company_name: str,
    documents: list[dict],
    current_eps_ttm: Optional[float] = None,
    current_revenue_ttm: Optional[float] = None,
) -> GuidanceSummary:
    llm = get_llm_gateway()
    guard = HallucinationGuard()
    all_items: list[GuidanceItem] = []
    all_extractions: list[ExtractionResult] = []

    for doc in documents:
        source_type = doc.get("source_type", "generic")
        raw_text = doc.get("raw_text", "")
        if not raw_text:
            continue

        # Cache key: hash of document text + source type.
        cache_key = hashlib.sha256(f"{source_type}:{raw_text}".encode()).hexdigest()[:16]

        # Check cache first.
        result = _load_cache(cache_key)
        if result:
            logger.info(f"LLM cache hit for {source_type}")
        else:
            excerpt = _smart_excerpt(raw_text)
            prompt = get_prompt_for_source_type(source_type)

            try:
                result = await llm.extract_guidance(prompt, excerpt)
            except Exception as e:
                logger.warning(f"LLM extraction failed for {source_type}: {e}")
                continue

            if result.guidance_items:
                _save_cache(cache_key, result)

        result.document_type = source_type

        validated = guard.filter_valid_items(result, current_eps_ttm, current_revenue_ttm)
        all_extractions.append(validated)

        for item in validated.guidance_items:
            item.source_type = source_type
            item.source_url = doc.get("source_url", "")
            all_items.append(item)

    if not all_items:
        return GuidanceSummary(
            ticker=ticker,
            company_name=company_name,
            analysis_date=date.today(),
            source_count=0,
            overall_confidence=0.0,
        )

    eps_items = [i for i in all_items if i.metric == "EPS" and i.is_official_guidance]
    revenue_items = [i for i in all_items if i.metric == "Revenue" and i.is_official_guidance]
    margin_items = [i for i in all_items if i.metric == "GrossMargin" and i.is_official_guidance]

    if not eps_items:
        eps_items = [i for i in all_items if i.metric == "EPS"]

    resolved_eps = _resolve_guidance(eps_items, "EPS") if eps_items else None
    resolved_revenue = _resolve_guidance(revenue_items, "Revenue") if revenue_items else None
    resolved_margin = _resolve_guidance(margin_items, "GrossMargin") if margin_items else None

    conflict = _detect_conflict(all_extractions)
    confidence = _calculate_confidence(all_items)

    return GuidanceSummary(
        ticker=ticker,
        company_name=company_name,
        analysis_date=date.today(),
        eps_guidance=resolved_eps,
        revenue_guidance=resolved_revenue,
        gross_margin_guidance=resolved_margin,
        guidance_period=resolved_eps.period_label if resolved_eps else "",
        source_count=len(documents),
        overall_confidence=round(confidence, 2),
        conflict_detected=conflict,
        all_items=all_items,
    )


def _resolve_guidance(items: list[GuidanceItem], metric: str) -> Optional[GuidanceItem]:
    official = [i for i in items if i.is_official_guidance]
    pool = official if official else items

    if not pool:
        return None

    values = []
    weights = []
    for item in pool:
        val = item.value_midpoint
        if val is None and item.value_low is not None and item.value_high is not None:
            val = (item.value_low + item.value_high) / 2
        if val is None:
            val = item.value_low or item.value_high
        if val is not None:
            values.append(val)
            weights.append(SOURCE_QUALITY_WEIGHTS.get(item.source_type, 0.5))

    if not values:
        return pool[0]

    weighted_median = _weighted_median(values, weights)
    best = max(pool, key=lambda i: SOURCE_QUALITY_WEIGHTS.get(i.source_type, 0.5))

    return GuidanceItem(
        metric=metric,
        value_midpoint=round(weighted_median, 4),
        value_low=min(values) if len(values) > 1 else None,
        value_high=max(values) if len(values) > 1 else None,
        unit=best.unit,
        period_label=best.period_label,
        fiscal_year=best.fiscal_year,
        fiscal_quarter=best.fiscal_quarter,
        is_official_guidance=best.is_official_guidance,
        source_quote=best.source_quote,
        confidence=best.confidence,
        guidance_type=best.guidance_type,
        source_type=best.source_type,
        source_url=best.source_url,
        extraction_confidence=best.extraction_confidence,
    )


def _weighted_median(values: list[float], weights: list[float]) -> float:
    sorted_pairs = sorted(zip(values, weights), key=lambda x: x[0])
    sorted_values, sorted_weights = zip(*sorted_pairs)
    cumsum = np.cumsum(sorted_weights)
    cutoff = cumsum[-1] / 2.0
    idx = np.searchsorted(cumsum, cutoff)
    return float(sorted_values[min(idx, len(sorted_values) - 1)])


def _detect_conflict(extractions: list[ExtractionResult]) -> bool:
    all_values = []
    for ext in extractions:
        for item in ext.guidance_items:
            if item.metric == "EPS":
                v = item.value_midpoint
                if v is None and item.value_low is not None and item.value_high is not None:
                    v = (item.value_low + item.value_high) / 2
                if v is None:
                    v = item.value_low or item.value_high
                if v is not None:
                    all_values.append(float(v))

    if len(all_values) < 2:
        return False

    min_v, max_v = min(all_values), max(all_values)
    if max_v == 0:
        return False
    deviation = (max_v - min_v) / abs(max_v)
    return deviation > 0.10


def _calculate_confidence(items: list[GuidanceItem]) -> float:
    if not items:
        return 0.0

    official = [i for i in items if i.is_official_guidance]
    eps_items = [i for i in items if i.metric == "EPS"]

    pool = official if official else items
    if not pool:
        return 0.0

    avg_source_quality = np.mean([
        SOURCE_QUALITY_WEIGHTS.get(i.source_type, 0.5) for i in pool
    ])
    score = 0.4 * avg_source_quality

    source_bonus = min(len(set(i.source_url for i in pool)) / 3, 1.0)
    score += 0.2 * source_bonus

    if len(eps_items) >= 2:
        eps_vals = []
        for i in eps_items:
            v = i.value_midpoint or i.value_low or i.value_high
            if v is not None:
                eps_vals.append(v)
        if eps_vals and np.mean(eps_vals) != 0:
            cv = float(np.std(eps_vals) / abs(np.mean(eps_vals)))
            score += 0.2 * max(0, 1 - cv * 5)
    else:
        score += 0.1

    return max(0.0, min(1.0, score))
