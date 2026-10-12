# Stock Guidance Platform — Complete Architecture & Workflow Deep Dive

---

## Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [Technology Stack](#2-technology-stack)
3. [Project File Map](#3-project-file-map)
4. [Complete Request Lifecycle: What Happens When You Enter a Ticker](#4-complete-request-lifecycle)
5. [Every Process, Function & Endpoint Explained](#5-every-process-function--endpoint-explained)
6. [The LLM Pipeline: How & When It's Called](#6-the-llm-pipeline)
7. [Token Usage Analysis Per Call](#7-token-usage-analysis-per-call)
8. [Caching: What Gets Cached & Where](#8-caching)
9. [Confidence Score: The Complete Math](#9-confidence-score)
10. [Frontend: How Confidence Is Displayed](#10-frontend)
11. [Valuation Engine Deep Dive](#11-valuation-engine)
12. [Guidance Resolution: Weighted Median & Conflict Detection](#12-guidance-resolution)
13. [Error Handling & Degradation](#13-error-handling--degradation)
14. [Database Schema](#14-database-schema)

---

## 1. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER'S BROWSER                               │
│  React 19 + Vite + TailwindCSS 4 + Zustand + Recharts              │
│  Port 3000 (dev) → proxies /api → localhost:8000                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP POST /api/v1/analyze
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND (port 8000)                     │
│                                                                     │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐        │
│  │ API Layer│   │  Services    │   │   AI / LLM Pipeline   │        │
│  │          │   │              │   │                      │        │
│  │ stocks.py│──▶│ valuation    │──▶│ llm_gateway.py       │        │
│  │ analysis │   │ _service.py  │   │   → DeepSeek V4 Flash│        │
│  │ .py      │   │              │   │                      │        │
│  │          │   │ guidance     │   │ prompts.py           │        │
│  │ websocket│   │ _service.py  │   │   → 4 prompt types   │        │
│  │ .py      │   │              │   │                      │        │
│  │          │   │ confidence   │   │ hallucination_guard  │        │
│  │          │   │ _service.py  │   │   → validation       │        │
│  │          │   │              │   │                      │        │
│  │          │   │ pe_calculator│   │ chunker.py           │        │
│  │          │   │ .py          │   │   → 800-token chunks │        │
│  │          │   │              │   │                      │        │
│  │          │   │ document     │   │ embedder.py          │        │
│  │          │   │ _ingestion.py│   │   → MiniLM-L6-v2     │        │
│  │          │   │              │   │                      │        │
│  │          │   │ content      │   │ rag_pipeline.py      │        │
│  │          │   │ _filter.py   │   │   → ChromaDB         │        │
│  └──────────┘   └──────────────┘   └──────────────────────┘        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                  INGESTION LAYER                          │      │
│  │  yfinance_client.py  →  Yahoo Finance (primary)          │      │
│  │  twelvedata_client.py → Twelve Data (fallback, 800/day)  │      │
│  │  edgar_client.py     →  SEC EDGAR (filings, token bucket)│      │
│  │  scraper.py          →  Web scraper (httpx + Playwright) │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                  STORAGE LAYER                            │      │
│  │  PostgreSQL  →  stocks, analysis_runs, valuations, docs  │      │
│  │  Redis       →  (client ready, not yet used in pipeline) │      │
│  │  ChromaDB    →  vector store for document chunks         │      │
│  │  .llm_cache/ →  filesystem JSON cache for LLM responses  │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 19, Vite 8, TailwindCSS 4 | SPA with dark theme |
| **State** | Zustand 5 | Recent searches (localStorage) |
| **Charts** | Recharts 3 | PE history & valuation scenario bars |
| **HTTP Client** | Axios | API calls with 90s timeout |
| **Routing** | React Router 7 | `/` (Home), `/analysis/:ticker` (Results) |
| **Backend** | FastAPI (Python) | REST API + WebSocket |
| **LLM** | DeepSeek V4 Flash | Guidance extraction via OpenAI-compatible API |
| **Embeddings** | all-MiniLM-L6-v2 (384-dim) | Sentence similarity for RAG |
| **Vector DB** | ChromaDB (PersistentClient) | Document chunk storage & retrieval |
| **Financial Data** | yfinance (primary), Twelve Data API (fallback) | Stock prices, EPS, PE ratios |
| **SEC Data** | SEC EDGAR API (data.sec.gov, efts.sec.gov) | 8-K, 10-Q filings |
| **Web Scraping** | httpx + BeautifulSoup4 + Playwright | News articles & JS-rendered pages |
| **Database** | PostgreSQL (async via SQLAlchemy + asyncpg) | Persistent storage |
| **Cache** | Redis (client ready), filesystem JSON | LLM response caching |
| **Validation** | Pydantic v2 | Request/response schemas |

---

## 3. Project File Map

### Backend (`backend/`)

```
backend/
├── app/
│   ├── main.py                          # FastAPI app, router registration
│   ├── api/
│   │   ├── v1/
│   │   │   ├── stocks.py                # GET /stocks/{ticker}, GET /stocks/{ticker}/validate
│   │   │   └── analysis.py              # POST /analyze — THE MAIN ENDPOINT
│   │   └── websocket.py                 # WS /ws/analysis/{job_id}
│   ├── core/
│   │   ├── config.py                    # Settings from .env (Pydantic BaseSettings)
│   │   ├── database.py                  # SQLAlchemy async engine, get_db()
│   │   └── redis_client.py             # get_redis() async generator
│   ├── models/
│   │   ├── stock.py                     # Stock ORM model
│   │   ├── analysis.py                  # AnalysisRun ORM model
│   │   ├── valuation.py                 # PEHistory + Valuation ORM models
│   │   └── document.py                  # SourceDocument ORM model
│   ├── schemas/
│   │   └── guidance.py                  # Pydantic: GuidanceItem, ExtractionResult, GuidanceSummary, ValidationResult
│   ├── services/
│   │   ├── valuation_service.py         # Core valuation calculation
│   │   ├── pe_calculator.py             # Historical median PE (5yr TTM)
│   │   ├── guidance_service.py          # LLM extraction orchestration + guidance resolution
│   │   ├── confidence_service.py        # Confidence scoring (guidance + valuation)
│   │   ├── document_ingestion.py        # discover_documents(): EDGAR + news
│   │   └── content_filter.py           # Quality checks, checksums
│   ├── ingestion/
│   │   ├── yfinance_client.py           # YFinance wrapper (primary data source)
│   │   ├── twelvedata_client.py         # Twelve Data wrapper (fallback)
│   │   ├── edgar_client.py              # SEC EDGAR API client
│   │   └── scraper.py                   # SmartScraper: httpx + Playwright
│   └── ai/
│       ├── llm_gateway.py               # DeepSeek API wrapper
│       ├── prompts.py                   # 4 prompt templates (general, earnings call, 8-K, news)
│       ├── hallucination_guard.py       # EPS/revenue validation
│       ├── chunker.py                   # 800-token chunker with overlap
│       ├── embedder.py                  # MiniLM-L6-v2 embeddings (384-dim)
│       └── rag_pipeline.py              # ChromaDB index/query
├── tests/
│   ├── conftest.py                      # Mock yfinance, sample 8-K, PE results
│   ├── unit/
│   │   ├── test_valuation.py            # PEG sanity checks
│   │   ├── test_confidence.py           # Confidence score math
│   │   ├── test_hallucination_guard.py  # Validation rules
│   │   ├── test_guidance_resolution.py  # Weighted median, conflict detection
│   │   └── test_content_filter.py       # Quality checks
│   └── integration/
│       └── test_valuation_pipeline.py   # Full valuation with mock data
├── alembic/                             # DB migrations
├── .llm_cache/                          # Filesystem LLM response cache
└── requirements.txt
```

### Frontend (`frontend/`)

```
frontend/src/
├── main.jsx                             # React bootstrap
├── App.jsx                              # Routes: / and /analysis/:ticker
├── index.css                            # TailwindCSS import
├── api/
│   └── client.js                        # Axios instance (baseURL /api/v1, 90s timeout)
├── store/
│   └── useAppStore.js                   # Zustand: recentSearches (localStorage)
├── hooks/
│   └── useAnalysis.js                   # startAnalysis(), progress tracking
├── pages/
│   ├── Home.jsx                         # Landing page + SearchBar + RecentSearches
│   └── Analysis.jsx                     # Analysis page: loading → error → dashboard
└── components/
    ├── Search/
    │   ├── SearchBar.jsx                # Debounced ticker input with validation
    │   └── RecentSearches.jsx           # Clickable recent ticker pills
    ├── Common/
    │   └── LoadingSpinner.jsx           # Animated progress bar
    ├── Dashboard/
    │   ├── DashboardLayout.jsx          # Main results grid assembler
    │   ├── PriceSummaryCard.jsx         # Currency/percent formatted card
    │   ├── ConfidenceMeter.jsx          # Score bar (red/amber/emerald)
    │   └── GuidancePeriodBadge.jsx      # Period label pill
    ├── Metrics/
    │   └── KeyMetricsGrid.jsx           # EPS, PE, Revenue, Market Cap, PEG
    ├── Charts/
    │   ├── ValuationScenarios.jsx       # Bear/Base/Bull bar chart
    │   └── PEHistoryChart.jsx           # P25/Median/P75 PE bar chart
    └── Guidance/
        ├── GuidanceTable.jsx            # Extracted guidance items table
        ├── SourceCard.jsx               # Individual source document card
        └── SourceList.jsx               # Grouped source documents
```

---

## 4. Complete Request Lifecycle

### What Happens When You Type "NVDA" and Press Enter

#### Phase 0: Ticker Entry (Frontend, ~300ms)

1. **`SearchBar.jsx`** captures keystrokes
2. On each change, a 300ms debounce timer starts
3. After 300ms of no typing, it calls `GET /api/v1/stocks/NVDA/validate`
4. The backend's **`stocks.py:validate_ticker()`** calls `yfinance_client.validate_ticker("NVDA")`
5. If yfinance returns a valid response (has `trailingEps` or `currentPrice`), it returns `{ticker, company_name, cik, exchange, sector, industry}`
6. The frontend shows a suggestion dropdown with the company name
7. User clicks or presses Enter → `addRecent("NVDA")` saves to localStorage → navigates to `/analysis/NVDA`

#### Phase 1: Analysis Start (Frontend → Backend)

8. **`Analysis.jsx`** mounts, `useEffect` fires
9. Calls `startAnalysis("NVDA")` from **`useAnalysis.js`**
10. Sets status to `'loading'`, progress to `{stage: 'validating', pct: 10}`
11. Makes `POST /api/v1/analyze` with body `{"ticker": "NVDA"}`

#### Phase 2: Ticker Validation & CIK Resolution (Backend)

12. **`analysis.py:start_analysis()`** receives the request
13. Validates ticker format: regex `^[A-Z0-9.\-]{1,10}$`
14. Generates a `job_id` (UUID v4)
15. Pushes progress via WebSocket: `{stage: "validating", pct: 5}`
16. Creates `YFinanceClient` and `TwelveDataClient` instances
17. Calls `yf_client.validate_ticker("NVDA")` — fetches stock info dict
18. **If yfinance is rate-limited (429)**: falls back to `td_client.validate_ticker("NVDA")`
    - Sets `data_source = "twelvedata"`, `pe_client = None` (Twelve Data can't do PE history)
    - Adds degradation flag: `"yfinance_rate_limited_using_twelvedata"`
19. **If both fail**: pushes error, raises HTTP 404
20. Extracts `company_name` and `cik` from validation result
21. If no CIK in validation, calls `await resolve_cik("NVDA")` which:
    - Checks in-memory `_cik_cache` dict
    - If miss: fetches `https://www.sec.gov/files/company_tickers.json`
    - Parses all tickers → CIK mappings, caches them
    - Returns CIK string (e.g., `"0001045810"` for NVDA)

#### Phase 3: Financial Data & Initial Valuation

22. Pushes progress: `{stage: "fetching_data", pct: 15}`
23. **If data source is yfinance**: calls `calculate_valuation("NVDA", yf_client)`
24. **If data source is twelvedata**: calls `calculate_valuation_from_data("NVDA", td_info, client=None)`
25. This is the core valuation:

    ```
    Step A: yf_client.get_stock_info("NVDA")
            → {current_price, eps_ttm, forward_eps, pe_ttm, revenue_ttm, market_cap, ...}

    Step B: calculate_historical_median_pe("NVDA", yf_client, years=5)
            → Fetches 5 years of monthly prices
            → Fetches 20 quarters of EPS
            → For each month, computes TTM EPS (sum of last 4 quarters)
            → Computes PE = price / TTM_EPS for each month
            → Returns {median_pe, mean_pe, p25_pe, p75_pe, min_pe, max_pe, observations}

    Step C: Apply valuation formula
            estimated_price = forward_eps × median_pe
            bull_price  = forward_eps × p75_pe
            bear_price  = forward_eps × p25_pe
            upside_pct  = (estimated_price - current_price) / current_price × 100
    ```

26. If `insufficient_data_flag` is True → raises HTTP 422
27. Pushes progress: `{stage: "fetching_documents", pct: 30}`

#### Phase 4: Document Discovery

28. Creates `EDGARClient` and `SmartScraper` instances
29. Calls `await discover_documents("NVDA", "NVIDIA Corp", "0001045810", edgar, scraper)`

    **EDGAR Path:**
    ```
    a. edgar.get_company_submissions("0001045810")
       → GET https://data.sec.gov/submissions/CIK0001045810.json
       → Returns all recent filings (forms, dates, accessions)

    b. Iterates through filings, looking for form types "8-K" and "10-Q"
       within the last 180 days

    c. For 8-K filings: checks if the filing contains EX-99 exhibits
       (earnings press releases) — skips if not

    d. For each qualifying filing:
       edgar.get_filing_text(cik, accession)
       → GET https://www.sec.gov/Archives/edgar/data/1045810/{acc}/{acc}.txt
       → _extract_text_from_filing() parses the multi-document SEC format:
         - Finds <DOCUMENT> sections with TYPE EX-99
         - Strips HTML via BeautifulSoup + lxml
         - Returns clean text

    e. content_quality_check(text):
       - Must be ≥ 200 words
       - Must be primarily English (<15% non-ASCII)
       - Must contain ≥ 2 financial keywords
       - Computes SHA-256 checksum

    f. Appends document to list, deduplicates by checksum
       Max 2 EDGAR documents
    ```

    **News Path:**
    ```
    g. search_guidance_news("NVDA", "NVIDIA Corp")
       → RSS: https://news.google.com/rss/search?q=NVIDIA+Corp+earnings+guidance+EPS+revenue+forecast
       → Parses via feedparser, returns up to 10 headlines

    h. For up to 5 news articles:
       scraper.scrape(link)
       → Static sites (sec.gov, reuters.com, businesswire.com): httpx + BeautifulSoup
       → JS sites (seekingalpha.com, fool.com): Playwright headless Chromium
       → Strips <script>, <style>, <nav>, <header>, <footer>, <aside>
       → Returns ScrapedContent(text, word_count)

    i. content_quality_check() on each article
    j. Deduplicates by checksum
    ```

30. Documents are sorted by priority: `SEC_8K > SEC_10Q > SEC_10K > press_release > news_article`

#### Phase 5: LLM Guidance Extraction

31. If no documents found: sets `guidance_used = "analyst_consensus"`, adds degradation flag `"no_documents_found"`
32. If documents found: calls `await extract_guidance_from_documents(ticker, company_name, documents, eps_ttm, revenue_ttm)`

    **For each document:**
    ```
    a. Compute cache key: SHA-256(source_type + ":" + raw_text)[:16]

    b. Check .llm_cache/{cache_key}.json
       → If exists and valid: CACHE HIT, skip LLM call
       → If not: proceed to LLM extraction

    c. _smart_excerpt(raw_text)
       → Searches for guidance section markers:
         "outlook for the", "financial outlook", "business outlook", "outlook", "guidance"
       → Finds the section start by walking back to the previous newline
       → Finds the section end by locating the next major boundary:
         "about nvidia", "forward-looking statements", "safe harbor",
         "non-gaap reconciliation", "supplemental", "contact",
         "investor relations", "conference call", "webcast"
       → Returns ~4000 characters centered on the guidance section
       → If no section found, takes middle ~4000 chars of document

    d. get_prompt_for_source_type(source_type)
       → SEC_8K, SEC_10Q, SEC_10K → SEC_8K_PROMPT
       → earnings_call → EARNINGS_CALL_PROMPT
       → news_article, press_release → NEWS_ARTICLE_PROMPT
       → default → GENERAL_EXTRACTION_PROMPT

    e. llm.extract_guidance(prompt, excerpt)
       → SEE SECTION 6 FOR FULL LLM DETAILS

    f. HallucinationGuard.filter_valid_items(result, eps_ttm, revenue_ttm)
       → For each EPS item: validates within 200% of TTM EPS
       → For each Revenue item: validates within 500% of TTM revenue
       → Checks source quotes contain the extracted numbers
       → Removes invalid items

    g. _save_cache(cache_key, result)
       → Writes ExtractionResult as JSON to .llm_cache/{key}.json
    ```

33. **Guidance Resolution** (`_resolve_guidance`):
    ```
    For each metric (EPS, Revenue, GrossMargin):
      a. Pool official guidance items (is_official_guidance=True)
         If none, fall back to all items
      b. Extract values + source quality weights from each item
      c. Compute weighted median:
         - Sort (value, weight) pairs by value
         - Find value at cumulative weight midpoint (50th percentile)
      d. Create consolidated GuidanceItem with:
         value_midpoint = weighted median
         value_low = min of all values (if >1 source)
         value_high = max of all values (if >1 source)
         Other fields from highest-quality source
    ```

34. **Conflict Detection** (`_detect_conflict`):
    ```
    For EPS items across all extractions:
      deviation = (max_value - min_value) / |max_value|
      conflict = deviation > 0.10 (10% threshold)
    ```

35. **Guidance Confidence** (`_calculate_confidence`):
    ```
    score = 0.4 × avg_source_quality      // SEC_8K=1.0, news=0.5, analyst=0.3
          + 0.2 × source_diversity_bonus  // min(unique_sources/3, 1.0)
          + 0.2 × consensus_tightness     // 1 - CV×5 (CV = std/mean of EPS values)
          (or +0.1 if <2 EPS items)
    ```

#### Phase 6: Recalculate Valuation With Extracted EPS

36. If `guidance_used == "extracted"` and we have a PE client:
    ```
    _recalculate_with_extracted_eps(valuation, guidance_summary, yf_client, "NVDA")

    a. Re-runs calculate_historical_median_pe() (needed for fresh PE data)
    b. estimated_price = extracted_eps × median_pe
    c. bull_price = extracted_eps × p75_pe
    d. bear_price = extracted_eps × p25_pe
    e. upside_pct = (estimated - current_price) / current_price × 100
    f. Sets valuation_method = "extracted_eps_x_median_pe"
    ```

#### Phase 7: Confidence Calculation

37. Calls `calculate_confidence_summary(guidance, pe_observations, negative_eps)`
    - See Section 9 for the complete math

#### Phase 8: Response Assembly

38. Builds the final response JSON (see Section 5 for full schema)
39. Pushes completion via WebSocket: `{type: "complete", pct: 100}`
40. Returns HTTP 200 with the full response

#### Phase 9: Frontend Rendering

41. **`useAnalysis.js`** receives the response
42. Sets `status = 'complete'`, `result = data`
43. **`Analysis.jsx`** renders **`DashboardLayout`** with the data
44. Dashboard shows:
    - Header: ticker, company name, guidance period badge
    - 3 price cards: Current Price, Estimated Price, Upside %
    - Confidence meter with colored bar
    - Key metrics grid (EPS, PE, Revenue, Market Cap, etc.)
    - Valuation scenarios bar chart (Bear/Base/Bull)
    - PE history bar chart (P25/Median/P75)
    - Guidance table (extracted items)
    - Source list (grouped by type)

---

## 5. Every Process, Function & Endpoint Explained

### 5.1 API Endpoints

#### `GET /health`
- **File:** `backend/app/main.py:25`
- **Purpose:** Kubernetes/load balancer health check
- **Returns:** `{"status": "ok"}`
- **No auth, no DB, no dependencies**

---

#### `GET /api/v1/stocks/{ticker}`
- **File:** `backend/app/api/v1/stocks.py:8`
- **Purpose:** Get basic stock information (current price, EPS, PE, etc.)
- **Flow:**
  1. Gets singleton `YFinanceClient` via `get_yfinance_client()`
  2. Calls `client.get_stock_info(ticker)` which calls yfinance's `Ticker.info`
  3. Retries up to 3 times with exponential backoff
  4. Returns flat dict: `{ticker, current_price, eps_ttm, forward_eps, pe_ttm, forward_pe, revenue_ttm, market_cap, company_name, sector, industry, analyst_target_price, recommendation}`
- **Error handling:**
  - 503 if yfinance rate-limited
  - 404 if ticker not found

---

#### `GET /api/v1/stocks/{ticker}/validate`
- **File:** `backend/app/api/v1/stocks.py:19`
- **Purpose:** Validate that a ticker exists and return metadata
- **Returns:** `{ticker, company_name, cik, exchange, sector, industry, fiscal_year_end}`
- **Used by:** `SearchBar.jsx` for the autocomplete dropdown
- **Same error handling as above**

---

#### `POST /api/v1/analyze`
- **File:** `backend/app/api/v1/analysis.py:37`
- **Purpose:** THE main endpoint — runs the full analysis pipeline
- **Request body:** `{"ticker": "NVDA", "force_refresh": false}`
- **Ticker validation:** regex `^[A-Z0-9.\-]{1,10}$`, stripped and uppercased
- **Response schema (the complete JSON):**

```json
{
  "job_id": "uuid-string",
  "status": "complete",
  "started_at": "ISO-8601 timestamp",
  "completed_at": "ISO-8601 timestamp",
  "result": {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corporation",
    "current_price": 150.00,
    "current_eps_ttm": 5.00,
    "current_revenue_ttm": 100000000000,
    "market_cap": 2000000000000,
    "current_pe_ttm": 30.0,
    "guidance_eps": 6.50,
    "guidance_revenue": null,
    "guidance_period": "Q1 FY2027",
    "guidance_source": "extracted",
    "median_pe": 48.3,
    "pe_years_used": 5,
    "pe_observations": 20,
    "pe_p25": 32.1,
    "pe_p75": 61.4,
    "estimated_price": 313.95,
    "bull_price": 399.10,
    "bear_price": 208.65,
    "upside_pct": 109.30,
    "confidence_score": 0.82,
    "valuation_method": "extracted_eps_x_median_pe",
    "negative_eps_flag": false,
    "low_confidence_flag": false,
    "insufficient_data_flag": false,
    "alternative_valuations": {},
    "peg_health": {
      "peg_ratio": 1.5,
      "pe_ttm": 30.0,
      "eps_growth_rate_pct": 20.0,
      "assessment": "PEG=1.50: fairly valued"
    }
  },
  "guidance": {
    "overall_confidence": 0.84,
    "guidance_period": "Q1 FY2027",
    "conflict_detected": false,
    "eps_guidance": {
      "metric": "EPS",
      "value_low": 0.87,
      "value_high": 0.91,
      "value_midpoint": 0.89,
      "unit": "USD",
      "period_label": "Q1 FY2027",
      "fiscal_year": 2027,
      "fiscal_quarter": 1,
      "is_official_guidance": true,
      "source_quote": "EPS expected to be approximately $0.89",
      "confidence": "high",
      "guidance_type": "initial",
      "source_type": "SEC_8K"
    },
    "revenue_guidance": { /* same structure */ },
    "gross_margin_guidance": { /* same structure */ },
    "items_found": 4,
    "source": "extracted"
  },
  "confidence": {
    "guidance_confidence": 0.84,
    "valuation_confidence": 0.82,
    "confidence_label": "HIGH",
    "has_official_guidance": true
  },
  "sources": [
    {
      "url": "https://www.sec.gov/Archives/edgar/data/...",
      "source_type": "SEC_8K",
      "document_date": "2026-02-25",
      "document_title": "NVDA 8-K Filing (2026-02-25)",
      "word_count": 4500
    }
  ],
  "source_count": 1,
  "degradation": {
    "flags": ["llm_extraction_succeeded"],
    "is_degraded": false
  }
}
```

---

#### WebSocket: `/ws/analysis/{job_id}`
- **File:** `backend/app/api/websocket.py:35`
- **Purpose:** Real-time progress updates during analysis
- **How it works:**
  1. Frontend connects to `ws://localhost:8000/ws/analysis/{job_id}`
  2. Backend creates an `asyncio.Queue` for that job_id
  3. During analysis, `push_progress(job_id, event_type, **data)` puts messages on the queue
  4. The WebSocket handler loops, reading from the queue with a 30-second timeout
  5. If no message in 30 seconds, sends `{type: "timeout"}` and closes
  6. On `"complete"` or `"error"` message, sends final message and closes
- **Event types:** `"progress"`, `"complete"`, `"error"`, `"timeout"`
- **Note:** The current frontend (`useAnalysis.js`) does NOT use WebSocket — it relies on the synchronous HTTP response. The WebSocket infrastructure exists for future async/background processing.

---

### 5.2 YFinanceClient

**File:** `backend/app/ingestion/yfinance_client.py`

| Method | What It Does | Returns |
|--------|-------------|---------|
| `validate_ticker(ticker)` | Calls `yf.Ticker(ticker).info`, extracts metadata | `{ticker, company_name, cik, exchange, sector, industry, fiscal_year_end}` or `None` |
| `get_stock_info(ticker)` | Calls `yf.Ticker(ticker).info`, extracts financials | `{current_price, eps_ttm, forward_eps, pe_ttm, forward_pe, revenue_ttm, market_cap, company_name, sector, industry, analyst_target_price, recommendation}` |
| `get_price_history(ticker, period)` | Calls `yf.Ticker(ticker).history(period, interval="1mo")` | DataFrame with monthly OHLCV |
| `get_quarterly_eps(ticker)` | Calls `stock.quarterly_income_stmt`, extracts "Diluted EPS" row | Series of quarterly EPS values |
| `get_quarterly_revenue(ticker)` | Same but extracts "Total Revenue" row | Series of quarterly revenue |
| `get_earnings_estimates(ticker)` | Fetches `stock.earnings_estimate` and `stock.revenue_estimate` | Dict with earnings/revenue estimates |

**Rate limiting:** Detects HTTP 429 in error messages, sets `_rate_limited = True`, retries 3 times with exponential backoff (1s, 2s, 4s).

**Singleton:** `get_yfinance_client()` is cached with `@lru_cache(maxsize=1)`.

---

### 5.3 TwelveDataClient

**File:** `backend/app/ingestion/twelvedata_client.py`

Used as fallback when yfinance is rate-limited. Free tier: 800 requests/day.

| Method | What It Does |
|--------|-------------|
| `get_quote(ticker)` | `GET /quote?symbol={ticker}` |
| `get_statistics(ticker)` | `GET /statistics?symbol={ticker}` |
| `get_time_series(ticker)` | `GET /time_series?symbol={ticker}&interval=1day` |
| `validate_ticker(ticker)` | Uses `get_quote()`, returns basic metadata |
| `get_stock_info(ticker)` | Combines `get_quote()` + `get_statistics()` |

**Note:** Twelve Data cannot provide PE history or quarterly EPS, so when it's the primary source, `pe_client = None` and PE-based valuation is disabled.

---

### 5.4 EDGARClient

**File:** `backend/app/ingestion/edgar_client.py`

SEC EDGAR API client with token bucket rate limiting (10 requests/second).

| Method | What It Does |
|--------|-------------|
| `get_company_submissions(cik)` | `GET /submissions/CIK{cik_padded}.json` — recent filings |
| `get_company_facts(cik)` | `GET /api/xbrl/companyfacts/CIK{cik_padded}.json` — XBRL facts |
| `get_eps_history(cik)` | Extracts diluted EPS from company facts |
| `search_filings(ticker, forms, days_back)` | Searches EDGAR full-text search for specific forms |
| `get_filing_text(cik, accession)` | Downloads full filing, extracts EX-99 text |

**`resolve_cik(ticker)`:** Fetches `https://www.sec.gov/files/company_tickers.json`, builds a ticker→CIK map, caches in memory.

**`_extract_text_from_filing(raw)`:** SEC filings contain multiple `<DOCUMENT>` sections. This function:
1. Finds EX-99 exhibits (earnings press releases) using regex
2. Parses HTML with BeautifulSoup + lxml
3. Strips `<script>`, `<style>`, `<head>` tags
4. Returns clean text

---

### 5.5 SmartScraper

**File:** `backend/app/ingestion/scraper.py`

| Method | What It Does |
|--------|-------------|
| `scrape(url)` | Routes to httpx or Playwright based on domain |
| `_httpx_scrape(url)` | Simple HTTP GET + BeautifulSoup text extraction |
| `_playwright_scrape(url)` | Launches headless Chromium, renders JS, extracts text |

**Domain classification:**
- **Static:** sec.gov, reuters.com, businesswire.com, prnewswire.com → httpx
- **JS-rendered:** seekingalpha.com, fool.com → Playwright
- **Unknown:** try httpx first, fall back to Playwright if result <100 words

**`search_guidance_news(ticker, company_name)`:** Queries Google News RSS with `"{company} earnings guidance EPS revenue forecast"`, returns up to 10 headlines.

---

### 5.6 Valuation Engine

**File:** `backend/app/services/valuation_service.py`

**`calculate_valuation(ticker, client, pe_years=5)`** → dict

This is the core valuation pipeline. Three paths:

#### Path 1: Normal (positive EPS, PE history available) — `_apply_pe_valuation()`
```
estimated_price = guidance_eps × median_pe
bull_price      = guidance_eps × p75_pe
bear_price      = guidance_eps × p25_pe
upside_pct      = (estimated_price - current_price) / current_price × 100
valuation_method = "guided_eps_x_median_pe"
```

**Example with NVDA:**
```
guidance_eps  = $6.50 (forward EPS from analyst consensus)
median_pe     = 48.3  (5-year historical median PE)
p75_pe        = 61.4
p25_pe        = 32.1
current_price = $150.00

estimated = 6.50 × 48.3 = $313.95
bull      = 6.50 × 61.4 = $399.10
bear      = 6.50 × 32.1 = $208.65
upside    = (313.95 - 150.00) / 150.00 × 100 = +109.3%
```

#### Path 2: No PE history, but positive EPS with current PE — fallback
```
estimated_price = guidance_eps × current_pe_ttm
bull_price      = estimated × 1.3
bear_price      = estimated × 0.7
valuation_method = "forward_eps_x_current_pe"
low_confidence_flag = True
```

#### Path 3: Negative EPS — `_apply_ps_ratio_valuation()`
```
current_ps = market_cap / revenue_ttm
estimated_ps = current_ps × 0.8
valuation_method = "ps_ratio_fallback"
low_confidence_flag = True
```

**PEG Sanity Check** (`_peg_sanity_check`):
```
growth_rate = (forward_eps - eps_ttm) / eps_ttm  // or from quarterly EPS trend
peg = pe_ttm / (growth_rate × 100)

Interpretation:
  peg < 1  → "potentially undervalued"
  peg < 2  → "fairly valued"
  peg < 3  → "somewhat overvalued"
  peg ≥ 3  → "potentially overvalued"
```

---

### 5.7 PE Calculator

**File:** `backend/app/services/pe_calculator.py`

**`calculate_historical_median_pe(ticker, client, years=5)`** → dict | None

```
Algorithm:
1. Get monthly price history for {years} years
   → prices["Close"].resample("ME").last()

2. Get quarterly EPS history (typically ~20 quarters for 5 years)
   → stock.quarterly_income_stmt → "Diluted EPS" row

3. Parse EPS entries: (date, value) tuples sorted by date

4. For each month-end price:
   a. Find the 4 most recent quarterly EPS values (TTM)
   b. Sum them → TTM EPS
   c. If TTM EPS > 0: PE = price / TTM_EPS
   d. Gap check: reject if gap between consecutive quarters > 150 days

5. Compute statistics on all valid PE observations:
   median_pe = np.median(pe_series)
   mean_pe   = np.mean(pe_series)
   p25_pe    = np.percentile(pe_series, 25)
   p75_pe    = np.percentile(pe_series, 75)
   min_pe    = np.min(pe_series)
   max_pe    = np.max(pe_series)
   observations = len(pe_series)

6. Return None if < 5 observations
```

---

### 5.8 Document Ingestion

**File:** `backend/app/services/document_ingestion.py`

**`discover_documents(ticker, company_name, cik, edgar, scraper, days_back=180)`** → list[dict]

```
1. _fetch_edgar_filings():
   - Gets company submissions from EDGAR
   - Scans recent filings (last 180 days)
   - Looks for 8-K and 10-Q forms
   - For 8-K: validates EX-99 presence (earnings release)
   - Downloads filing text
   - Runs content_quality_check()
   - Max 2 EDGAR documents

2. _fetch_news_articles():
   - Searches Google News RSS
   - Scrapes up to 5 articles
   - Runs content_quality_check() on each

3. Deduplicates by SHA-256 checksum

4. Sorts by priority: SEC_8K (0) > SEC_10Q (1) > SEC_10K (2) > press_release (3) > news_article (4)
```

---

### 5.9 Content Filter

**File:** `backend/app/services/content_filter.py`

**`content_quality_check(text)`** → dict

Three checks:
1. **Word count:** ≥ 200 words
2. **Language:** < 15% non-ASCII characters (checks first 1000 chars)
3. **Financial keywords:** must contain ≥ 2 of: revenue, earnings, eps, guidance, outlook, forecast, gross margin, operating income, net income, ebitda, free cash flow, diluted eps, gaap, non-gaap, quarter, fiscal year, share, dividend, buyback, growth, segment, consensus, estimate

Also computes SHA-256 checksum for deduplication.

---

### 5.10 Chunker

**File:** `backend/app/ai/chunker.py`

**`chunk_document(text, source_type)`** → list[dict]

- **Chunk size:** 800 tokens (approximated as `len(text) // 4`)
- **Overlap:** 100 tokens
- **Break strategy:** tries `\n\n` → `\n` → `. ` → `, ` → ` ` (in order)
- **Earnings call special handling:**
  - Splits by speaker labels (e.g., `[Jensen Huang (management)]:`)
  - Tags chunks with `is_management` flag
  - Management = CEO, CFO, President, Officer, COO, Director, Chairman
  - Analyst = everyone else

---

### 5.11 Embedder

**File:** `backend/app/ai/embedder.py`

- **Model:** `all-MiniLM-L6-v2` from sentence-transformers
- **Dimension:** 384
- **`embed_texts(texts)`** → np.ndarray of shape (n, 384)
- **`embed_query(query)`** → list[float] of length 384
- **Fallback:** zero vectors if model can't load

---

### 5.12 RAG Pipeline (ChromaDB)

**File:** `backend/app/ai/rag_pipeline.py`

- **Collection naming:** `stock_guidance_{ticker_lowercase}`
- **`index_documents(ticker, chunks, metadata)`** → stores chunks in ChromaDB
- **`retrieve_relevant_chunks(ticker, query, top_k=8)`** → returns top-k by cosine distance
- **Note:** This module exists but is NOT currently called in the main `POST /analyze` pipeline. It was built for a potential RAG enhancement where guidance extraction would be augmented with vector-retrieved context. The current pipeline sends document excerpts directly to the LLM.

---

### 5.13 Smart Excerpt

**File:** `backend/app/services/guidance_service.py:_smart_excerpt()`

This function extracts only the guidance-relevant portion of a document before sending to the LLM:

```
1. Search for guidance markers (case-insensitive):
   "outlook for the", "financial outlook", "business outlook", "outlook", "guidance"

2. When found: walk back to the start of that line (previous \n)

3. Find the end by locating the next section boundary:
   "about nvidia", "about advanced micro", "about intel",
   "forward-looking statements", "safe harbor", "non-gaap reconciliation",
   "supplemental", "contact", "investor relations",
   "conference call", "webcast", "table of contents"

4. Default excerpt size: 4000 characters from guidance start

5. If no guidance section found: take middle 4000 chars of document
   (documents tend to have boilerplate at start/end)

6. Minimum: 200 characters (otherwise returns 4000 chars from guidance start)
```

**Example with NVIDIA 8-K:**
```
Full document: ~15,000 characters (legal headers, results, tables, guidance, boilerplate)
After smart excerpt: ~3,500 characters (just the "Financial Outlook" section)

Input to LLM: ~3,500 chars ≈ ~875 tokens (significantly reduced from ~3,750 tokens)
```

---

### 5.14 Guidance Service Orchestration

**File:** `backend/app/services/guidance_service.py`

This is the central orchestrator for all guidance-related logic.

**`extract_guidance_from_documents(ticker, company_name, documents, eps_ttm, revenue_ttm)`** → GuidanceSummary

```
For each document:
  ┌─────────────────────────────────────────────┐
  │ 1. Compute cache key from source_type+text  │
  │ 2. Check .llm_cache/ HIT → use cached       │
  │ 3. MISS → _smart_excerpt() → 4000 chars     │
  │ 4. get_prompt_for_source_type() → prompt    │
  │ 5. llm.extract_guidance(prompt, excerpt)    │
  │ 6. guard.filter_valid_items(result)         │
  │ 7. Tag items with source_url, source_type   │
  │ 8. _save_cache() → write JSON               │
  └─────────────────────────────────────────────┘

After all documents:
  ┌─────────────────────────────────────────────┐
  │ 9. _resolve_guidance(EPS items)             │
  │    → weighted median across sources         │
  │10. _resolve_guidance(Revenue items)         │
  │11. _detect_conflict(all extractions)        │
  │    → deviation > 10% → conflict             │
  │12. _calculate_confidence(all items)         │
  │    → source quality + diversity + consensus │
  │13. Return GuidanceSummary                   │
  └─────────────────────────────────────────────┘
```

---

## 6. The LLM Pipeline

### 6.1 LLM Gateway

**File:** `backend/app/ai/llm_gateway.py`

**Model:** `deepseek-v4-flash`
**Base URL:** `https://api.deepseek.com`
**Client:** OpenAI-compatible (`openai.OpenAI`)
**Max tokens:** 8000
**Temperature:** 0.0 (deterministic output)
**Response format:** `json_object`
**Thinking:** Disabled (`extra_body={"thinking": {"type": "disabled"}}`)

**Singleton:** `get_llm_gateway()` creates one `LLMGateway` instance.

### 6.2 How Many Times Is the LLM Called?

**Worst case (no cache hits):** One call per document.

- Max 2 EDGAR filings (8-K or 10-Q from last 180 days)
- Max 5 news articles
- **Maximum: 7 LLM calls per analysis**

**Typical case:**
- 1 EDGAR filing (most recent 8-K with EX-99 exhibit)
- 2-3 news articles
- **Typical: 3-4 LLM calls**

**Best case (all cache hits):**
- 0 LLM calls — everything served from `.llm_cache/`

**Cache hit scenario:**
- If you analyze the same ticker again and the documents haven't changed (same SHA-256 of text), ALL calls are cache hits
- Cache key is `SHA-256(source_type + ":" + raw_text)[:16]`
- So identical documents across analyses are cached, but a new filing (different text) means a fresh LLM call

### 6.3 LLM Call Flow (Single Document)

```
1. PREPARE PROMPT
   ├── get_prompt_for_source_type(source_type)
   │   ├── "earnings_call" → EARNINGS_CALL_PROMPT
   │   ├── "SEC_8K"/"SEC_10Q" → SEC_8K_PROMPT
   │   ├── "news_article"/"press_release" → NEWS_ARTICLE_PROMPT
   │   └── default → GENERAL_EXTRACTION_PROMPT
   └── prompt = template.replace("{document_chunk}", excerpt)

2. SANITIZE TEXT
   ├── Replace smart quotes: ' ' → ' ' , " " → " "
   ├── Replace em-dashes: — → --
   ├── Replace non-breaking spaces
   ├── Strip non-ASCII → replace with '?'
   ├── Collapse multiple spaces to single
   └── Collapse 3+ newlines to 2

3. CALL LLM (with retry)
   ├── Attempt 1: client.chat.completions.create(...)
   │   ├── model: "deepseek-v4-flash"
   │   ├── messages: [{"role": "user", "content": prompt}]
   │   ├── max_tokens: 8000
   │   ├── temperature: 0.0
   │   ├── response_format: {"type": "json_object"}
   │   └── extra_body: {"thinking": {"type": "disabled"}}
   │
   ├── On RateLimitError (429):
   │   └── Wait 2^attempt seconds, retry (max 5 attempts)
   │
   ├── On APIStatusError:
   │   └── Wait 2^attempt seconds, retry, return "{}" if all fail
   │
   └── On any Exception:
       └── Wait 1s, retry, return "{}" if all fail

4. PARSE RESPONSE
   ├── Strip ```json fences if present
   ├── Try json.loads(raw)
   ├── If JSONDecodeError:
   │   └── _repair_json():
   │       ├── Remove trailing commas before ] or }
   │       ├── Extract JSON object via regex r"\{[\s\S]*\}"
   │       └── Try json.loads(repaired)
   └── Return ExtractionResult(**data) or empty result
```

### 6.4 The Prompts

**Schema instructions** (appended to every prompt):
```
Return ONLY this json: {"guidance_items":[{"metric":"EPS|Revenue|GrossMargin|OperatingIncome|Other",
"value_low":n|null,"value_high":n|null,"value_midpoint":n|null,
"unit":"USD|USD_billions|percent|USD_millions","period_label":"str",
"fiscal_year":n|null,"fiscal_quarter":1-4|null,"is_official_guidance":bool,
"source_quote":"verbatim","confidence":"high|medium|low",
"guidance_type":"initial|raised|lowered|reiterated|withdrawn"}],
"document_type":"8-K|10-Q|earnings_call|press_release|news_article",
"company_name":"","reporting_period":"","extraction_notes":""}
OFFICIAL guidance only (management, not analysts). Numbers: $X.XX billion -> numeric.
```

**GENERAL_EXTRACTION_PROMPT:**
```
Extract ALL forward-looking management guidance from the document below.
For each: metric, numeric value/range, period, verbatim quote, is_official_guidance.

DOCUMENT:
{document_chunk}

{schema_instructions}
```

**EARNINGS_CALL_PROMPT:**
```
Extract guidance from this earnings call transcript. Management speakers
are labeled (e.g., "[CEO]: ...", "[CFO]: ..."). ONLY extract management guidance,
not analyst questions. Identify raised/lowered/reiterated vs prior guidance.

TRANSCRIPT:
{document_chunk}

{schema_instructions}
```

**SEC_8K_PROMPT:**
```
Extract forward-looking guidance from this SEC 8-K filing. Guidance is
typically in "Outlook" or "Guidance" sections. EXCLUDE historical results
(financial tables of past quarters). Only extract management's future projections.

FILING SECTION:
{document_chunk}

{schema_instructions}
```

**NEWS_ARTICLE_PROMPT:**
```
Extract guidance from this financial news article. Distinguish:
- Direct management quotes (is_official_guidance: true)
- Journalist summary of management statements (is_official_guidance: true)
- Analyst opinions (is_official_guidance: false)
Set extraction_confidence = 0.5 for news articles.

ARTICLE:
{document_chunk}

{schema_instructions}
```

### 6.5 Hallucination Guard

**File:** `backend/app/ai/hallucination_guard.py`

Validates LLM output against known financial data to catch hallucinations.

**EPS Validation:**
```
MAX_EPS_DEVIATION = 2.0  # 200% of TTM EPS

if current_eps_ttm is available:
    deviation = |extracted_eps - current_eps_ttm| / |current_eps_ttm|
    if deviation > 2.0:
        REJECT (not plausible — LLM hallucinated)

Example:
    TTM EPS = $5.00
    Extracted EPS = $0.89
    deviation = |0.89 - 5.00| / 5.00 = 0.822 = 82.2% < 200% → PASS

    TTM EPS = $5.00
    Extracted EPS = $50.00
    deviation = |50.00 - 5.00| / 5.00 = 9.0 = 900% > 200% → REJECT
```

**Revenue Validation:**
```
Convert to billions for comparison:
    USD_billions → as-is
    USD_millions → divide by 1000
    USD          → divide by 1e9

MAX_DEVIATION = 5.0  # 500% of TTM revenue

if current_revenue_ttm > 0:
    deviation = |extracted_revenue_bn - ttm_revenue_bn| / ttm_revenue_bn
    if deviation > 5.0:
        REJECT

Example:
    TTM Revenue = $100B
    Extracted = $185B
    deviation = |185 - 100| / 100 = 0.85 = 85% < 500% → PASS
```

**Quote Verification:**
```
1. Extract all numbers from the source quote: regex \$?(\d+\.?\d*)\s*(?:billion|million|trillion)?
2. Normalize: multiply by 1e9 for "billion", 1e6 for "million"
3. Check if any extracted number is within 10% of the claimed value

Example:
    source_quote = "revenue of $43.0 billion"
    extracted_numbers = [43.0] → normalized = [43e9]
    claimed_value = 43e9
    43e9 is within 10% of 43e9 → PASS

    source_quote = "revenue was $10B"
    claimed_value = 180e9
    No number within 10% of 180e9 → flag: "quote_mismatch"
```

**`filter_valid_items(result, eps_ttm, revenue_ttm)`:**
- Runs all validations
- Removes items that fail (where `valid=False`)
- Adds note to `extraction_notes`: "Filtered N invalid item(s)"

---

## 7. Token Usage Analysis Per Call

### 7.1 Input Tokens (Prompt + Document)

| Component | Approximate Characters | Approximate Tokens (÷4) |
|-----------|----------------------|------------------------|
| Prompt template (instructions) | ~1,200 chars | ~300 tokens |
| Schema instructions | ~650 chars | ~160 tokens |
| Document excerpt (smart_excerpt) | ~4,000 chars | ~1,000 tokens |
| **Total input per call** | **~5,850 chars** | **~1,460 tokens** |

### 7.2 Output Tokens (DeepSeek Response)

The LLM returns a JSON object with guidance items. Typical size:

```json
{
  "guidance_items": [
    {
      "metric": "EPS",
      "value_low": 0.87,
      "value_high": 0.91,
      "value_midpoint": 0.89,
      "unit": "USD",
      "period_label": "Q1 FY2027",
      "fiscal_year": 2027,
      "fiscal_quarter": 1,
      "is_official_guidance": true,
      "source_quote": "Non-GAAP diluted EPS is expected to be approximately $0.89, plus or minus $0.02.",
      "confidence": "high",
      "guidance_type": "initial"
    },
    {
      "metric": "Revenue",
      "value_low": 42.14,
      "value_high": 43.86,
      "value_midpoint": 43.0,
      "unit": "USD_billions",
      "period_label": "Q1 FY2027",
      "fiscal_year": 2027,
      "fiscal_quarter": 1,
      "is_official_guidance": true,
      "source_quote": "revenue to be approximately $43.0 billion, plus or minus 2%.",
      "confidence": "high",
      "guidance_type": "initial"
    }
  ],
  "document_type": "8-K",
  "company_name": "NVIDIA Corporation",
  "reporting_period": "Q4 FY2026",
  "extraction_notes": ""
}
```

| Metric | Typical Value |
|--------|--------------|
| Output tokens per guidance item | ~100-150 tokens |
| Items per document | 2-6 items |
| **Output per call (typical)** | **~400-800 tokens** |
| Output per call (max) | 8,000 tokens (capped) |

### 7.3 Total Tokens Per Analysis

| Scenario | LLM Calls | Input Tokens | Output Tokens | **Total** |
|----------|----------|-------------|---------------|--------|
| **All cache hits** | 0 | 0 | 0 | **0** |
| **1 doc, 1 call** | 1 | ~1,500 | ~500 | **~2,000** |
| **Typical (1 EDGAR + 2 news)** | 3 | ~4,500 | ~1,500 | **~6,000** |
| **Maximum (2 EDGAR + 5 news)** | 7 | ~10,500 | ~3,500 | **~14,000** |

### 7.4 Token Efficiency

The `_smart_excerpt()` function is the key efficiency mechanism. Without it, full SEC filings (15,000-50,000 characters, ~3,750-12,500 tokens) would be sent to the LLM. The smart excerpt cuts this to ~1,000 tokens by extracting only the guidance section — a **~75-92% reduction** in input tokens.

---

## 8. Caching

### 8.1 LLM Response Cache (`backend/.llm_cache/`)

**Location:** Filesystem, `backend/.llm_cache/{cache_key}.json`

**Cache key:** `SHA-256(source_type + ":" + raw_document_text)[:16]`

**What's cached:** The full `ExtractionResult` (guidance items, document type, company name, reporting period, extraction notes).

**Cache format:**
```json
{
  "guidance_items": [
    {
      "metric": "EPS",
      "value_low": 0.87,
      "value_high": 0.91,
      "value_midpoint": 0.89,
      ...
    }
  ],
  "document_type": "SEC_8K",
  "company_name": "NVIDIA Corporation",
  "reporting_period": "Q4 FY2026",
  "extraction_notes": ""
}
```

**Cache semantics:**
- Cache is based on document CONTENT, not ticker
- If the same document appears in a future analysis (same SEC filing URL/text), it's a cache hit
- A new quarterly filing (different text) = new cache key = fresh LLM call
- **No TTL / no expiry** — cache entries live forever unless manually deleted
- **No invalidation** — if the LLM model changes, old cached results persist

**Cache write:** `_save_cache()` in `guidance_service.py:61`
**Cache read:** `_load_cache()` in `guidance_service.py:43`

### 8.2 In-Memory Caches

| Cache | Location | Scope | Contents |
|-------|---------|-------|----------|
| CIK mapping | `edgar_client.py:_cik_cache` | Process lifetime | ticker → CIK mappings from SEC |
| YFinance client | `yfinance_client.py:get_yfinance_client` | Process lifetime (lru_cache) | Singleton client instance |
| TwelveData client | `twelvedata_client.py:get_twelvedata_client` | Process lifetime (lru_cache) | Singleton client instance |
| LLM gateway | `llm_gateway.py:get_llm_gateway` | Process lifetime | Singleton OpenAI client |

### 8.3 What's NOT Cached (but could be)

- **Stock financial data:** Fetched fresh from yfinance on every request (no request-level cache)
- **PE history:** Recalculated from raw price/EPS data on every request
- **Valuation results:** No result-level cache — every analysis is a fresh computation
- **Redis:** Client is defined (`redis_client.py`) but never used in the pipeline

---

## 9. Confidence Score: The Complete Math

### 9.1 Overview

Confidence is calculated in two layers:

1. **Guidance Confidence** (how reliable is the extracted guidance?)
2. **Valuation Confidence** (how reliable is the valuation given the guidance?)

The final score displayed in the frontend is **Valuation Confidence**.

---

### 9.2 Guidance Confidence

**Function:** `calculate_guidance_confidence(items, source_count, days_since_guidance, hallucination_flags)` in `confidence_service.py:26`

**Source quality weights:**
| Source Type | Weight |
|-------------|--------|
| SEC_8K | 1.0 |
| SEC_10Q | 1.0 |
| SEC_10K | 0.95 |
| earnings_call_transcript | 0.95 |
| press_release | 0.9 |
| investor_day | 0.85 |
| news_article | 0.5 |
| analyst_estimate | 0.3 |

**Guidance type modifiers:**
| Type | Modifier |
|------|----------|
| initial | 1.0 |
| reiterated | 0.95 |
| raised | 0.9 |
| lowered | 0.85 |
| analyst | 0.6 |
| ambiguous | 0.4 |

**Formula:**
```
score = 0.0

# Component 1: Source quality (40% weight)
avg_quality = mean of SOURCE_QUALITY_WEIGHTS for all items in pool
             (pool = official items if any exist, else all items)
score += 0.4 × avg_quality

# Component 2: Source diversity (20% weight)
unique_sources = count of distinct source_urls in pool
source_bonus = min(unique_sources / 3, 1.0)
score += 0.2 × source_bonus

# Component 3: Consensus tightness (20% weight)
if len(eps_items) >= 2:
    cv = std_dev(eps_values) / |mean(eps_values)|    # coefficient of variation
    consensus_score = max(0, 1 - cv × 5)
    score += 0.2 × consensus_score
else:
    score += 0.1   # no consensus measurement possible

# Component 4: Recency (10% weight)
if days_since_guidance is not None:
    recency = max(0, 1 - days_since_guidance / 90)   # linear decay over 90 days
    score += 0.1 × recency

# Penalty: Hallucination flags
score -= hallucination_flags × 0.1

# Final: Apply guidance type modifier
best_modifier = max(GUIDANCE_TYPE_MODIFIERS[item.guidance_type] for item in pool)
score = score × best_modifier

# Clamp to [0, 1], round to 2 decimal places
return round(max(0.0, min(1.0, score)), 2)
```

**Example 1: High-quality SEC 8-K with 2 sources, no issues**
```
Items: 2 EPS items from SEC_8K (weight 1.0), both official
Pool: 2 items
avg_quality = (1.0 + 1.0) / 2 = 1.0

Component 1: 0.4 × 1.0 = 0.40
Component 2: unique_sources = 2, bonus = min(2/3, 1.0) = 0.667
             0.2 × 0.667 = 0.133
Component 3: EPS values = [5.00, 4.90], mean=4.95, std=0.0707
             cv = 0.0707 / 4.95 = 0.0143
             consensus = max(0, 1 - 0.0143×5) = max(0, 0.9286) = 0.9286
             0.2 × 0.9286 = 0.186
Component 4: days_since_guidance = 1
             recency = max(0, 1 - 1/90) = 0.989
             0.1 × 0.989 = 0.099

score_before_modifier = 0.40 + 0.133 + 0.186 + 0.099 = 0.818
best_modifier = max(1.0) = 1.0  (both items "initial")
score = 0.818 × 1.0 = 0.82

→ guidance_confidence = 0.82
```

**Example 2: Single news article, no official guidance**
```
Items: 1 item from news_article (weight 0.5), is_official_guidance=False
Pool: ["news_article" → 0.5]
avg_quality = 0.5

Component 1: 0.4 × 0.5 = 0.20
Component 2: unique_sources = 1, bonus = min(1/3, 1.0) = 0.333
             0.2 × 0.333 = 0.067
Component 3: Only 1 EPS item → 0.1
Component 4: no days_since → no recency bonus

score_before_modifier = 0.20 + 0.067 + 0.1 = 0.367
best_modifier = 0.6 (analyst type for non-official)
score = 0.367 × 0.6 = 0.22

→ guidance_confidence = 0.22
```

**Example 3: Multiple official sources with hallucination flags**
```
Items: 3 items from various sources, 2 hallucination flags
(assume base score = 0.85 from components)
hallucination_penalty = 2 × 0.1 = 0.2
score = 0.85 - 0.2 = 0.65
best_modifier = 1.0
score = 0.65

→ guidance_confidence = 0.65
```

---

### 9.3 Valuation Confidence

**Function:** `calculate_valuation_confidence(guidance_confidence, pe_observation_count, negative_eps, has_guidance)` in `confidence_service.py:72`

**Formula:**
```
if negative_eps:
    return round(guidance_confidence × 0.5, 2)    # CAPPED: half of guidance confidence

if not has_guidance:
    return round(guidance_confidence × 0.6, 2)    # REDUCED: 60% of guidance confidence

# Normal case:
score = guidance_confidence × 0.7                  # guidance contributes 70%

if pe_observation_count:
    pe_bonus = min(pe_observation_count / 20, 1.0) # PE history contributes up to 30%
    score += 0.3 × pe_bonus

return round(max(0.0, min(1.0, score)), 2)
```

**Example 1: Perfect scenario**
```
guidance_confidence = 0.82
pe_observation_count = 20 (max bonus)
negative_eps = False
has_guidance = True

score = 0.82 × 0.7 = 0.574
pe_bonus = min(20/20, 1.0) = 1.0
score += 0.3 × 1.0 = 0.3

final = 0.574 + 0.3 = 0.874
→ valuation_confidence = 0.87
```

**Example 2: Negative EPS company**
```
guidance_confidence = 0.60
pe_observation_count = 15
negative_eps = True
has_guidance = True

final = 0.60 × 0.5 = 0.30
→ valuation_confidence = 0.30 (heavily penalized)
```

**Example 3: No extracted guidance (analyst consensus only)**
```
guidance_confidence = 0.30 (default analyst consensus)
pe_observation_count = 10
negative_eps = False
has_guidance = False

final = 0.30 × 0.6 = 0.18
→ valuation_confidence = 0.18
```

**Example 4: Low PE history**
```
guidance_confidence = 0.75
pe_observation_count = 5
negative_eps = False
has_guidance = True

score = 0.75 × 0.7 = 0.525
pe_bonus = min(5/20, 1.0) = 0.25
score += 0.3 × 0.25 = 0.075

final = 0.525 + 0.075 = 0.60
→ valuation_confidence = 0.60
```

---

### 9.4 Confidence Summary (Label Assignment)

**Function:** `calculate_confidence_summary(guidance, pe_observations, negative_eps, ...)`

```
if no guidance:
    guidance_confidence = 0.30 (default for analyst consensus)
    has_guidance = False
else:
    guidance_confidence = calculate_guidance_confidence(all_items, ...)
    has_guidance = len(all_items) > 0

valuation_confidence = calculate_valuation_confidence(
    guidance_confidence, pe_observations, negative_eps, has_guidance
)

# Label assignment (first match wins):
if valuation_confidence >= 0.8:  label = "HIGH"
elif valuation_confidence >= 0.5: label = "MEDIUM"
else:                             label = "LOW"
```

---

## 10. Frontend: How Confidence Is Displayed

### 10.1 ConfidenceMeter Component

**File:** `frontend/src/components/Dashboard/ConfidenceMeter.jsx`

```jsx
// Converts 0-1 score to percentage
const pct = Math.round((score || 0) * 100)

// Color coding:
pct >= 80 → emerald (green)  — HIGH
pct >= 50 → amber (yellow)   — MEDIUM
pct < 50  → red              — LOW
```

The component renders:
1. **Score as percentage** (e.g., "82%") with colored text
2. **Label badge** (HIGH / MEDIUM / LOW) with matching color
3. **Progress bar** — colored bar with `width: {pct}%`, animated with `transition-all duration-700`

### 10.2 Data Flow

```
Backend:          confidence.valuation_confidence = 0.82
                  confidence.confidence_label = "HIGH"
                  result.confidence_score = 0.82

Frontend receives: data.confidence.valuation_confidence
                   data.confidence.confidence_label

DashboardLayout:  <ConfidenceMeter
                     score={confidence?.valuation_confidence || result.confidence_score}
                     label={confidence?.confidence_label}
                   />
```

The `score` is always `valuation_confidence` (0-1 range), and the `label` is the human-readable category.

---

## 11. Valuation Engine Deep Dive

### 11.1 Complete Valuation Flow

```
Input: ticker, client (YFinanceClient)

1. get_stock_info(ticker)
   → current_price, eps_ttm, forward_eps, pe_ttm, revenue_ttm, market_cap

2. calculate_historical_median_pe(ticker, client, years=5)
   → median_pe, mean_pe, p25_pe, p75_pe, min_pe, max_pe, observations

3. Decision tree:

   ┌─ negative_eps AND pe_result?
   │  YES → _apply_ps_ratio_valuation()
   │        (PE meaningless for negative earnings)
   │
   ├─ pe_result AND guidance_eps > 0?
   │  YES → _apply_pe_valuation()
   │        estimated = guidance_eps × median_pe
   │        bull = guidance_eps × p75_pe
   │        bear = guidance_eps × p25_pe
   │        upside = (estimated - current) / current × 100
   │        valuation_method = "guided_eps_x_median_pe"
   │
   └─ guidance_eps > 0 AND pe_ttm > 0? (fallback)
      YES → Use current PE instead of historical median
            estimated = guidance_eps × pe_ttm
            bull = estimated × 1.3
            bear = estimated × 0.7
            valuation_method = "forward_eps_x_current_pe"
            low_confidence_flag = True

4. PEG sanity check:
   growth_rate = (forward_eps - eps_ttm) / eps_ttm
   peg = pe_ttm / (growth_rate × 100)
```

### 11.2 P/S Ratio Fallback (Negative EPS)

When EPS is negative, PE-based valuation is mathematically meaningless. The system falls back to Price-to-Sales:

```
ps_current = market_cap / revenue_ttm
estimated_ps = ps_current × 0.8    # conservative 20% haircut

Result stored in alternative_valuations.ps_ratio
valuation_method = "ps_ratio_fallback"
low_confidence_flag = True
```

### 11.3 Recalculation With Extracted EPS

After LLM guidance extraction, if extracted EPS is available:

```python
# _recalculate_with_extracted_eps() in analysis.py:193

extracted_eps = guidance_summary.eps_guidance.value_midpoint  # e.g., $0.89 for NVDA Q1

# Re-run PE calculation (may get new data)
pe_result = calculate_historical_median_pe(ticker, client)

median_pe = pe_result["median_pe"]  # e.g., 48.3
current_price = valuation["current_price"]  # e.g., $150

estimated = extracted_eps × median_pe    # 0.89 × 48.3 = $42.99
bull = extracted_eps × pe_result["p75_pe"]  # 0.89 × 61.4 = $54.65
bear = extracted_eps × pe_result["p25_pe"]  # 0.89 × 32.1 = $28.57
upside = (42.99 - 150) / 150 × 100 = -71.3%

valuation_method = "extracted_eps_x_median_pe"
```

**IMPORTANT NOTE about quarterly EPS:** In this example, NVDA's extracted Q1 guidance EPS is $0.89 (quarterly), which produces a much LOWER estimated price than the analyst forward EPS of $6.50 (annual). This is because `extracted_eps` from the LLM may be a quarterly figure while `forward_eps` from yfinance is annual. The system does not currently normalize between quarterly and annual EPS — this is a known limitation.

---

## 12. Guidance Resolution

### 12.1 Weighted Median

When multiple sources provide guidance for the same metric, the system resolves them using a **weighted median**:

```python
def _weighted_median(values, weights):
    # Sort by value
    sorted_pairs = sorted(zip(values, weights), key=lambda x: x[0])
    sorted_values, sorted_weights = zip(*sorted_pairs)

    # Find the value at the 50th percentile of cumulative weight
    cumsum = np.cumsum(sorted_weights)
    cutoff = cumsum[-1] / 2.0
    idx = np.searchsorted(cumsum, cutoff)
    return sorted_values[min(idx, len(sorted_values)-1)]
```

**Why weighted median instead of weighted mean?**
The weighted median is robust to outliers. If one source reports wildly different guidance (e.g., due to a different fiscal year interpretation), it doesn't skew the result as much as a mean would.

**Example:**
```
Source A (SEC_8K, weight 1.0):  EPS = $5.00
Source B (SEC_10Q, weight 1.0): EPS = $4.90
Source C (news_article, weight 0.5): EPS = $5.10

Sorted: [($4.90, 1.0), ($5.00, 1.0), ($5.10, 0.5)]
Cumsum: [1.0, 2.0, 2.5]
Cutoff: 2.5 / 2 = 1.25
Search: 1.25 falls between index 0 (1.0) and index 1 (2.0) → index 1
Result: $5.00
```

### 12.2 Conflict Detection

```python
def _detect_conflict(extractions):
    all_eps_values = [extract EPS midpoints from all extractions]
    if len(all_eps_values) < 2:
        return False

    deviation = (max - min) / |max|
    return deviation > 0.10  # 10% threshold
```

**Example:**
```
Source A: EPS = $5.00
Source B: EPS = $5.40
deviation = (5.40 - 5.00) / 5.40 = 0.074 = 7.4%
→ NO conflict (< 10%)

Source A: EPS = $4.00
Source B: EPS = $5.50
deviation = (5.50 - 4.00) / 5.50 = 0.273 = 27.3%
→ CONFLICT (> 10%)
```

### 12.3 Guidance Consolidation

```python
def _resolve_guidance(items, metric):
    official = [i for i in items if i.is_official_guidance]
    pool = official if official else items  # prefer official

    weighted_median_value = _weighted_median(values, weights)
    best_source = max(pool, key=lambda i: SOURCE_QUALITY_WEIGHTS[i.source_type])

    return GuidanceItem(
        metric=metric,
        value_midpoint=round(weighted_median_value, 4),
        value_low=min(values) if len(values) > 1 else None,
        value_high=max(values) if len(values) > 1 else None,
        unit=best_source.unit,
        period_label=best_source.period_label,
        # ... other fields from best_source
    )
```

---

## 13. Error Handling & Degradation

### 13.1 Degradation Tiers

The system is designed to degrade gracefully. Each failure adds a flag to `degradation.flags`:

| Flag | Meaning | Impact |
|------|---------|--------|
| `yfinance_rate_limited_using_twelvedata` | Primary data source throttled, using fallback | No PE history available (Twelve Data lacks it) |
| `valuation_failed` | Could not compute valuation | Request fails with 502 |
| `document_fetch_partial` | Some documents couldn't be fetched | Fewer sources for LLM extraction |
| `no_documents_found` | Zero documents discovered | Falls back to analyst consensus, guidance from forward EPS |
| `llm_extraction_succeeded` | LLM successfully extracted guidance | Positive flag — extraction worked |
| `llm_extraction_failed_using_fallback` | LLM extraction failed, using analyst consensus | Uses forward_eps from yfinance instead |
| `no_extracted_guidance` | No extracted guidance available | Falls back to analyst consensus |

### 13.2 Degradation Status

```python
is_degraded = any("failed" in f or "no_" in f for f in degradation_flags)
```

A degraded analysis still returns results but with lower confidence.

### 13.3 LLM Failure Recovery

```
try:
    result = await llm.extract_guidance(prompt, excerpt)
except Exception:
    logger.warning("LLM extraction failed")
    continue  # skip this document

# If ALL extractions fail:
if not all_items:
    return GuidanceSummary(overall_confidence=0.0)
    # System falls back to analyst_consensus
```

---

## 14. Database Schema

### 14.1 Stock
```sql
CREATE TABLE stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    cik VARCHAR(20),
    exchange VARCHAR(20),
    sector VARCHAR(100),
    industry VARCHAR(100),
    fiscal_year_end VARCHAR(5),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_stocks_ticker ON stocks(ticker);
CREATE INDEX idx_stocks_cik ON stocks(cik);
```

### 14.2 AnalysisRun
```sql
CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id UUID REFERENCES stocks(id),
    ticker VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    triggered_by VARCHAR(50),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    task_ids JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 14.3 Valuation
```sql
CREATE TABLE valuations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES analysis_runs(id),
    stock_id UUID REFERENCES stocks(id),
    ticker VARCHAR(10) NOT NULL,
    current_price NUMERIC(12,4),
    current_eps_ttm NUMERIC(10,4),
    current_revenue_ttm NUMERIC(20,2),
    guidance_eps NUMERIC(10,4),
    guidance_revenue NUMERIC(20,2),
    guidance_period VARCHAR(100),
    median_pe_used NUMERIC(10,4),
    pe_years_used INTEGER,
    pe_observation_count INTEGER,
    estimated_price NUMERIC(12,4),
    bull_price NUMERIC(12,4),
    bear_price NUMERIC(12,4),
    upside_pct NUMERIC(8,2),
    confidence_score FLOAT,
    valuation_method VARCHAR(50),
    alternative_valuations JSONB,
    negative_eps_flag BOOLEAN DEFAULT FALSE,
    low_confidence_flag BOOLEAN DEFAULT FALSE,
    insufficient_data_flag BOOLEAN DEFAULT FALSE,
    calculated_at TIMESTAMPTZ DEFAULT now()
);
```

### 14.4 PEHistory
```sql
CREATE TABLE pe_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id UUID REFERENCES stocks(id) NOT NULL,
    date DATE NOT NULL,
    price NUMERIC(12,4),
    eps_ttm NUMERIC(10,4),
    pe_ratio NUMERIC(10,4),
    data_source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(stock_id, date)
);
CREATE INDEX idx_pe_history_stock ON pe_history(stock_id);
```

### 14.5 SourceDocument
```sql
CREATE TABLE source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id UUID REFERENCES stocks(id),
    run_id UUID REFERENCES analysis_runs(id),
    source_url TEXT NOT NULL,
    source_type VARCHAR(50),
    document_title TEXT,
    document_date DATE,
    raw_text TEXT,
    word_count INTEGER,
    fetch_status VARCHAR(20) DEFAULT 'pending',
    fetched_at TIMESTAMPTZ DEFAULT now(),
    checksum VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_source_docs_checksum_status ON source_documents(checksum, fetch_status);
```

---

## Summary: Numbers At a Glance

| Metric | Value |
|--------|-------|
| **API Endpoints** | 5 (health, get stock, validate ticker, analyze, websocket) |
| **LLM Calls (typical)** | 3-4 per analysis |
| **LLM Calls (max)** | 7 per analysis |
| **Input Tokens per LLM call** | ~1,500 |
| **Output Tokens per LLM call** | ~500 |
| **Total Tokens (typical)** | ~6,000 |
| **Total Tokens (max)** | ~14,000 |
| **LLM Cache hits (re-analyze same ticker)** | 100% (if docs unchanged) |
| **Chunk size** | 800 tokens |
| **Smart excerpt size** | ~4,000 chars (~1,000 tokens) |
| **Embedding dimension** | 384 |
| **PE history years** | 5 |
| **PE observation threshold** | 5 minimum |
| **EPS deviation max** | 200% |
| **Revenue deviation max** | 500% |
| **Conflict threshold** | 10% EPS spread |
| **Confidence: HIGH** | ≥ 80% |
| **Confidence: MEDIUM** | 50-79% |
| **Confidence: LOW** | < 50% |
| **EDGAR rate limit** | 10 requests/second |
| **yfinance retries** | 3, exponential backoff |
| **LLM retries** | 5, exponential backoff |
| **Frontend API timeout** | 90 seconds |
| **WebSocket timeout** | 30 seconds |
