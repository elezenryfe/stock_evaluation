import uuid
from datetime import datetime, date

from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Date, DateTime, Numeric, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PEHistory(Base):
    __tablename__ = "pe_history"
    __table_args__ = (UniqueConstraint("stock_id", "date"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stocks.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4))
    eps_ttm: Mapped[float] = mapped_column(Numeric(10, 4))
    pe_ratio: Mapped[float] = mapped_column(Numeric(10, 4))
    data_source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Valuation(Base):
    __tablename__ = "valuations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id")
    )
    stock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stocks.id")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)

    current_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    current_eps_ttm: Mapped[float | None] = mapped_column(Numeric(10, 4))
    current_revenue_ttm: Mapped[float | None] = mapped_column(Numeric(20, 2))
    guidance_eps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    guidance_revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    guidance_period: Mapped[str | None] = mapped_column(String(100))
    median_pe_used: Mapped[float | None] = mapped_column(Numeric(10, 4))
    pe_years_used: Mapped[int | None] = mapped_column(Integer)
    pe_observation_count: Mapped[int | None] = mapped_column(Integer)

    estimated_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    bull_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    bear_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    upside_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    valuation_method: Mapped[str | None] = mapped_column(String(50))

    alternative_valuations: Mapped[dict | None] = mapped_column(JSONB)

    negative_eps_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    low_confidence_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    insufficient_data_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
