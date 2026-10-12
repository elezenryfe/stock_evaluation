import numpy as np

from app.schemas.guidance import GuidanceItem, GuidanceSummary

SOURCE_QUALITY_WEIGHTS: dict[str, float] = {
    "SEC_8K": 1.0,
    "SEC_10Q": 1.0,
    "SEC_10K": 0.95,
    "earnings_call_transcript": 0.95,
    "press_release": 0.9,
    "investor_day": 0.85,
    "news_article": 0.5,
    "analyst_estimate": 0.3,
}

GUIDANCE_TYPE_MODIFIERS: dict[str, float] = {
    "initial": 1.0,
    "reiterated": 0.95,
    "raised": 0.9,
    "lowered": 0.85,
    "analyst": 0.6,
    "ambiguous": 0.4,
}


def calculate_guidance_confidence(
    items: list[GuidanceItem],
    source_count: int,
    days_since_guidance: int | None = None,
    hallucination_flags: int = 0,
    return_breakdown: bool = False,
):
    if not items:
        if return_breakdown:
            return 0.0, {}
        return 0.0

    official = [i for i in items if i.is_official_guidance]
    eps_items = [i for i in items if i.metric == "EPS"]

    pool = official if official else items
    source_scores = [SOURCE_QUALITY_WEIGHTS.get(i.source_type, 0.5) for i in pool]

    avg_quality = np.mean(source_scores) if source_scores else 0.0
    source_quality_contrib = 0.4 * avg_quality

    unique_sources = len(set(i.source_url for i in pool if i.source_url))
    source_bonus = min(unique_sources / 3, 1.0)
    source_diversity_contrib = 0.2 * source_bonus

    consensus_contrib = 0.0
    cv = None
    if len(eps_items) >= 2:
        eps_vals = [_midpoint(i) for i in eps_items]
        eps_vals = [v for v in eps_vals if v is not None]
        if eps_vals and np.mean(eps_vals) != 0:
            cv = float(np.std(eps_vals) / abs(np.mean(eps_vals)))
            consensus_score = max(0, 1 - cv * 5)
            consensus_contrib = 0.2 * consensus_score
        else:
            consensus_contrib = 0.1
    else:
        consensus_contrib = 0.1

    recency_contrib = 0.0
    recency = None
    if days_since_guidance is not None:
        recency = max(0, 1 - days_since_guidance / 90)
        recency_contrib = 0.1 * recency

    score = source_quality_contrib + source_diversity_contrib + consensus_contrib + recency_contrib

    score -= hallucination_flags * 0.1

    modifier = _best_modifier(pool)
    score *= modifier

    final = round(max(0.0, min(1.0, score)), 2)

    if return_breakdown:
        breakdown = {
            "source_quality": round(source_quality_contrib, 3),
            "source_diversity": round(source_diversity_contrib, 3),
            "consensus_tightness": round(consensus_contrib, 3),
            "recency": round(recency_contrib, 3),
            "hallucination_penalty": round(hallucination_flags * 0.1, 3),
            "guidance_type_modifier": modifier,
            "avg_source_weight": round(avg_quality, 3),
            "unique_sources": unique_sources,
            "eps_items_count": len(eps_items),
            "cv": round(cv, 4) if cv is not None else None,
            "days_since_guidance": days_since_guidance,
        }
        return final, breakdown
    return final


def calculate_valuation_confidence(
    guidance_confidence: float,
    pe_observation_count: int | None,
    negative_eps: bool,
    has_guidance: bool,
    return_breakdown: bool = False,
):
    if negative_eps:
        final = round(guidance_confidence * 0.5, 2)
        if return_breakdown:
            return final, {"capped": "negative_eps", "guidance_contrib": round(guidance_confidence * 0.5, 3)}
        return final
    if not has_guidance:
        final = round(guidance_confidence * 0.6, 2)
        if return_breakdown:
            return final, {"capped": "no_guidance", "guidance_contrib": round(guidance_confidence * 0.6, 3)}
        return final

    guidance_contrib = guidance_confidence * 0.7
    pe_bonus = min(pe_observation_count / 20, 1.0) if pe_observation_count else 0.0
    pe_contrib = 0.3 * pe_bonus
    score = guidance_contrib + pe_contrib
    final = round(max(0.0, min(1.0, score)), 2)

    if return_breakdown:
        return final, {
            "guidance_contrib": round(guidance_contrib, 3),
            "pe_history_contrib": round(pe_contrib, 3),
            "pe_observations": pe_observation_count,
            "pe_bonus_factor": round(pe_bonus, 3),
        }
    return final


def calculate_confidence_summary(
    guidance: GuidanceSummary | None,
    pe_observations: int | None,
    negative_eps: bool,
    days_since_guidance: int | None = None,
    hallucination_flags: int = 0,
) -> dict:
    if guidance is None or not guidance.all_items:
        guidance_conf = 0.3  # analyst consensus default
        has_guidance = False
        guidance_breakdown = {}
    else:
        guidance_conf, guidance_breakdown = calculate_guidance_confidence(
            guidance.all_items,
            guidance.source_count,
            days_since_guidance,
            hallucination_flags,
            return_breakdown=True,
        )
        has_guidance = len(guidance.all_items) > 0

    valuation_conf, valuation_breakdown = calculate_valuation_confidence(
        guidance_conf, pe_observations, negative_eps, has_guidance,
        return_breakdown=True,
    )

    descriptors = [
        (0.8, "HIGH"),
        (0.5, "MEDIUM"),
        (0.0, "LOW"),
    ]

    label = next(d for threshold, d in descriptors if valuation_conf >= threshold)

    return {
        "guidance_confidence": guidance_conf,
        "valuation_confidence": valuation_conf,
        "confidence_label": label,
        "has_official_guidance": has_guidance,
        "breakdown": {
            "guidance": guidance_breakdown,
            "valuation": valuation_breakdown,
        },
    }


def _midpoint(item: GuidanceItem) -> float | None:
    if item.value_midpoint is not None:
        return item.value_midpoint
    if item.value_low is not None and item.value_high is not None:
        return (item.value_low + item.value_high) / 2
    return item.value_low or item.value_high


def _best_modifier(items: list[GuidanceItem]) -> float:
    if not items:
        return 0.5
    return max(
        GUIDANCE_TYPE_MODIFIERS.get(i.guidance_type, 0.7) for i in items
    )
