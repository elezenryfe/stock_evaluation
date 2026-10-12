import hashlib
import re

FINANCIAL_KEYWORDS = [
    "revenue", "earnings", "eps", "guidance", "outlook", "forecast",
    "gross margin", "operating income", "net income", "ebitda",
    "free cash flow", "diluted eps", "gaap", "non-gaap",
    "quarter", "fiscal year", "share", "dividend", "buyback",
    "growth", "segment", "consensus", "estimate",
]

MIN_WORD_COUNT = 200


def compute_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_english(text: str) -> bool:
    if len(text) < 50:
        return True
    sample = text[:1000].lower()
    non_ascii = sum(1 for c in sample if ord(c) > 127)
    return non_ascii / max(len(sample), 1) < 0.15


def has_financial_keywords(text: str) -> bool:
    text_lower = text.lower()
    matches = sum(1 for kw in FINANCIAL_KEYWORDS if kw in text_lower)
    return matches >= 2


def meets_min_word_count(text: str) -> bool:
    return len(text.split()) >= MIN_WORD_COUNT


def content_quality_check(text: str) -> dict:
    word_count = len(text.split())
    checksum = compute_checksum(text)
    return {
        "checksum": checksum,
        "word_count": word_count,
        "passes_word_count": word_count >= MIN_WORD_COUNT,
        "is_english": is_english(text),
        "has_financial_keywords": has_financial_keywords(text),
        "passed": (
            word_count >= MIN_WORD_COUNT
            and is_english(text)
            and has_financial_keywords(text)
        ),
    }
