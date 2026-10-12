# Stock Guidance Analysis & Valuation Forecasting Platform
## Complete Production-Grade Architecture & Implementation Plan

> **Constraint:** All tools and technologies are free/open-source except LLM API keys (Anthropic/OpenAI).

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [End-to-End Data Flow](#2-end-to-end-data-flow)
3. [Recommended Tech Stack](#3-recommended-tech-stack)
4. [Guidance Extraction Strategy](#4-guidance-extraction-strategy)
5. [Financial Valuation Logic](#5-financial-valuation-logic)
6. [LLM/AI Architecture](#6-llmai-architecture)
7. [Database Schema Design](#7-database-schema-design)
8. [APIs to Use (Free)](#8-apis-to-use-free)
9. [Web Scraping Architecture](#9-web-scraping-architecture)
10. [Frontend UX/UI Plan](#10-frontend-uxui-plan)
11. [Scalability Considerations](#11-scalability-considerations)
12. [Security & Reliability](#12-security--reliability)
13. [Production Deployment Plan](#13-production-deployment-plan)
14. [MVP vs Production Roadmap](#14-mvp-vs-production-roadmap)
15. [End-to-End Walkthrough: NVIDIA](#15-end-to-end-walkthrough-nvidia)
16. [Architecture Diagrams, Contracts & Folder Structure](#16-architecture-diagrams-contracts--folder-structure)

---

## 1. High-Level System Architecture

### 1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER BROWSER / CLIENT                          │
│              React SPA  ──  WebSocket (live updates)                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS
┌────────────────────────────────▼────────────────────────────────────────┐
│                        NGINX REVERSE PROXY                              │
│              Rate Limiting │ TLS Termination │ Load Balancing           │
└──────┬─────────────────────┬───────────────────────────────────────────┘
       │                     │
┌──────▼──────┐    ┌─────────▼─────────┐
│  FastAPI    │    │  FastAPI           │
│  REST API   │    │  WebSocket Server  │
│  (Gunicorn) │    │  (Uvicorn)         │
└──────┬──────┘    └─────────┬──────────┘
       │                     │
┌──────▼─────────────────────▼──────────────────────────────────────────┐
│                      CORE SERVICE LAYER                                │
│                                                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐   │
│  │ Ticker       │  │ Guidance      │  │ Valuation Engine         │   │
│  │ Resolution   │  │ Extraction    │  │ (PE × EPS calculation)   │   │
│  │ Service      │  │ Orchestrator  │  │                          │   │
│  └──────────────┘  └───────────────┘  └──────────────────────────┘   │
│                                                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐   │
│  │ Confidence   │  │ Source        │  │ Notification             │   │
│  │ Scoring      │  │ Citation      │  │ Service                  │   │
│  │ Service      │  │ Service       │  │                          │   │
│  └──────────────┘  └───────────────┘  └──────────────────────────┘   │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│                        TASK QUEUE LAYER                                │
│              Celery Workers  +  Redis Broker  +  Redis Result Backend  │
│   [scrape_task] [llm_extract_task] [financials_task] [valuation_task]  │
└───────┬─────────────────────────────────────────────┬──────────────────┘
        │                                             │
┌───────▼──────────────────┐         ┌───────────────▼─────────────────┐
│   DATA INGESTION LAYER   │         │        AI/LLM LAYER             │
│                          │         │                                  │
│  ┌────────────────────┐  │         │  ┌────────────────────────────┐ │
│  │ SEC EDGAR Fetcher  │  │         │  │ LLM Gateway                │ │
│  │ (free EDGAR API)   │  │         │  │ (Anthropic Claude /        │ │
│  └────────────────────┘  │         │  │  OpenAI GPT-4o)            │ │
│  ┌────────────────────┐  │         │  └────────────────────────────┘ │
│  │ Yahoo Finance      │  │         │  ┌────────────────────────────┐ │
│  │ (yfinance lib)     │  │         │  │ RAG Pipeline               │ │
│  └────────────────────┘  │         │  │ (LangChain + ChromaDB)     │ │
│  ┌────────────────────┐  │         │  └────────────────────────────┘ │
│  │ Web Scraper        │  │         │  ┌────────────────────────────┐ │
│  │ (Playwright/httpx) │  │         │  │ Structured Extractor       │ │
│  └────────────────────┘  │         │  │ (Pydantic output schema)   │ │
│  ┌────────────────────┐  │         │  └────────────────────────────┘ │
│  │ RSS/News Feeds     │  │         └──────────────────────────────────┘
│  │ (feedparser)       │  │
│  └────────────────────┘  │
└──────────────────────────┘
        │                                   │
┌───────▼───────────────────────────────────▼──────────────────────────┐
│                         CACHING LAYER                                 │
│         Redis (TTL-based):  stock prices (5m) │ PE data (1h)         │
│                             guidance (24h)     │ valuations (6h)      │
└───────────────────────────────────────────────┬──────────────────────┘
                                                │
┌───────────────────────────────────────────────▼──────────────────────┐
│                         DATABASE LAYER                                │
│                                                                       │
│   PostgreSQL (primary)          ChromaDB (vector store)              │
│   ├─ stocks                     └─ document embeddings               │
│   ├─ guidance_extractions           (OpenAI/local embeddings)        │
│   ├─ valuations                                                       │
│   ├─ source_documents                                                 │
│   ├─ pe_history                                                       │
│   └─ analysis_runs                                                    │
└───────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Descriptions

| Component | Technology | Responsibility |
|---|---|---|
| **Frontend** | React + Vite + TailwindCSS | User interface, real-time updates |
| **API Gateway** | Nginx | TLS, rate limiting, routing |
| **Backend API** | FastAPI (Python 3.11+) | REST endpoints, WebSocket |
| **Task Queue** | Celery + Redis | Async job execution |
| **Data Ingestion** | yfinance, EDGAR, Playwright | Fetching raw financial data |
| **AI Layer** | LangChain + Claude/GPT-4o | Guidance extraction from text |
| **Vector Store** | ChromaDB (self-hosted) | Semantic search over docs |
| **Relational DB** | PostgreSQL 15 | Persistent structured data |
| **Cache** | Redis 7 | TTL-based result caching |
| **Monitoring** | Prometheus + Grafana + Loki | Metrics, logs, alerting |
| **Embeddings** | sentence-transformers (local) | Free embedding generation |

### 1.3 Deployment Architecture

```
┌──────────────────────────────────────────────┐
│           Docker Compose (Dev/MVP)            │
│  nginx │ api │ worker │ postgres │ redis      │
│  chromadb │ prometheus │ grafana              │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│        Kubernetes (Production)                │
│  Namespaces: app / data / monitoring          │
│  Deployments: api (3 replicas)                │
│               worker (5 replicas)             │
│               frontend (2 replicas)           │
│  StatefulSets: postgres, redis, chromadb      │
│  Ingress: nginx-ingress-controller            │
└──────────────────────────────────────────────┘
```

---

## 2. End-to-End Data Flow

### Step-by-Step Pipeline

```
USER INPUT: "NVDA"
     │
     ▼
[1] TICKER RESOLUTION
     │  yfinance.Ticker("NVDA").info → validate ticker exists
     │  Normalize: "nvidia" → "NVDA"
     │  Check Redis cache: cache:nvda:analysis → HIT (return cached) / MISS (continue)
     │
     ▼
[2] JOB CREATION
     │  POST /api/v1/analyze { ticker: "NVDA" }
     │  Create analysis_run record in PostgreSQL (status=PENDING)
     │  Return job_id to client, open WebSocket channel
     │
     ▼
[3] PARALLEL TASK DISPATCH (Celery)
     │
     ├─► [3a] FINANCIAL DATA TASK (financials_worker)
     │         yfinance: current_price, EPS TTM, revenue TTM
     │         EDGAR API: last 12 quarters of EPS for PE history
     │         Calculate: trailing PE = price / EPS_TTM
     │         Calculate: 3-year median PE from historical quarterly data
     │         → Store in Redis + DB
     │
     ├─► [3b] DOCUMENT DISCOVERY TASK (scrape_worker)
     │         Search sources for guidance documents:
     │           1. SEC EDGAR full-text search (10-Q, 8-K filings)
     │           2. Yahoo Finance earnings page scrape
     │           3. Seeking Alpha earnings transcript (if available)
     │           4. Investor Relations page scrape (company website)
     │           5. Google News RSS: "NVDA earnings guidance"
     │         For each document: download → parse → chunk → embed → store in ChromaDB
     │         → Return document_ids
     │
     ▼
[4] GUIDANCE EXTRACTION TASK (llm_worker)
     │  For each retrieved document:
     │    a. Retrieve top-k relevant chunks from ChromaDB
     │       (query: "EPS guidance revenue guidance next quarter fiscal year")
     │    b. Send chunks + extraction prompt to LLM (Claude claude-sonnet-4-20250514)
     │    c. Parse structured JSON response:
     │       { eps_guidance, revenue_guidance, period, confidence, source_quote }
     │    d. Validate extracted numbers against reasonable bounds
     │    e. Cross-reference multiple sources for consensus
     │  → Deduplicate and rank guidance signals
     │
     ▼
[5] VALUATION CALCULATION (valuation_worker)
     │  Inputs:
     │    - guidance_eps (from LLM extraction)
     │    - median_pe_3yr (from historical data)
     │    - current_price (from yfinance)
     │    - current_eps_ttm (from yfinance/EDGAR)
     │
     │  Calculations:
     │    estimated_price = guidance_eps × median_pe_3yr
     │    upside_pct = (estimated_price - current_price) / current_price × 100
     │    confidence_score = f(source_quality, guidance_clarity,
     │                         eps_deviation_from_consensus, pe_stability)
     │
     │  Alternative valuations (supplementary):
     │    - EV/EBITDA method
     │    - PEG ratio check
     │    - DCF sanity check
     │
     ▼
[6] RESULT ASSEMBLY & STORAGE
     │  Assemble full output object
     │  Store valuation record in PostgreSQL
     │  Cache result in Redis (TTL: 6 hours)
     │  Push update to WebSocket channel → client re-renders
     │
     ▼
[7] FRONTEND RENDER
     │  Dashboard displays:
     │    - Current vs estimated price chart
     │    - PE ratio band chart (3yr history)
     │    - Guidance table with source citations
     │    - Confidence meter
     │    - Upside/downside indicator
     │    - Full source list with links and extracted quotes
```

---

## 3. Recommended Tech Stack

### Full Stack (All Free/Open-Source)

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 18 + Vite 5 | Fast, ecosystem mature |
| **Styling** | TailwindCSS 3 | Utility-first, zero cost |
| **Charts** | Recharts + D3.js | Free, composable |
| **State** | Zustand + React Query | Lightweight, cache-aware |
| **Backend** | FastAPI 0.111 (Python 3.11) | Async, auto docs, fast |
| **ASGI Server** | Uvicorn + Gunicorn | Production-grade |
| **Task Queue** | Celery 5 | Battle-tested async |
| **Message Broker** | Redis 7 | Celery broker + cache |
| **Database** | PostgreSQL 15 | Free, ACID, JSON support |
| **ORM** | SQLAlchemy 2.0 + Alembic | Migrations, type-safe |
| **Vector DB** | ChromaDB (self-hosted) | Free, embedded or server |
| **Embeddings** | sentence-transformers (local) | Free, runs on CPU |
| **LLM** | Anthropic Claude API (paid key) OR OpenAI API (paid key) | Extraction quality |
| **LLM Orchestration** | LangChain 0.2 | RAG pipelines, chains |
| **Financial Data** | yfinance (Yahoo Finance wrapper) | Free, comprehensive |
| **SEC Data** | EDGAR Full-Text Search API (free) | Official SEC data |
| **Web Scraping** | Playwright (async) + httpx | Headless browser, async HTTP |
| **HTML Parsing** | BeautifulSoup4 + lxml | Robust parsing |
| **PDF Parsing** | pdfplumber + pymupdf | Extract text from PDFs |
| **Reverse Proxy** | Nginx | TLS, routing, rate limits |
| **Monitoring** | Prometheus + Grafana | Free, industry standard |
| **Logging** | Loki + Promtail | Free log aggregation |
| **Tracing** | OpenTelemetry + Jaeger | Distributed tracing |
| **Containerization** | Docker + Docker Compose | Dev/staging |
| **Orchestration** | Kubernetes (k3s for self-hosted) | Production |
| **CI/CD** | GitHub Actions | Free tier available |
| **Auth** | FastAPI-Users + JWT | OAuth2, free |
| **Validation** | Pydantic v2 | Request/response models |

### LLM Provider Options (API Key Required)

| Provider | Model | Best For | Cost Estimate |
|---|---|---|---|
| **Anthropic** | claude-sonnet-4-20250514 | Structured extraction, long context | ~$3/MTok |
| **OpenAI** | gpt-4o-mini | Faster, cheaper extraction | ~$0.15/MTok |
| **Ollama** (self-hosted) | llama3.1:70b | Zero API cost, less accurate | Free (GPU needed) |

**Recommendation:** Use claude-sonnet-4-20250514 for primary extraction (long context = full transcripts). Use gpt-4o-mini as fallback. Run Ollama locally for development to avoid API costs.

---

## 4. Guidance Extraction Strategy

### 4.1 Source Priority Hierarchy

```
Priority 1 (Official, Highest Confidence)
├── SEC 8-K filings (press releases with official guidance)
├── SEC 10-Q/10-K filings (management outlook sections)
└── Earnings call transcripts (verbatim management commentary)

Priority 2 (Semi-Official)
├── Investor Day presentations (PDF → text)
├── Company IR page press releases
└── Official Bloomberg/Reuters wire reports

Priority 3 (Derived, Lower Confidence)
├── Analyst consensus from aggregators
├── Financial news articles quoting management
└── SeekingAlpha/Motley Fool summaries
```

### 4.2 Locating Guidance Online

**SEC EDGAR (Primary - Free, Official)**
```python
# EDGAR Full-Text Search API (free, no key required)
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms=8-K,10-Q"

# EDGAR Company Facts API (structured financials)
EDGAR_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

# Example: Fetch recent 8-K filings for NVIDIA
def get_recent_8k_filings(cik: str, days_back: int = 90):
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=10"
    # Returns filing index pages → parse for document links
```

**Yahoo Finance Earnings (Supplementary)**
```python
import yfinance as yf

ticker = yf.Ticker("NVDA")
# Analyst estimates (forward EPS consensus)
estimates = ticker.earnings_estimate
# Quarterly earnings history
quarterly = ticker.quarterly_earnings
# Revenue estimates
revenue_est = ticker.revenue_estimate
```

**Google News RSS (Discovery)**
```python
import feedparser

def search_guidance_news(ticker: str, company: str) -> list[dict]:
    query = f"{company} earnings guidance EPS revenue forecast"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    return [{"title": e.title, "link": e.link, "published": e.published}
            for e in feed.entries[:10]]
```

### 4.3 Extracting EPS/Revenue Guidance from Unstructured Text

**LLM Extraction Prompt (structured output)**

```python
GUIDANCE_EXTRACTION_PROMPT = """
You are a financial analyst extracting official management guidance from earnings documents.

DOCUMENT EXCERPT:
{document_chunk}

TASK:
Extract ALL forward-looking guidance statements. For each guidance item found:

1. Identify the EXACT metric (EPS, revenue, gross margin, operating income, etc.)
2. Identify the VALUE (numeric) or RANGE (low-high)
3. Identify the PERIOD (Q1 FY2026, Full Year 2025, Next Quarter, etc.)
4. Assess if this is OFFICIAL COMPANY GUIDANCE or ANALYST ESTIMATE
5. Extract the VERBATIM QUOTE from the source text

Return ONLY valid JSON matching this schema:
{
  "guidance_items": [
    {
      "metric": "EPS" | "Revenue" | "GrossMargin" | "OperatingIncome" | "Other",
      "value_low": <number or null>,
      "value_high": <number or null>,
      "value_midpoint": <number or null>,
      "unit": "USD" | "USD_billions" | "percent" | "USD_millions",
      "period": "<string: quarter/year descriptor>",
      "fiscal_year": <integer or null>,
      "fiscal_quarter": <integer or null>,  // 1-4
      "calendar_year": <integer or null>,
      "is_official_guidance": <boolean>,  // true = management said it
      "source_quote": "<exact quote from document>",
      "confidence": "high" | "medium" | "low",
      "guidance_type": "initial" | "raised" | "lowered" | "reiterated" | "withdrawn"
    }
  ],
  "document_type": "earnings_call" | "8-K" | "10-Q" | "press_release" | "news_article",
  "company_name": "<string>",
  "reporting_period": "<string>",
  "extraction_notes": "<any ambiguities or caveats>"
}

CRITICAL RULES:
- ONLY extract statements made by company management, not analysts
- If a number appears as "$X.XX billion", convert to numeric (e.g., 28.5 for $28.5B in billions)
- If range given (e.g., "$X.X to $X.X"), populate both value_low and value_high
- Do NOT invent or infer guidance not explicitly stated
- Mark analyst estimates as is_official_guidance: false
"""
```

### 4.4 Distinguishing Official Guidance from Analyst Speculation

**Rule-based Pre-filtering**

```python
MANAGEMENT_INDICATORS = [
    "we expect", "we guide", "we anticipate", "we project",
    "our guidance", "we are raising", "we are lowering",
    "we now expect", "we continue to expect", "outlook",
    "CFO:", "CEO:", "management expects", "company expects",
    "for the [quarter/year], we expect"
]

ANALYST_INDICATORS = [
    "analyst consensus", "wall street expects", "estimates suggest",
    "analysts project", "consensus estimate", "FactSet consensus",
    "Bloomberg consensus", "we estimate", "we model"  # analyst "we"
]

def classify_guidance_source(text_chunk: str) -> str:
    text_lower = text_chunk.lower()
    mgmt_score = sum(1 for phrase in MANAGEMENT_INDICATORS if phrase in text_lower)
    analyst_score = sum(1 for phrase in ANALYST_INDICATORS if phrase in text_lower)
    if mgmt_score > analyst_score:
        return "official"
    elif analyst_score > mgmt_score:
        return "analyst"
    return "ambiguous"
```

### 4.5 Identifying Guidance Periods

```python
import re
from datetime import datetime

PERIOD_PATTERNS = [
    # Full year patterns
    (r"(?:fiscal|fy)?\s*20(\d{2})", "full_year"),
    (r"full[- ]year\s*20(\d{2})", "full_year"),
    # Quarter patterns
    (r"q([1-4])\s*(?:fiscal|fy)?\s*20(\d{2})", "quarter"),
    (r"(?:first|second|third|fourth)\s+quarter\s*(?:of\s*)?20(\d{2})", "quarter"),
    # Next quarter/year
    (r"next\s+quarter", "next_quarter"),
    (r"next\s+(?:fiscal\s+)?year", "next_year"),
]

def parse_guidance_period(text: str, report_date: datetime) -> dict:
    """
    Returns structured period: {type, fiscal_year, quarter, calendar_start, calendar_end}
    """
    ...
```

### 4.6 Handling Conflicting Estimates

**Conflict Resolution Algorithm**

```python
def resolve_guidance_conflicts(extractions: list[GuidanceExtraction]) -> GuidanceExtraction:
    """
    Priority: official > semi-official > analyst
    Among equals: most recent > older
    For ranges: prefer narrower range (more specific)
    For point estimates: weighted median by source quality score
    """
    # Step 1: Filter to official only (if available)
    official = [e for e in extractions if e.is_official_guidance]
    pool = official if official else extractions

    # Step 2: Sort by recency
    pool.sort(key=lambda x: x.document_date, reverse=True)

    # Step 3: For EPS guidance, take weighted median
    eps_values = [e.guidance_eps for e in pool if e.guidance_eps]
    weights = [SOURCE_QUALITY_WEIGHTS[e.source_type] for e in pool if e.guidance_eps]
    consensus_eps = weighted_median(eps_values, weights)

    # Step 4: Calculate standard deviation → used in confidence score
    eps_std = np.std(eps_values)
    confidence_adjustment = max(0, 1 - (eps_std / consensus_eps))

    return GuidanceExtraction(
        eps=consensus_eps,
        eps_range=(min(eps_values), max(eps_values)),
        confidence_adjustment=confidence_adjustment,
        sources=[e.source_url for e in pool]
    )

SOURCE_QUALITY_WEIGHTS = {
    "SEC_8K": 1.0,
    "SEC_10Q": 1.0,
    "earnings_call_transcript": 0.95,
    "press_release": 0.9,
    "investor_day": 0.85,
    "news_article": 0.5,
    "analyst_estimate": 0.3,
}
```

### 4.7 Structuring Extracted Financial Data

**Pydantic Schema**

```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from typing import Optional
from datetime import date

class GuidanceItem(BaseModel):
    metric: str
    value_low: Optional[Decimal] = None
    value_high: Optional[Decimal] = None
    value_midpoint: Optional[Decimal] = None
    unit: str
    period_label: str
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    is_official: bool
    source_url: str
    source_type: str
    source_quote: str
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    guidance_type: str  # initial/raised/lowered/reiterated

    @validator("fiscal_quarter")
    def validate_quarter(cls, v):
        if v is not None and v not in (1, 2, 3, 4):
            raise ValueError("Quarter must be 1-4")
        return v

class GuidanceSummary(BaseModel):
    ticker: str
    company_name: str
    analysis_date: date
    eps_guidance: Optional[GuidanceItem]
    revenue_guidance: Optional[GuidanceItem]
    gross_margin_guidance: Optional[GuidanceItem]
    guidance_period: str
    source_count: int
    overall_confidence: float
    conflict_detected: bool
    all_items: list[GuidanceItem]
```

---

## 5. Financial Valuation Logic

### 5.1 PE Ratio Methodology

**Which PE to Use: Forward vs Trailing**

| Method | Definition | Use Case | Drawback |
|---|---|---|---|
| **Trailing PE (TTM)** | Price ÷ EPS (last 12 months) | Backward-looking baseline | Lags actual performance |
| **Forward PE** | Price ÷ Estimated EPS (next 12m) | Market's expectation | Analyst estimates vary |
| **Normalized PE** | Price ÷ Avg EPS over cycle | Cyclical companies | Smooths distortions |
| **Shiller CAPE** | Price ÷ 10yr Avg Real EPS | Long-term valuation | Too long for growth stocks |

**Recommendation for this system:**
- Use **trailing PE** for the historical median calculation (objective, auditable)
- Use **forward PE** (implied from guidance) for the target price estimate
- Cross-validate with a **5-year median PE** (not 3-year) for growth stocks like semiconductors where 3 years may include anomalous COVID periods

### 5.2 Calculating Historical Median PE

```python
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

def calculate_historical_median_pe(
    ticker: str,
    years: int = 5,
    method: str = "quarterly"  # or "monthly"
) -> dict:
    """
    Calculate median PE using historical price and EPS data.
    
    For each historical date:
      PE = Price / TTM_EPS_at_that_date
    
    Returns median, mean, 25th/75th percentile, and raw series.
    """
    stock = yf.Ticker(ticker)

    # Get quarterly EPS history (actual reported)
    income_stmt = stock.quarterly_income_stmt
    # Get price history
    end = datetime.today()
    start = end - timedelta(days=365 * years)
    prices = stock.history(start=start, end=end, interval="1mo")["Close"]

    # Build rolling TTM EPS for each price date
    pe_series = []
    for date, price in prices.items():
        # Sum last 4 quarters of EPS up to this date
        historical_eps = sum_ttm_eps_as_of(date, income_stmt)
        if historical_eps and historical_eps > 0:
            pe_series.append(price / historical_eps)

    if not pe_series:
        return None

    return {
        "median_pe": float(np.median(pe_series)),
        "mean_pe": float(np.mean(pe_series)),
        "p25_pe": float(np.percentile(pe_series, 25)),
        "p75_pe": float(np.percentile(pe_series, 75)),
        "min_pe": float(np.min(pe_series)),
        "max_pe": float(np.max(pe_series)),
        "observations": len(pe_series),
        "years_used": years,
        "pe_series": [(d.isoformat(), pe) for d, pe in zip(prices.index, pe_series)]
    }
```

**Why 5 Years vs 3 Years:**
- 3 years may over-weight COVID distortions (2020-2022) or post-rate-hike compression
- 5 years captures a fuller business cycle
- For high-growth tech: consider capping median PE at sector benchmark if historical PE was suppressed by one-time charges

### 5.3 Estimated Future Share Price

```python
def calculate_estimated_price(
    guidance_eps: float,
    median_pe: float,
    current_price: float,
    current_eps_ttm: float
) -> ValuationResult:
    """
    Core formula: Estimated Price = Guidance EPS × Historical Median PE
    """
    # Primary valuation
    estimated_price = guidance_eps * median_pe

    # Bull/bear case using PE percentile bands
    bull_price = guidance_eps * median_pe_p75  # 75th percentile PE
    bear_price = guidance_eps * median_pe_p25  # 25th percentile PE

    # Upside/downside
    upside_pct = (estimated_price - current_price) / current_price * 100

    # Current implied PE (for sanity check)
    current_pe = current_price / current_eps_ttm if current_eps_ttm > 0 else None

    return ValuationResult(
        estimated_price=round(estimated_price, 2),
        bull_price=round(bull_price, 2),
        bear_price=round(bear_price, 2),
        upside_pct=round(upside_pct, 2),
        current_pe=current_pe,
        pe_used=median_pe,
        method="guided_eps_x_median_pe"
    )
```

### 5.4 Handling Negative EPS Companies

```python
def handle_negative_eps(ticker: str, guidance_summary: GuidanceSummary) -> ValuationResult:
    """
    When EPS is negative, PE-based valuation is meaningless.
    Fall back to alternative methods:
    """
    if guidance_summary.eps_guidance and guidance_summary.eps_guidance.value_midpoint < 0:
        # Method 1: Price/Sales ratio
        ps_result = price_to_sales_valuation(ticker)

        # Method 2: EV/Revenue
        ev_revenue_result = ev_revenue_valuation(ticker)

        # Method 3: Path to profitability timeline
        path_result = path_to_profitability_valuation(ticker, guidance_summary)

        return ValuationResult(
            method="ps_ratio",  # primary fallback
            estimated_price=ps_result.estimated_price,
            alternative_methods=[ev_revenue_result, path_result],
            caveat="EPS is negative; PE-based valuation inapplicable. Using P/S ratio."
        )
```

### 5.5 Alternative Valuation Methods

| Method | Formula | When to Use | Free Data Source |
|---|---|---|---|
| **P/S Ratio** | Price × Shares / Revenue | Negative EPS companies | yfinance |
| **EV/EBITDA** | Enterprise Value / EBITDA | Capital-intensive businesses | yfinance + EDGAR |
| **PEG Ratio** | PE / EPS Growth Rate | Growth stocks | Derived from guidance |
| **DCF (simplified)** | PV of projected free cash flows | Long-term investors | yfinance FCF |
| **Sector Median PE** | Peer group median PE | Company PE unavailable | yfinance peer list |

```python
# PEG check (if PE-based)
def peg_sanity_check(pe: float, eps_growth_rate: float) -> str:
    """PEG < 1: undervalued. PEG 1-2: fair. PEG > 2: expensive."""
    if eps_growth_rate <= 0:
        return "Cannot compute PEG (negative growth)"
    peg = pe / eps_growth_rate
    if peg < 1:
        return f"PEG={peg:.2f}: potentially undervalued"
    elif peg < 2:
        return f"PEG={peg:.2f}: fairly valued"
    else:
        return f"PEG={peg:.2f}: potentially overvalued"
```

---

## 6. LLM/AI Architecture

### 6.1 RAG Pipeline Design

```
RAW DOCUMENT
     │
     ▼
[1] DOCUMENT PRE-PROCESSING
     │  PDF → text (pdfplumber)
     │  HTML → markdown (markdownify)
     │  Clean: remove headers/footers, fix encoding
     │
     ▼
[2] CHUNKING STRATEGY
     │  Semantic chunking (preferred):
     │    - Split at paragraph boundaries
     │    - Target: 512-800 tokens per chunk
     │    - Overlap: 50-100 tokens (preserve context)
     │    - Special: Never split mid-sentence
     │  Special handling:
     │    - Q&A sections: keep question+answer together
     │    - Tables: serialize as markdown table
     │    - Numbered lists: keep together
     │
     ▼
[3] EMBEDDING GENERATION
     │  Model: all-MiniLM-L6-v2 (sentence-transformers, free, CPU-capable)
     │  Or: bge-large-en-v1.5 (better quality, more RAM)
     │  Dimension: 384 (MiniLM) or 1024 (BGE)
     │  Batch embedding for efficiency
     │
     ▼
[4] VECTOR STORAGE (ChromaDB)
     │  Collection per ticker per document_type
     │  Metadata: ticker, date, doc_type, source_url, chunk_index
     │
     ▼
[5] RETRIEVAL
     │  Query: "EPS guidance revenue guidance next quarter fiscal year {ticker}"
     │  Top-k: 8 chunks (enough for context, not too much)
     │  Reranking: cross-encoder/ms-marco-MiniLM-L-6-v2 (free)
     │  Filter by metadata: date > 90 days ago, doc_type in [earnings_call, 8K]
     │
     ▼
[6] LLM GENERATION (Claude claude-sonnet-4-20250514)
     │  Structured extraction with function calling / JSON mode
     │  Temperature: 0 (deterministic, financial data)
     │  Max tokens: 1000 (structured JSON output)
     │
     ▼
[7] VALIDATION & CITATION
     │  Validate JSON structure (Pydantic)
     │  Validate numbers against yfinance actuals (±50% bounds check)
     │  Map source_quote back to original document (citation)
     │  Return result with chunk_id + source_url + page_number
```

### 6.2 Chunking Strategy (Detailed)

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

def create_financial_chunker():
    """
    Earnings call transcripts need special handling:
    - Keep speaker labels with their content
    - Preserve Q&A pairs
    - Don't split numbers across chunks
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=800,      # tokens
        chunk_overlap=100,
        length_function=token_count,
        separators=[
            "\n\n",          # paragraph boundary (primary)
            "\n",            # line boundary
            ". ",            # sentence boundary
            ", ",            # clause boundary
            " ",             # word boundary (last resort)
        ]
    )

def chunk_earnings_call(transcript: str) -> list[dict]:
    """Specialized chunker that respects speaker boundaries"""
    # Split by speaker turns first
    speaker_pattern = re.compile(r'^([A-Z][a-zA-Z\s]+):\s*$', re.MULTILINE)
    turns = speaker_pattern.split(transcript)

    chunks = []
    chunker = create_financial_chunker()

    for i in range(1, len(turns), 2):
        speaker = turns[i].strip()
        content = turns[i+1] if i+1 < len(turns) else ""

        # Tag management vs analyst speech
        role = "management" if any(t in speaker.lower()
                                    for t in ["ceo", "cfo", "president", "officer"])
               else "analyst"

        for chunk in chunker.split_text(content):
            chunks.append({
                "text": f"[{speaker} ({role})]: {chunk}",
                "speaker": speaker,
                "role": role,
                "is_management": role == "management"
            })

    return chunks
```

### 6.3 Hallucination Prevention

**Multi-layer approach:**

```python
class HallucinationGuard:
    """
    Prevent LLM from inventing guidance figures.
    """

    def validate_eps_extraction(
        self,
        extracted_eps: float,
        current_eps_ttm: float,
        peer_eps_range: tuple[float, float]
    ) -> ValidationResult:

        # Rule 1: Guidance shouldn't deviate >200% from current EPS
        if abs(extracted_eps - current_eps_ttm) / abs(current_eps_ttm) > 2.0:
            return ValidationResult(
                valid=False,
                reason=f"Extracted EPS {extracted_eps} deviates >200% from TTM {current_eps_ttm}"
            )

        # Rule 2: Must be within peer range
        if not (peer_eps_range[0] * 0.5 <= extracted_eps <= peer_eps_range[1] * 2.0):
            return ValidationResult(valid=False, reason="Outside peer range")

        # Rule 3: Source quote must contain a number resembling the extracted value
        if not self._quote_contains_value(source_quote, extracted_eps):
            return ValidationResult(valid=False, reason="Source quote doesn't support value")

        return ValidationResult(valid=True)

    def _quote_contains_value(self, quote: str, value: float) -> bool:
        """Check that the source quote actually contains a number near the extracted value"""
        numbers_in_quote = re.findall(r'\$?(\d+\.?\d*)\s*(?:billion|million|B|M)?', quote)
        extracted_numbers = [float(n) for n in numbers_in_quote]
        return any(abs(n - value) / max(abs(value), 1e-9) < 0.05 for n in extracted_numbers)
```

**Additional safeguards:**
- Always extract `source_quote` alongside each number
- Run extraction twice with temperature=0; if results differ, flag as low-confidence
- Cross-validate against yfinance analyst consensus (`ticker.earnings_estimate`)
- Require minimum 2 independent sources to achieve "high" confidence

### 6.4 Confidence Scoring Model

```python
def calculate_confidence_score(
    source_count: int,
    source_quality_scores: list[float],
    eps_std_dev: float,
    eps_consensus: float,
    hallucination_flags: int,
    guidance_type: str,  # initial, raised, lowered, reiterated
    days_since_guidance: int,
) -> float:
    """
    Composite confidence score: 0.0 - 1.0
    """
    score = 0.0

    # Source quality (0-0.4)
    avg_source_quality = np.mean(source_quality_scores) if source_quality_scores else 0
    score += 0.4 * avg_source_quality

    # Source count bonus (0-0.2)
    source_bonus = min(source_count / 3, 1.0)  # max out at 3 sources
    score += 0.2 * source_bonus

    # Consensus tightness (0-0.2): lower std dev = higher confidence
    if eps_consensus and eps_consensus != 0:
        cv = eps_std_dev / abs(eps_consensus)  # coefficient of variation
        consensus_score = max(0, 1 - cv * 5)  # CV of 0.2 → score of 0
    else:
        consensus_score = 0
    score += 0.2 * consensus_score

    # Recency penalty (0-0.1)
    recency_score = max(0, 1 - days_since_guidance / 90)  # 90 days = zero bonus
    score += 0.1 * recency_score

    # Hallucination flag penalty
    score -= hallucination_flags * 0.1

    # Guidance type modifier
    modifiers = {"official": 1.0, "reiterated": 0.95, "raised": 0.9,
                 "lowered": 0.85, "analyst": 0.6, "ambiguous": 0.4}
    score *= modifiers.get(guidance_type, 0.7)

    return max(0.0, min(1.0, score))
```

---

## 7. Database Schema Design

### 7.1 PostgreSQL Schema

```sql
-- ─────────────────────────────────────────────
-- CORE TABLES
-- ─────────────────────────────────────────────

CREATE TABLE stocks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) NOT NULL UNIQUE,
    company_name    VARCHAR(255) NOT NULL,
    cik             VARCHAR(20),           -- SEC CIK number
    exchange        VARCHAR(20),           -- NASDAQ, NYSE, etc.
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    sic_code        VARCHAR(10),
    fiscal_year_end VARCHAR(5),           -- e.g., "01-31" for Jan 31
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stocks_ticker ON stocks(ticker);
CREATE INDEX idx_stocks_cik ON stocks(cik);

-- ─────────────────────────────────────────────

CREATE TABLE analysis_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id        UUID REFERENCES stocks(id),
    ticker          VARCHAR(10) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/running/complete/failed
    triggered_by    VARCHAR(50),                     -- user_id or 'scheduled'
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    task_ids        JSONB,                           -- Celery task IDs
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_runs_stock_id ON analysis_runs(stock_id);
CREATE INDEX idx_runs_status ON analysis_runs(status);

-- ─────────────────────────────────────────────

CREATE TABLE source_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id        UUID REFERENCES stocks(id),
    run_id          UUID REFERENCES analysis_runs(id),
    source_url      TEXT NOT NULL,
    source_type     VARCHAR(50),   -- SEC_8K, SEC_10Q, earnings_call, news_article
    document_title  TEXT,
    document_date   DATE,
    raw_text_path   TEXT,          -- path to stored raw text (filesystem/S3)
    word_count      INTEGER,
    fetch_status    VARCHAR(20),   -- success, failed, partial
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    checksum        VARCHAR(64)    -- SHA-256 for deduplication
);

CREATE UNIQUE INDEX idx_source_docs_checksum ON source_documents(checksum)
    WHERE fetch_status = 'success';

-- ─────────────────────────────────────────────

CREATE TABLE guidance_extractions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID REFERENCES analysis_runs(id),
    source_document_id  UUID REFERENCES source_documents(id),
    stock_id            UUID REFERENCES stocks(id),
    ticker              VARCHAR(10) NOT NULL,

    -- Guidance values
    metric              VARCHAR(50),      -- EPS, Revenue, GrossMargin, etc.
    value_low           NUMERIC(20, 4),
    value_high          NUMERIC(20, 4),
    value_midpoint      NUMERIC(20, 4),
    unit                VARCHAR(30),

    -- Period
    period_label        VARCHAR(100),
    fiscal_year         INTEGER,
    fiscal_quarter      SMALLINT CHECK (fiscal_quarter BETWEEN 1 AND 4),
    calendar_year       INTEGER,
    guidance_period_start DATE,
    guidance_period_end   DATE,

    -- Metadata
    is_official_guidance BOOLEAN DEFAULT FALSE,
    guidance_type       VARCHAR(30),   -- initial/raised/lowered/reiterated/withdrawn
    source_quote        TEXT,          -- verbatim quote from document
    llm_model_used      VARCHAR(50),
    extraction_confidence FLOAT CHECK (extraction_confidence BETWEEN 0 AND 1),

    -- Validation
    validation_passed   BOOLEAN,
    validation_notes    TEXT,

    extracted_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_guidance_stock_metric ON guidance_extractions(stock_id, metric);
CREATE INDEX idx_guidance_period ON guidance_extractions(fiscal_year, fiscal_quarter);

-- ─────────────────────────────────────────────

CREATE TABLE pe_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id        UUID REFERENCES stocks(id),
    date            DATE NOT NULL,
    price           NUMERIC(12, 4),
    eps_ttm         NUMERIC(10, 4),
    pe_ratio        NUMERIC(10, 4),
    data_source     VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);

CREATE INDEX idx_pe_history_stock_date ON pe_history(stock_id, date DESC);

-- ─────────────────────────────────────────────

CREATE TABLE valuations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  UUID REFERENCES analysis_runs(id),
    stock_id                UUID REFERENCES stocks(id),
    ticker                  VARCHAR(10) NOT NULL,

    -- Inputs
    current_price           NUMERIC(12, 4),
    current_eps_ttm         NUMERIC(10, 4),
    current_revenue_ttm     NUMERIC(20, 2),
    guidance_eps            NUMERIC(10, 4),
    guidance_revenue        NUMERIC(20, 2),
    guidance_period         VARCHAR(100),
    median_pe_used          NUMERIC(10, 4),
    pe_years_used           SMALLINT,
    pe_observation_count    INTEGER,

    -- Outputs
    estimated_price         NUMERIC(12, 4),
    bull_price              NUMERIC(12, 4),
    bear_price              NUMERIC(12, 4),
    upside_pct              NUMERIC(8, 2),
    confidence_score        FLOAT,
    valuation_method        VARCHAR(50),

    -- Alternative methods (JSONB)
    alternative_valuations  JSONB,

    -- Quality flags
    negative_eps_flag       BOOLEAN DEFAULT FALSE,
    low_confidence_flag     BOOLEAN DEFAULT FALSE,
    insufficient_data_flag  BOOLEAN DEFAULT FALSE,

    calculated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_valuations_stock ON valuations(stock_id, calculated_at DESC);

-- ─────────────────────────────────────────────
-- SUPPORTING TABLES
-- ─────────────────────────────────────────────

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE watchlists (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    ticker      VARCHAR(10) NOT NULL,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    stock_id        UUID REFERENCES stocks(id),
    alert_type      VARCHAR(50),  -- price_target, new_guidance, confidence_change
    threshold_value NUMERIC,
    is_active       BOOLEAN DEFAULT TRUE,
    last_triggered  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- CACHING METADATA (track what's cached in Redis)
-- ─────────────────────────────────────────────

CREATE TABLE cache_registry (
    cache_key       VARCHAR(255) PRIMARY KEY,
    entity_type     VARCHAR(50),
    entity_id       VARCHAR(50),
    cached_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    data_version    INTEGER DEFAULT 1
);
```

### 7.2 Caching Strategy

```
Redis Key Schema:
  stock:{ticker}:price          TTL: 5 minutes
  stock:{ticker}:financials     TTL: 1 hour
  stock:{ticker}:pe_history     TTL: 24 hours
  stock:{ticker}:guidance       TTL: 6 hours  (refresh after earnings)
  stock:{ticker}:valuation      TTL: 6 hours
  job:{job_id}:status           TTL: 48 hours
  job:{job_id}:result           TTL: 48 hours

Cache Invalidation Events:
  - New 8-K filing detected → invalidate guidance + valuation
  - Price moves >5% in 1 hour → invalidate price cache
  - Manual admin trigger → invalidate any key
```

---

## 8. APIs to Use (Free)

### 8.1 Financial Data APIs

| API | Endpoint | Data Available | Rate Limit | Auth |
|---|---|---|---|---|
| **Yahoo Finance** (yfinance) | Python library | Price, EPS, estimates, history | ~2000/hr | None |
| **SEC EDGAR** | `data.sec.gov/api/xbrl/` | All XBRL financials, 10-K/10-Q/8-K | 10/sec | None (add User-Agent) |
| **SEC EDGAR Full-Text** | `efts.sec.gov/LATEST/search-index` | Search filings by text | 10/sec | None |
| **SEC EDGAR Submissions** | `data.sec.gov/submissions/CIK*.json` | Filing history by company | 10/sec | None |
| **Federal Reserve FRED** | `api.stlouisfed.org/fred/` | Macro data (interest rates, GDP) | 120/min | Free key |
| **Alpha Vantage** | `alphavantage.co/query` | Price history, fundamentals | 25/day (free) | Free key |
| **Stooq** | `stooq.com/q/d/l/` | Price history | Moderate | None |
| **Open Exchange Rates** | `openexchangerates.org` | FX rates | 1000/mo (free) | Free key |

### 8.2 SEC EDGAR API Usage

```python
import httpx
import time

SEC_HEADERS = {
    "User-Agent": "YourAppName admin@yourapp.com",  # Required by SEC
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

class EDGARClient:
    BASE_URL = "https://data.sec.gov"
    SEARCH_URL = "https://efts.sec.gov"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=SEC_HEADERS)
        self.rate_limiter = TokenBucket(rate=10, capacity=10)

    async def get_company_facts(self, cik: str) -> dict:
        """All XBRL financial data for a company"""
        cik_padded = cik.zfill(10)
        url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        await self.rate_limiter.acquire()
        resp = await self.client.get(url)
        return resp.json()

    async def get_eps_history(self, cik: str) -> list[dict]:
        """Extract EPS from XBRL company facts"""
        facts = await self.get_company_facts(cik)
        eps_data = facts["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"]
        # Filter to annual/quarterly form filings
        return [
            {"date": item["end"], "eps": item["val"], "form": item["form"]}
            for item in eps_data
            if item["form"] in ("10-K", "10-Q")
        ]

    async def search_filings(
        self, ticker: str, form_types: list[str], days_back: int = 90
    ) -> list[dict]:
        """Full-text search for recent filings"""
        start_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        forms_param = ",".join(form_types)
        url = (
            f"{self.SEARCH_URL}/LATEST/search-index"
            f"?q=%22{ticker}%22&forms={forms_param}"
            f"&dateRange=custom&startdt={start_date}"
        )
        await self.rate_limiter.acquire()
        resp = await self.client.get(url)
        return resp.json().get("hits", {}).get("hits", [])

    async def get_filing_document(self, accession_number: str, cik: str) -> str:
        """Download actual filing text"""
        acc_formatted = accession_number.replace("-", "")
        cik_padded = cik.zfill(10)
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_formatted}/{accession_number}-index.htm"
        # Parse index to find primary document
        ...
```

### 8.3 yfinance Usage

```python
import yfinance as yf
from functools import lru_cache

class YFinanceClient:

    @lru_cache(maxsize=100)
    def get_stock_info(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        info = stock.info
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
        return yf.Ticker(ticker).history(period=period)

    def get_earnings_estimates(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        return {
            "earnings_estimate": stock.earnings_estimate.to_dict(),
            "revenue_estimate": stock.revenue_estimate.to_dict(),
            "eps_trend": stock.eps_trend.to_dict() if hasattr(stock, 'eps_trend') else {},
        }
```

---

## 9. Web Scraping Architecture

### 9.1 Scraping Pipeline

```
                    ┌─────────────────────┐
                    │  Scrape Task Queued  │
                    │  (Celery)            │
                    └──────────┬──────────┘
                               │
              ┌────────────────▼───────────────────┐
              │        SCRAPE ROUTER               │
              │  Decides strategy per URL type:    │
              │  - SEC.gov → direct httpx (fast)   │
              │  - JS-rendered sites → Playwright  │
              │  - News sites → httpx + parsing    │
              └───┬──────────────────┬─────────────┘
                  │                  │
     ┌────────────▼──────┐  ┌────────▼──────────────┐
     │  httpx Fetcher    │  │  Playwright Fetcher    │
     │  (static HTML)    │  │  (JS-rendered)         │
     │  Retry: 3x        │  │  Headless Chromium     │
     │  Timeout: 30s     │  │  Wait: networkidle     │
     └────────┬──────────┘  └────────┬───────────────┘
              │                      │
              └──────────┬───────────┘
                         │
              ┌──────────▼──────────┐
              │  HTML → Text Parser  │
              │  (BS4 + markdownify) │
              │  PDF → Text          │
              │  (pdfplumber)        │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Content Quality     │
              │  Filter              │
              │  Min 200 words       │
              │  Language = EN       │
              │  Contains financial  │
              │  keywords            │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Deduplication       │
              │  SHA-256 of text     │
              │  Check DB for dups   │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  Store + Embed       │
              │  ChromaDB + PG       │
              └─────────────────────┘
```

### 9.2 Scraping Implementation

```python
import httpx
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import markdownify

class SmartScraper:
    STATIC_DOMAINS = [
        "sec.gov", "edgar.sec.gov", "reuters.com",
        "businesswire.com", "prnewswire.com"
    ]
    JS_DOMAINS = [
        "seekingalpha.com", "fool.com"
    ]

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysisBot/1.0; +https://yourapp.com/bot)",
                "Accept": "text/html,application/xhtml+xml,application/xml",
            }
        )

    async def scrape(self, url: str) -> ScrapedContent:
        domain = urlparse(url).netloc.replace("www.", "")

        if any(d in domain for d in self.STATIC_DOMAINS):
            return await self._httpx_scrape(url)
        elif any(d in domain for d in self.JS_DOMAINS):
            return await self._playwright_scrape(url)
        else:
            # Try httpx first, fall back to playwright
            try:
                result = await self._httpx_scrape(url)
                if result.word_count < 100:  # Likely JS-rendered
                    return await self._playwright_scrape(url)
                return result
            except Exception:
                return await self._playwright_scrape(url)

    async def _httpx_scrape(self, url: str) -> ScrapedContent:
        for attempt in range(3):
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    html = response.text
                    text = self._html_to_text(html)
                    return ScrapedContent(url=url, text=text, method="httpx")
                elif response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except httpx.TimeoutException:
                await asyncio.sleep(1)
        raise ScrapingError(f"Failed to scrape {url} after 3 attempts")

    async def _playwright_scrape(self, url: str) -> ScrapedContent:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # Block images/fonts to speed up
            await page.route("**/*.{png,jpg,gif,svg,woff,woff2}", lambda r: r.abort())

            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()

            text = self._html_to_text(html)
            return ScrapedContent(url=url, text=text, method="playwright")

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        # Remove nav, ads, scripts
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        return markdownify.markdownify(str(soup), heading_style="ATX")
```

### 9.3 Rate Limiting & Anti-Bot

```python
class AdaptiveRateLimiter:
    """Per-domain rate limiting with backoff"""

    DOMAIN_LIMITS = {
        "sec.gov": (10, 1.0),       # 10 req/sec
        "yahoo.com": (5, 1.0),      # 5 req/sec
        "reuters.com": (2, 1.0),    # 2 req/sec
        "seekingalpha.com": (1, 2.0), # 1 req/2sec (aggressive limit)
        "default": (2, 1.0),
    }

    async def acquire(self, domain: str):
        rate, period = self.DOMAIN_LIMITS.get(domain, self.DOMAIN_LIMITS["default"])
        # Token bucket implementation
        ...
```

### 9.4 Legal & Compliance Considerations

```
COMPLIANCE CHECKLIST:
├── robots.txt: Always check and respect before scraping
│     → Parse via urllib.robotparser
├── Terms of Service:
│     → SEC.gov: Public domain, explicitly allows crawling
│     → Yahoo Finance: Terms prohibit commercial scraping (use yfinance library)
│     → SeekingAlpha: Requires subscription for full transcripts
│     → Reuters: Limited free access; don't cache for redistribution
├── GDPR/CCPA: Ensure no personal data stored from scraped content
├── Rate Limiting: Implement polite delays (1-10 sec between requests)
├── Identification: Always include User-Agent with contact info
│     "User-Agent: StockGuidanceBot/1.0 (contact@yourapp.com)"
└── Copyright: Store only metadata + extracted guidance figures, not full text
```

### 9.5 Fallback Strategy

```
For each source type:
  Primary: Direct scrape
  Fallback 1: Cached version from previous run (if <24h old)
  Fallback 2: Alternative source (e.g., Reuters instead of Bloomberg)
  Fallback 3: yfinance analyst estimates (lower confidence)
  Fallback 4: Degrade gracefully (report "insufficient data")
```

---

## 10. Frontend UX/UI Plan

### 10.1 Application Layout

```
┌─────────────────────────────────────────────────────────────┐
│  NAVBAR: [Logo] [Search Bar: Enter ticker or company]  [⚙️] │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│  HERO: Analysis Dashboard — NVDA (NVIDIA Corporation)       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ CURRENT PRICE│  │ EST. PRICE   │  │ UPSIDE/DOWNSIDE  │  │
│  │  $875.40     │  │  $1,124.60   │  │   ▲ +28.5%       │  │
│  │  (live)      │  │  (12mo tgt)  │  │   (base case)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌────────────────────────────────┐  ┌───────────────────┐  │
│  │  CONFIDENCE METER              │  │ GUIDANCE PERIOD   │  │
│  │  ████████░░  78%              │  │ FY2026 Full Year  │  │
│  │  (Based on 4 official sources) │  │ (ends Jan 2026)   │  │
│  └────────────────────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────┬───────────────────────┐
│  PRICE CHART (2yr with PE bands)    │  GUIDANCE TABLE       │
│                                     │                       │
│  $1200                              │  Metric  │ Guidance   │
│  $1000  ┄┄┄est price               │  EPS     │ $X.XX      │
│   $875  ━━━current                  │  Revenue │ $XXB       │
│   $600  ┄┄┄bear case               │  Margin  │ XX%        │
│                                     │                       │
│  PE Band:                           │  Period: FY2026       │
│  ─ Median 5yr PE: 48.3x            │  Type: Raised ▲       │
│  ─ 25th pct: 32.1x                 │                       │
│  ─ 75th pct: 61.4x                 │  [See All Sources ↗]  │
└─────────────────────────────────────┴───────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│  KEY METRICS                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │EPS (TTM) │ │Fwd EPS   │ │P/E (TTM) │ │Fwd P/E   │       │
│  │ $1.69    │ │ $2.48    │ │ 51.7x    │ │ 35.3x    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐                                  │
│  │Revenue   │ │Mkt Cap   │                                  │
│  │ $96.3B   │ │ $2.14T   │                                  │
│  └──────────┘ └──────────┘                                  │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│  VALUATION SCENARIOS                                        │
│                                                             │
│           Bear      Base      Bull                          │
│           $690      $1,125    $1,380                        │
│  Price: ───┼──────────●──────────────►                      │
│            ▲current                                         │
│           $875                                              │
│                                                             │
│  Bear: 25th pct PE (32.1x) × Guidance EPS                  │
│  Base: Median PE (48.3x) × Guidance EPS                     │
│  Bull: 75th pct PE (61.4x) × Guidance EPS                  │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│  SOURCE EVIDENCE & CITATIONS                                │
│                                                             │
│  [✓] SEC 8-K (Nov 20, 2024) — HIGH CONFIDENCE             │
│      "For fiscal year 2026, we expect revenue of           │
│       approximately $XXX billion..."                        │
│      → [View Filing ↗]  [See Full Excerpt]                  │
│                                                             │
│  [✓] Earnings Call Q3 FY25 (Nov 20, 2024) — HIGH          │
│      "[CFO name]: Our guidance for next year..."            │
│      → [View Transcript ↗]                                  │
│                                                             │
│  [~] Yahoo Finance Analyst Consensus — MEDIUM              │
│      EPS estimate: $X.XX (27 analysts)                     │
│      → [View ↗]                                             │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────────────────────────────────────────────┐
│  GUIDANCE HISTORY (click to expand)                         │
│  Q1 FY25  Q2 FY25  Q3 FY25  Q4 FY25  Current              │
│  $X.XX    $X.XX    $X.XX    $X.XX    $X.XX  (EPS guidance) │
│  ▲+3%     ▲+8%     ▲+12%   ▲+15%   ▲+22%  (raises)       │
└─────────────────────────────────────────────────────────────┘
│
└───────── [♡ Add to Watchlist] [↺ Refresh] [⬇ Export CSV] ──┘
```

### 10.2 React Component Architecture

```
src/
├── components/
│   ├── Search/
│   │   ├── SearchBar.jsx          # Autocomplete ticker search
│   │   └── RecentSearches.jsx
│   ├── Dashboard/
│   │   ├── DashboardLayout.jsx    # Main grid layout
│   │   ├── PriceSummaryCard.jsx   # Current / Est / Upside cards
│   │   ├── ConfidenceMeter.jsx    # Animated confidence gauge
│   │   └── GuidancePeriodBadge.jsx
│   ├── Charts/
│   │   ├── PriceWithPEBands.jsx   # Recharts: price + PE overlay
│   │   ├── ValuationScenarios.jsx # Bear/base/bull range chart
│   │   ├── PEHistoryChart.jsx     # Historical PE bar chart
│   │   └── GuidanceHistory.jsx   # Timeline of raised/lowered guidance
│   ├── Guidance/
│   │   ├── GuidanceTable.jsx      # EPS/Revenue/Margin table
│   │   ├── SourceCard.jsx         # Individual source with quote
│   │   └── SourceList.jsx
│   ├── Metrics/
│   │   └── KeyMetricsGrid.jsx     # EPS, P/E, Revenue cards
│   └── Common/
│       ├── LoadingSpinner.jsx
│       ├── ErrorBoundary.jsx
│       └── TooltipWrapper.jsx
├── hooks/
│   ├── useAnalysis.js             # React Query + WebSocket
│   ├── useWatchlist.js
│   └── useRealTimePrice.js        # WebSocket price updates
├── store/
│   └── useAppStore.js             # Zustand global state
├── api/
│   └── client.js                  # Axios instance + interceptors
└── pages/
    ├── Home.jsx
    ├── Analysis.jsx
    ├── Watchlist.jsx
    └── History.jsx
```

### 10.3 Real-Time Updates (WebSocket)

```javascript
// useAnalysis.js
import { useEffect, useState } from "react";

export function useAnalysis(ticker) {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [jobId, setJobId] = useState(null);

  const startAnalysis = async () => {
    setStatus("loading");
    const response = await api.post("/api/v1/analyze", { ticker });
    setJobId(response.data.job_id);
  };

  useEffect(() => {
    if (!jobId) return;

    // WebSocket for real-time progress
    const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${jobId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "progress") {
        setStatus(data.stage);  // "fetching_data", "extracting", "calculating"
      } else if (data.type === "complete") {
        setResult(data.result);
        setStatus("complete");
        ws.close();
      } else if (data.type === "error") {
        setStatus("error");
        ws.close();
      }
    };

    return () => ws.close();
  }, [jobId]);

  return { startAnalysis, status, result };
}
```

---

## 11. Scalability Considerations

### 11.1 Async Processing Architecture

```python
# celery_app.py
from celery import Celery
from kombu import Queue

app = Celery("stock_guidance")

app.config_from_object({
    "broker_url": "redis://redis:6379/0",
    "result_backend": "redis://redis:6379/1",
    "task_queues": [
        Queue("financials", routing_key="financials"),  # Fast, CPU-bound
        Queue("scraping", routing_key="scraping"),       # I/O bound
        Queue("llm", routing_key="llm"),                 # API calls, rate-limited
        Queue("valuation", routing_key="valuation"),     # CPU-bound, fast
    ],
    "task_routes": {
        "tasks.fetch_financials": {"queue": "financials"},
        "tasks.scrape_sources": {"queue": "scraping"},
        "tasks.extract_guidance": {"queue": "llm"},
        "tasks.calculate_valuation": {"queue": "valuation"},
    },
    "worker_concurrency": {
        "financials": 10,   # High concurrency (yfinance is fast)
        "scraping": 5,      # Medium (I/O + network)
        "llm": 3,           # Low (API rate limits)
        "valuation": 10,    # High (pure CPU calc)
    },
    "task_soft_time_limit": 120,  # 2 min warning
    "task_time_limit": 180,       # 3 min kill
    "task_acks_late": True,        # Only ack after task succeeds
    "task_reject_on_worker_lost": True,
})
```

### 11.2 Caching Strategy (Tiered)

```
L1: In-process Python dict cache (functools.lru_cache)
    → Ticker validation, sector lookups
    → TTL: process lifetime
    → Size: ~1000 entries

L2: Redis (hot data)
    → Stock prices, current financials, valuations
    → TTL: 5min - 24hrs depending on volatility
    → Size: ~10GB RAM per Redis instance

L3: PostgreSQL (warm data)
    → Historical PE series, guidance history
    → Index-optimized queries
    → Size: unlimited disk

L4: Filesystem/S3 (cold data)
    → Raw scraped text (de-duplicated by hash)
    → Processed embeddings cache
    → Size: unlimited
```

### 11.3 Queue System Design

```
                     API Server
                         │
                    POST /analyze
                         │
              ┌──────────▼──────────────┐
              │   Redis Task Queue       │
              │   (Celery Broker)        │
              └──────┬────────┬──────────┘
                     │        │
         ┌───────────▼──┐  ┌──▼────────────┐
         │  financials  │  │   scraping    │
         │  workers(5)  │  │   workers(5)  │
         └──────────────┘  └───────────────┘
                  │                │
         ┌────────▼────────────────▼──────┐
         │       llm workers (3)          │
         │    (LLM extraction tasks)      │
         └────────────────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │    valuation workers (5)       │
         └────────────────────────────────┘
                         │
              WebSocket PUSH to client
```

### 11.4 Cost Optimization

| Component | Free Option | Cost Estimate |
|---|---|---|
| LLM Extraction | Ollama (llama3.1 local) | $0 (GPU server ~$50/mo) |
| LLM Extraction | Claude claude-sonnet-4-20250514 | ~$0.003/analysis |
| Embeddings | sentence-transformers (local CPU) | $0 |
| Stock Data | yfinance | $0 |
| SEC Data | EDGAR API | $0 |
| Database | PostgreSQL self-hosted | $0 (hosting only) |
| Vector DB | ChromaDB self-hosted | $0 (hosting only) |
| Infrastructure | k3s on Hetzner/DigitalOcean | ~$20-50/mo |

**LLM Cost Per Analysis:**
- Claude claude-sonnet-4-20250514 @ $3/MTok input, $15/MTok output
- ~8 chunks × 800 tokens = 6,400 tokens input
- ~500 tokens output per chunk = 4,000 tokens output
- Total: ~$0.02-0.08 per full analysis (depending on source count)

---

## 12. Security & Reliability

### 12.1 API Key Management

```python
# config.py - NEVER hardcode secrets
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    postgres_url: str
    redis_url: str
    secret_key: str  # JWT signing
    fred_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Docker: mount secrets as env vars, never in image
# Kubernetes: use Kubernetes Secrets or HashiCorp Vault
# Development: .env file (gitignored)
```

### 12.2 Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True
)
async def fetch_with_retry(url: str) -> str:
    response = await http_client.get(url)
    response.raise_for_status()
    return response.text

# LLM retry with rate limit handling
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=1, max=60),
    retry=retry_if_exception_type(RateLimitError),
)
async def call_llm_with_retry(prompt: str) -> str:
    ...
```

### 12.3 Input Validation

```python
from pydantic import BaseModel, validator
import re

class AnalysisRequest(BaseModel):
    ticker: str
    force_refresh: bool = False

    @validator("ticker")
    def validate_ticker(cls, v):
        ticker = v.strip().upper()
        # Only allow alphanumeric, dot, dash (e.g., BRK.B, BRK-B)
        if not re.match(r'^[A-Z0-9.\-]{1,10}$', ticker):
            raise ValueError("Invalid ticker format")
        return ticker
```

### 12.4 Error Handling Strategy

```python
# Structured error responses
class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code

ERROR_REGISTRY = {
    "TICKER_NOT_FOUND": AppError("TICKER_NOT_FOUND", "Ticker not found", 404),
    "INSUFFICIENT_DATA": AppError("INSUFFICIENT_DATA", "Not enough data to calculate valuation", 422),
    "LLM_FAILURE": AppError("LLM_FAILURE", "AI extraction failed, using fallback", 207),
    "SCRAPING_BLOCKED": AppError("SCRAPING_BLOCKED", "Source blocked scraping", 503),
}

# Graceful degradation: if LLM fails, fall back to yfinance analyst consensus
async def extract_guidance_with_fallback(ticker: str, docs: list) -> GuidanceSummary:
    try:
        return await llm_extract_guidance(ticker, docs)
    except LLMError:
        logger.warning(f"LLM extraction failed for {ticker}, using analyst consensus")
        return await get_analyst_consensus_fallback(ticker)
```

### 12.5 Observability Stack

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics

  - job_name: 'celery'
    static_configs:
      - targets: ['flower:5555']  # Celery Flower monitoring
```

```python
# metrics.py - Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

ANALYSIS_COUNTER = Counter("analyses_total", "Total analyses run", ["ticker", "status"])
ANALYSIS_DURATION = Histogram("analysis_duration_seconds", "Time per analysis")
LLM_COST_COUNTER = Counter("llm_tokens_used_total", "LLM tokens consumed", ["model"])
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["cache_type"])
GUIDANCE_CONFIDENCE = Histogram("guidance_confidence_score", "Distribution of confidence scores")
```

---

## 13. Production Deployment Plan

### 13.1 Folder Structure

```
stock-guidance-platform/
├── frontend/                    # React application
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── analysis.py      # POST /analyze, GET /analysis/{id}
│   │   │   │   ├── stocks.py        # GET /stocks/{ticker}
│   │   │   │   ├── watchlist.py
│   │   │   │   └── auth.py
│   │   │   └── websocket.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── redis_client.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── stock.py
│   │   │   ├── guidance.py
│   │   │   ├── valuation.py
│   │   │   └── user.py
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ticker_service.py
│   │   │   ├── guidance_service.py
│   │   │   ├── valuation_service.py
│   │   │   └── confidence_service.py
│   │   ├── tasks/               # Celery tasks
│   │   │   ├── celery_app.py
│   │   │   ├── financial_tasks.py
│   │   │   ├── scraping_tasks.py
│   │   │   ├── llm_tasks.py
│   │   │   └── valuation_tasks.py
│   │   ├── ingestion/           # Data fetchers
│   │   │   ├── edgar_client.py
│   │   │   ├── yfinance_client.py
│   │   │   ├── scraper.py
│   │   │   └── rss_client.py
│   │   ├── ai/                  # AI/LLM layer
│   │   │   ├── llm_gateway.py
│   │   │   ├── prompts.py
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py
│   │   │   ├── rag_pipeline.py
│   │   │   └── hallucination_guard.py
│   │   └── main.py
│   ├── alembic/                 # DB migrations
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── backtest/
│   └── requirements.txt
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.frontend
│   ├── docker-compose.yml       # Dev environment
│   ├── docker-compose.prod.yml  # Production compose
│   └── kubernetes/
│       ├── namespace.yaml
│       ├── deployments/
│       ├── services/
│       ├── configmaps/
│       ├── secrets/             # Sealed Secrets
│       └── ingress.yaml
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── loki/
│       └── loki-config.yaml
│
├── scripts/
│   ├── backtest.py              # Historical valuation validation
│   ├── seed_data.py
│   └── migrate.sh
│
├── .github/
│   └── workflows/
│       ├── test.yml
│       ├── build.yml
│       └── deploy.yml
│
├── docker-compose.yml
├── .env.example
└── README.md
```

### 13.2 Docker Compose (Development)

```yaml
version: "3.9"
services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
    depends_on: [api, frontend]

  api:
    build:
      context: ./backend
      dockerfile: ../infra/docker/Dockerfile.api
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - chromadb
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker-financials:
    build:
      context: ./backend
      dockerfile: ../infra/docker/Dockerfile.worker
    env_file: .env
    command: celery -A app.tasks.celery_app worker -Q financials -c 10
    depends_on: [redis, postgres]

  worker-scraping:
    build:
      context: ./backend
      dockerfile: ../infra/docker/Dockerfile.worker
    env_file: .env
    command: celery -A app.tasks.celery_app worker -Q scraping -c 5
    depends_on: [redis, postgres]

  worker-llm:
    build:
      context: ./backend
      dockerfile: ../infra/docker/Dockerfile.worker
    env_file: .env
    command: celery -A app.tasks.celery_app worker -Q llm -c 3
    depends_on: [redis, postgres]

  worker-valuation:
    build:
      context: ./backend
      dockerfile: ../infra/docker/Dockerfile.worker
    env_file: .env
    command: celery -A app.tasks.celery_app worker -Q valuation -c 10
    depends_on: [redis, postgres]

  flower:
    image: mher/flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0

  postgres:
    image: postgres:15-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: stockguidance
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chromadata:/chroma/chroma

  frontend:
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    depends_on: [prometheus]

volumes:
  pgdata:
  redisdata:
  chromadata:
```

### 13.3 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install -r backend/requirements.txt
          pytest backend/tests/ -v --cov=app

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: |
          docker build -t stockguidance/api:${{ github.sha }} -f infra/docker/Dockerfile.api ./backend
          docker build -t stockguidance/worker:${{ github.sha }} -f infra/docker/Dockerfile.worker ./backend
          docker build -t stockguidance/frontend:${{ github.sha }} ./frontend

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to k3s
        run: |
          # Update image tags in k8s manifests
          kubectl set image deployment/api api=stockguidance/api:${{ github.sha }}
          kubectl set image deployment/worker worker=stockguidance/worker:${{ github.sha }}
          kubectl rollout status deployment/api
```

---

## 14. MVP vs Production Roadmap

### Phase 1: MVP (4-6 weeks)

**Goal:** Working analysis for S&P 500 large-caps with manual trigger

| Feature | Description | Priority |
|---|---|---|
| Ticker search | Resolve ticker + basic info | P0 |
| yfinance data | Current price, TTM EPS, revenue | P0 |
| EDGAR 8-K fetch | Download recent press releases | P0 |
| LLM extraction | Extract EPS/revenue guidance | P0 |
| PE calculation | 3-year median PE (simplified) | P0 |
| Valuation output | Price estimate + upside % | P0 |
| Source display | Show where guidance came from | P0 |
| Basic UI | Dashboard with key metrics | P0 |
| Confidence score | Basic confidence calculation | P1 |
| Bull/bear range | PE percentile bands | P1 |

**MVP Tech:** FastAPI + React + PostgreSQL + Redis + yfinance + EDGAR + Claude API

### Phase 2: Production (Weeks 7-16)

| Feature | Description |
|---|---|
| Earnings call transcripts | Full Playwright scraping + parsing |
| RAG pipeline | ChromaDB + sentence-transformers |
| Hallucination guards | Validation + cross-referencing |
| Watchlist + alerts | User accounts, price target alerts |
| Historical guidance | Track guidance changes over time |
| Alternative valuations | P/S, EV/EBITDA for negative EPS |
| Scheduled refresh | Auto-re-analyze after earnings |
| Performance backtesting | Validate past valuation accuracy |
| Export (CSV/PDF) | Download analysis reports |
| Kubernetes deploy | Production-grade scaling |

### Phase 3: Enterprise (Months 4-8)

| Feature | Description |
|---|---|
| Agent workflow | Auto-monitor watchlist, trigger alerts |
| Multi-metric guidance | Segment guidance, margin guidance |
| Sector comparison | Peer group PE analysis |
| Earnings calendar | Auto-trigger before earnings dates |
| Portfolio-level analysis | Aggregate across holdings |
| API access | Expose as B2B API with auth |
| Backtesting dashboard | Historical accuracy metrics |
| Audit trail | Full governance for institutional use |
| Multi-LLM consensus | Run extraction on multiple models, vote |
| On-premise LLM | Ollama + fine-tuned model for guidance extraction |

### Backtesting Framework

```python
# scripts/backtest.py
def backtest_valuation_accuracy(
    ticker: str,
    start_date: str,
    end_date: str
) -> BacktestResult:
    """
    For each historical quarter:
    1. Simulate what guidance was available at earnings date
    2. Run valuation calculation
    3. Compare estimated price to actual price 3/6/12 months later
    4. Calculate accuracy metrics: MAPE, directional accuracy, Sharpe
    """
    # Load historical guidance_extractions from DB
    # Load historical valuations
    # Load actual price history from yfinance
    # Calculate prediction error for each time horizon
    # Return: {MAPE_3m, MAPE_6m, MAPE_12m, directional_accuracy, sample_size}
```

---

## 15. End-to-End Walkthrough: NVIDIA (NVDA)

**Scenario:** User types "NVDA" on November 21, 2024 (day after Q3 FY2025 earnings)

### Step 1: Ticker Resolution (0-1s)
```
Input: "NVDA"
yfinance.Ticker("NVDA").info returns:
  company_name: "NVIDIA Corporation"
  cik: "0001045810"
  sector: "Technology"
  industry: "Semiconductors"
  fiscal_year_end: "January"  (NVDA's FY ends in January)

Cache check: Redis MISS → proceed with fresh analysis
Create analysis_run_id: "run_abc123"
WebSocket channel opened for client
```

### Step 2: Parallel Data Fetch (1-8s)

**Financial data (yfinance):**
```
current_price: $875.40
eps_ttm: $1.69 (sum of Q4FY24 $0.44 + Q1FY25 $0.40 + Q2FY25 $0.68 + Q3FY25 $0.17... adjusted)
revenue_ttm: ~$96.3B
forward_eps (analyst consensus): $2.48
```

**EDGAR fetch:**
```
8-K filed: 2024-11-20 (Q3 FY2025 earnings press release)
URL: https://www.sec.gov/Archives/edgar/data/1045810/...
Status: SUCCESS
Document: 28-page press release + full financial tables
```

**Google News RSS:**
```
Query: "NVIDIA NVDA earnings guidance FY2026"
Results: 8 recent articles from Reuters, Bloomberg, CNBC
Filtered to: 4 relevant articles
```

### Step 3: Document Processing (3-15s)

**8-K Document:**
```
PDF → text: 4,200 words
Chunking: 12 chunks (avg 350 tokens each)
Embedding: all-MiniLM-L6-v2 → 384-dim vectors
Stored in ChromaDB collection: "nvda_2024_11_20_8K"
```

**Earnings Call Transcript** (if available):
```
Source: Scraped from Seeking Alpha free excerpt OR
        fetched from SEC directly (some companies file transcripts)
Chunking: 45 chunks (earnings calls are long)
Tagged: CFO/CEO speech = is_management: true
```

### Step 4: Guidance Extraction (8-20s)

**RAG Query:**
```
Query: "NVIDIA FY2026 revenue guidance EPS guidance next year forecast"
Retrieved chunks (top-8 by cosine similarity, reranked):

Chunk 1 (score: 0.94, management=true):
"[CFO Colette Kress]: For the fourth quarter of fiscal 2025, we expect
 revenue to be $37.5 billion, plus or minus 2%..."

Chunk 2 (score: 0.91, management=true):
"We are raising our fiscal 2025 full-year revenue outlook to approximately
 $129 billion..."

Chunk 3 (score: 0.88, management=true):
"Non-GAAP EPS for Q4 FY25 is expected to be..."
```

**LLM Extraction (Claude):**
```json
{
  "guidance_items": [
    {
      "metric": "Revenue",
      "value_low": 36.75,
      "value_high": 38.25,
      "value_midpoint": 37.5,
      "unit": "USD_billions",
      "period_label": "Q4 FY2025",
      "fiscal_year": 2025,
      "fiscal_quarter": 4,
      "is_official_guidance": true,
      "source_quote": "revenue to be $37.5 billion, plus or minus 2%",
      "confidence": "high",
      "guidance_type": "initial"
    }
  ],
  "document_type": "8-K",
  "company_name": "NVIDIA Corporation"
}
```

**Hallucination Validation:**
```
Extracted revenue: $37.5B
TTM revenue: $96.3B → Quarterly run rate: $24.1B
$37.5B is 55% above prior quarter run rate → PLAUSIBLE (rapid growth)
Cross-check: Yahoo Finance analyst consensus for Q4 FY25: ~$37.1B ✓
Validation: PASSED
```

### Step 5: PE Calculation (1-3s)

**Historical PE calculation:**
```python
# EDGAR XBRL: EPS by quarter (FY2020-FY2025)
# yfinance: monthly price history 2019-2024

pe_series = [
  ("2020-01", 85.3),  ("2020-06", 98.1), ...
  ("2022-01", 75.6),  ("2022-06", 42.1), ... # Multiple compression
  ("2023-01", 55.2),  ...
  ("2024-10", 54.9),  ("2024-11", 51.7)
]

median_pe_5yr: 48.3
p25_pe: 32.1
p75_pe: 61.4

# Note: NVDA's PE is volatile; 5yr median more robust than 3yr
# (3yr would overweight COVID-era inflated multiples)
```

### Step 6: Valuation Calculation (< 1s)

**Using Q4 FY25 Guidance + Full Year Forward Projection:**
```
Approach: Since Q4 guidance implies accelerating trajectory,
project FY2026 EPS using:
  Q4FY25 EPS run rate × 4 (annualized) as FY2026 proxy
  OR use analyst FY2026 consensus EPS: ~$4.80

Guidance EPS (FY2026 proxy): $4.80 (from analyst consensus + growth rate)
Median PE (5yr): 48.3x

Estimated Price = $4.80 × 48.3 = $231.84... 

⚠️ NOTE: This illustrates the method. Actual NVDA values would 
be from live API calls at analysis time.

Bear case: $4.80 × 32.1 = $154.08
Bull case: $4.80 × 61.4 = $294.72

Upside vs current = (estimated - current) / current × 100

Confidence score:
  Source quality: 3 official sources (SEC, earnings call, IR) → 0.95
  Consensus tightness: Low std dev → 0.85
  Recency: 1 day old → 1.0
  Hallucination: 0 flags → 1.0
  Official guidance: true → 1.0
  Weighted score: 0.84 → "HIGH CONFIDENCE"
```

### Step 7: Output Delivered to UI (Total time: ~25-45s)

```
═══════════════════════════════════════════════════
 NVIDIA CORPORATION (NVDA)  │  Analysis: Nov 21, 2024
═══════════════════════════════════════════════════

 CURRENT PRICE:     $875.40
 ESTIMATED PRICE:   $XXX.XX   [FY2026 projection]
 UPSIDE/DOWNSIDE:   ▲ +X.X%  (base case)

 CONFIDENCE:        ████████░░  84%  (HIGH)
 GUIDANCE PERIOD:   FY2026 (ends Jan 2026)

 KEY METRICS:
   EPS TTM:         $1.69
   Guidance EPS:    $4.80 (FY2026 proxy)
   Revenue TTM:     $96.3B
   Guidance Rev:    ~$37.5B (Q4FY25) → $150B+ annual run rate
   Median PE (5yr): 48.3x
   PE Range:        32.1x - 61.4x

 SCENARIO ANALYSIS:
   Bear (32.1x PE): $XXX.XX
   Base (48.3x PE): $XXX.XX
   Bull (61.4x PE): $XXX.XX

 SOURCES:
   [✓] SEC 8-K — Nov 20, 2024 — HIGH CONFIDENCE
       "revenue to be $37.5 billion, plus or minus 2%"
   [✓] Q3 FY2025 Earnings Call — Nov 20, 2024 — HIGH
       "[CFO Colette Kress]: Our guidance for..."
   [~] Yahoo Finance Consensus — MEDIUM
       Analyst EPS FY2026: $4.80 (avg of 40 analysts)
═══════════════════════════════════════════════════
```

---

## 16. Architecture Diagrams, Contracts & Folder Structure

### 16.1 API Contract

```yaml
# OpenAPI 3.0

paths:
  /api/v1/analyze:
    post:
      summary: Start stock analysis
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                ticker:
                  type: string
                  example: "NVDA"
                force_refresh:
                  type: boolean
                  default: false
      responses:
        202:
          content:
            application/json:
              schema:
                type: object
                properties:
                  job_id: { type: string }
                  status: { type: string, enum: [pending] }
                  ws_url: { type: string }

  /api/v1/analysis/{job_id}:
    get:
      summary: Get analysis result
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValuationResult'

components:
  schemas:
    ValuationResult:
      type: object
      properties:
        ticker: { type: string }
        company_name: { type: string }
        current_price: { type: number }
        estimated_price: { type: number }
        bear_price: { type: number }
        bull_price: { type: number }
        upside_pct: { type: number }
        confidence_score: { type: number, minimum: 0, maximum: 1 }
        current_eps_ttm: { type: number }
        guidance_eps: { type: number }
        guidance_revenue: { type: number }
        guidance_period: { type: string }
        median_pe: { type: number }
        pe_years_used: { type: integer }
        negative_eps_flag: { type: boolean }
        sources:
          type: array
          items:
            type: object
            properties:
              url: { type: string }
              source_type: { type: string }
              document_date: { type: string, format: date }
              source_quote: { type: string }
              confidence: { type: string, enum: [high, medium, low] }
        analyzed_at: { type: string, format: date-time }

  /ws/analysis/{job_id}:
    description: WebSocket for real-time progress
    messages:
      progress:
        payload:
          type: object
          properties:
            type: { type: string, enum: [progress] }
            stage: { type: string }
            message: { type: string }
            pct_complete: { type: integer }
      complete:
        payload:
          type: object
          properties:
            type: { type: string, enum: [complete] }
            result: { $ref: '#/components/schemas/ValuationResult' }
```

### 16.2 Service Boundaries (Microservice Map)

```
┌────────────────────────────────────────────────────────┐
│                    API Gateway Service                  │
│  • REST + WebSocket endpoints                           │
│  • Auth middleware                                      │
│  • Rate limiting                                        │
│  • Job creation + status tracking                       │
└──────────────────────────┬─────────────────────────────┘
                           │ Celery tasks
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐ ┌────────▼───────┐ ┌───────▼──────────┐
│Financial Data │ │Document Ingest │ │AI Extraction Svc │
│Service        │ │Service         │ │                  │
│• yfinance     │ │• EDGAR client  │ │• LLM gateway     │
│• PE calc      │ │• Web scraper   │ │• RAG pipeline    │
│• EPS history  │ │• PDF parser    │ │• Hallucination   │
│• Price hist   │ │• Chunker       │ │  guard           │
│               │ │• Embedder      │ │• Confidence      │
└───────────────┘ └────────────────┘ └──────────────────┘
        │                  │                  │
        └──────────────────▼──────────────────┘
                           │
                 ┌─────────▼────────┐
                 │Valuation Engine  │
                 │• PE × EPS calc   │
                 │• Alt methods     │
                 │• Scenario calc   │
                 │• Result assembly │
                 └──────────────────┘
```

### 16.3 Example Prompts for Different Document Types

**For Earnings Call Transcripts:**
```
You are analyzing an earnings call transcript. Management's statements
begin with their name (e.g., "Jensen Huang:", "Colette Kress:").

Extract ONLY guidance provided by COMPANY MANAGEMENT (not analysts asking questions).

Look specifically for:
1. Specific numeric guidance for EPS, revenue, gross margin
2. Qualitative guidance ("expect strong growth", "confident in X")
3. Period of guidance (next quarter, full year, multiple years)
4. Any changes from prior guidance (raised/lowered/reiterated)

TRANSCRIPT SECTION:
{chunk_text}

{schema_instructions}
```

**For SEC 8-K Press Releases:**
```
You are analyzing an SEC 8-K earnings press release.

Press releases contain:
- Official company guidance in "Outlook" or "Guidance" sections
- Financial tables with actuals (not guidance - these are historical)
- Management's prepared remarks

Extract ONLY forward-looking guidance (not historical results).
Guidance usually appears in sections labeled:
"Outlook", "Guidance", "Financial Outlook", "Business Outlook"

DOCUMENT SECTION:
{chunk_text}

{schema_instructions}
```

**For News Articles:**
```
You are analyzing a financial news article about {company_name} ({ticker}).

IMPORTANT: News articles may quote management, summarize guidance,
or include analyst opinions. You MUST distinguish:
- Direct quotes from management (is_official_guidance: true)
- Journalist summaries of guidance (is_official_guidance: true)
- Analyst estimates or opinions (is_official_guidance: false)

ARTICLE TEXT:
{chunk_text}

{schema_instructions}

Set extraction_confidence = 0.5 for news articles (lower than primary sources).
```

### 16.4 Where NOT to Use LLMs

```
DO USE LLM for:
✓ Extracting guidance from unstructured text
✓ Distinguishing official guidance from speculation
✓ Identifying guidance periods from ambiguous language
✓ Summarizing multiple conflicting sources

DO NOT USE LLM for:
✗ Fetching live stock prices (use yfinance API directly)
✗ Mathematical PE calculations (use deterministic Python)
✗ Looking up SEC filings (use EDGAR API directly)
✗ Validating extracted numbers (use rule-based bounds checking)
✗ Caching or database lookups (use Redis/PostgreSQL directly)
✗ User authentication (use standard JWT library)
```

### 16.5 Failure Scenarios & Mitigations

| Failure | Probability | Mitigation |
|---|---|---|
| LLM API down | Low | Fallback to OpenAI, then to analyst consensus from yfinance |
| yfinance returns null EPS | Medium | Fetch from EDGAR XBRL directly |
| Scraper blocked (429) | High for some sites | Respect robots.txt, exponential backoff, rotate User-Agents |
| No guidance found in docs | Medium | Return analysis with null guidance, flag as "No official guidance found" |
| Negative EPS | Low-Medium (growth co.) | Switch to P/S valuation, flag prominently |
| Historical PE < 5 data points | Medium (new IPOs) | Use sector median PE as substitute |
| ChromaDB connection failure | Low | In-memory fallback using simple keyword search |
| Database down | Very Low | Redis cache can serve recent results; queue persists tasks |
| Conflicting guidance (raised/lowered) | Low | Use most recent; flag conflict in UI |
| LLM hallucinated EPS | Low with guards | Validation rejects implausible values; fallback to consensus |

---

## Summary: Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| LLM Provider | Claude claude-sonnet-4-20250514 (primary) | Best structured extraction, long context |
| PE Timeframe | 5-year median (not 3) | More robust, avoids single-cycle distortions |
| Valuation Method | EPS × Median PE (primary) + P/S fallback | Simple, auditable, market-tested |
| Embedding Model | all-MiniLM-L6-v2 (local) | Free, CPU-capable, good quality |
| Vector DB | ChromaDB self-hosted | Free, easy deployment, Python-native |
| Task Queue | Celery + Redis | Battle-tested, flexible worker routing |
| Source Priority | SEC 8-K > Earnings Call > News | Official > derived |
| Confidence Signal | Composite: source quality + recency + consensus tightness | Transparent, explainable |
| Negative EPS | P/S ratio fallback | Industry standard alternative |
| Data Access | yfinance + EDGAR (both free) | No paid API dependency |

---

*Architecture Version 1.0 | Designed for production-grade deployment*
*All technologies: Free/Open-Source | LLM: API key required (Anthropic/OpenAI)*