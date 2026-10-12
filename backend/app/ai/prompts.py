# Compact schema — the model already knows financial JSON schemas.
# Must include 'json' (lowercase) for response_format json_object mode.
SCHEMA_INSTRUCTIONS = """
Return ONLY this json: {"guidance_items":[{"metric":"EPS|Revenue|GrossMargin|OperatingIncome|Other",
"value_low":n|null,"value_high":n|null,"value_midpoint":n|null,
"unit":"USD|USD_billions|percent|USD_millions","period_label":"str",
"fiscal_year":n|null,"fiscal_quarter":1-4|null,"is_official_guidance":bool,
"source_quote":"verbatim","confidence":"high|medium|low",
"guidance_type":"initial|raised|lowered|reiterated|withdrawn"}],
"document_type":"8-K|10-Q|earnings_call|press_release|news_article",
"company_name":"","reporting_period":"","extraction_notes":""}
OFFICIAL guidance only (management, not analysts). Numbers: $X.XX billion -> numeric.
"""

GENERAL_EXTRACTION_PROMPT = f"""
Extract ALL forward-looking management guidance from the document below.
For each: metric, numeric value/range, period, verbatim quote, is_official_guidance.

DOCUMENT:
{{document_chunk}}

{SCHEMA_INSTRUCTIONS}"""

EARNINGS_CALL_PROMPT = f"""
Extract guidance from this earnings call transcript. Management speakers
are labeled (e.g., "[CEO]: ...", "[CFO]: ..."). ONLY extract management guidance,
not analyst questions. Identify raised/lowered/reiterated vs prior guidance.

TRANSCRIPT:
{{document_chunk}}

{SCHEMA_INSTRUCTIONS}"""

SEC_8K_PROMPT = f"""
Extract forward-looking guidance from this SEC 8-K filing. Guidance is
typically in "Outlook" or "Guidance" sections. EXCLUDE historical results
(financial tables of past quarters). Only extract management's future projections.

FILING SECTION:
{{document_chunk}}

{SCHEMA_INSTRUCTIONS}"""

NEWS_ARTICLE_PROMPT = f"""
Extract guidance from this financial news article. Distinguish:
- Direct management quotes (is_official_guidance: true)
- Journalist summary of management statements (is_official_guidance: true)
- Analyst opinions (is_official_guidance: false)
Set extraction_confidence = 0.5 for news articles.

ARTICLE:
{{document_chunk}}

{SCHEMA_INSTRUCTIONS}"""


def get_prompt_for_source_type(source_type: str) -> str:
    if source_type in ("earnings_call", "earnings_call_transcript"):
        return EARNINGS_CALL_PROMPT
    if source_type in ("SEC_8K", "SEC_10Q", "SEC_10K", "8-K", "10-Q"):
        return SEC_8K_PROMPT
    if source_type in ("news_article", "press_release"):
        return NEWS_ARTICLE_PROMPT
    return GENERAL_EXTRACTION_PROMPT
