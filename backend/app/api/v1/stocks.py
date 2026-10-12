from fastapi import APIRouter, HTTPException

from app.ingestion.yfinance_client import get_yfinance_client

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{ticker}")
async def get_stock(ticker: str):
    client = get_yfinance_client()
    info = client.get_stock_info(ticker)
    if not info.get("current_price") and not info.get("eps_ttm"):
        if client.is_rate_limited():
            raise HTTPException(status_code=503, detail="Financial data source is temporarily unavailable. Please try again later.")
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found or has no data.")
    return {"ticker": ticker.upper(), **info}


@router.get("/{ticker}/validate")
async def validate_ticker(ticker: str):
    client = get_yfinance_client()
    result = client.validate_ticker(ticker)
    if result is None:
        if client.is_rate_limited():
            raise HTTPException(status_code=503, detail="Financial data source is temporarily unavailable. Please try again later.")
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found")
    return result
