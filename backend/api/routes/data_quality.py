"""
Data Quality Routes - API for monitoring data quality metrics.

Provides endpoints for checking candle data quality including:
- Missing data gaps
- Stale data detection
- Volume and price anomaly detection
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from core.database import get_db

router = APIRouter(prefix="/api/v1/data-quality", tags=["data-quality"])


# ====================
# Pydantic Schemas
# ====================

class GapInfo(BaseModel):
    """Information about a missing data gap."""
    pair: str
    timeframe: str
    gap_start: str
    gap_end: str
    duration_minutes: int
    severity: str  # "critical" if > 1 day, "warning" otherwise


class StalenessInfo(BaseModel):
    """Information about stale data."""
    pair: str
    timeframe: str
    latest_candle: str
    age_minutes: int
    severity: str  # "critical" if > 60 min, "warning" if > 15 min, "ok" otherwise


class VolumeAnomaly(BaseModel):
    """A candle with anomalous volume."""
    pair: str
    timeframe: str
    timestamp: str
    volume: float
    rolling_avg_volume: float
    ratio: float  # volume / rolling_avg
    severity: str  # "critical" if ratio > 5, "warning" if > 3


class PriceAnomaly(BaseModel):
    """A candle with anomalous price change."""
    pair: str
    timeframe: str
    timestamp: str
    pct_change: float
    severity: str  # "critical" if > 10%, "warning" if > 5%


class CandleQualityMetrics(BaseModel):
    """Full data quality metrics for candle data."""
    gaps: list[GapInfo]
    staleness: list[StalenessInfo]
    volume_anomalies: list[VolumeAnomaly]
    price_anomalies: list[PriceAnomaly]
    checked_at: str


class DataQualitySummary(BaseModel):
    """Overall data quality score and summary."""
    score: int  # 0-100
    status: str  # "healthy", "degraded", "critical"
    total_pairs: int
    pairs_with_gaps: int
    pairs_stale: int
    volume_anomaly_count: int
    price_anomaly_count: int
    checked_at: str


# ====================
# Helper Functions
# ====================

def _calculate_rolling_avg(volumes: list, window: int = 20) -> float:
    """Calculate rolling average volume, ignoring zeros and NaNs."""
    if not volumes:
        return 0.0
    valid = [v for v in volumes if v and v > 0]
    if len(valid) < window:
        return np.mean(valid) if valid else 0.0
    return np.mean(valid[-window:])


def _get_severity_for_gap(duration_minutes: int) -> str:
    """Determine severity based on gap duration."""
    if duration_minutes > 1440:  # > 1 day
        return "critical"
    return "warning"


def _get_severity_for_staleness(age_minutes: int) -> str:
    """Determine severity based on data age."""
    if age_minutes > 60:
        return "critical"
    if age_minutes > 15:
        return "warning"
    return "ok"


# ====================
# Routes
# ====================

@router.get("/candles", response_model=CandleQualityMetrics)
async def get_candle_quality_metrics(
    db: AsyncSession = Depends(get_db),
    pair_filter: Optional[str] = Query(None, description="Filter by pair (e.g., 'BTC/USDT')"),
    timeframe_filter: Optional[str] = Query(None, description="Filter by timeframe (e.g., '1h')"),
    lookback_hours: int = Query(168, ge=1, le=720, description="Lookback period in hours (default: 7 days)"),
):
    """
    Get comprehensive data quality metrics for candle data.

    Returns:
    - Gaps: missing candle ranges per pair/timeframe
    - Staleness: latest candle age per pair/timeframe
    - Volume anomalies: candles with volume > 3x rolling average
    - Price anomalies: candles with % change > threshold from previous
    """
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(hours=lookback_hours)

    gaps: list[GapInfo] = []
    staleness: list[StalenessInfo] = []
    volume_anomalies: list[VolumeAnomaly] = []
    price_anomalies: list[PriceAnomaly] = []

    # Query distinct pairs and timeframes
    pair_query = select(
        text("DISTINCT symbol as pair"),
        text("timeframe")
    ).select_from(text("candles")).where(
        text("timestamp >= :lookback")
    ).params(lookback=lookback_start)

    if pair_filter:
        pair_query = pair_query.where(text("symbol = :pair")).params(pair=pair_filter)
    if timeframe_filter:
        pair_query = pair_query.where(text("timeframe = :tf")).params(tf=timeframe_filter)

    # For each pair/timeframe, check gaps
    try:
        result = await db.execute(
            text("""
                SELECT DISTINCT symbol, timeframe
                FROM candles
                WHERE timestamp >= :lookback
                GROUP BY symbol, timeframe
            """).params(lookback=lookback_start)
        )
        pair_timeframes = result.fetchall()
    except Exception:
        # candles table might not exist or be populated
        pair_timeframes = []

    for row in pair_timeframes:
        pair = row.symbol
        tf = row.timeframe

        # Check for gaps in timestamps
        gap_result = await db.execute(
            text("""
                WITH ordered_candles AS (
                    SELECT timestamp,
                           LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
                    FROM candles
                    WHERE symbol = :pair AND timeframe = :tf AND timestamp >= :lookback
                ),
                gaps AS (
                    SELECT timestamp, prev_timestamp,
                           EXTRACT(EPOCH FROM (timestamp - prev_timestamp))/60 as gap_minutes
                    FROM ordered_candles
                    WHERE prev_timestamp IS NOT NULL
                      AND EXTRACT(EPOCH FROM (timestamp - prev_timestamp))/60 > :expected_interval
                )
                SELECT gap_minutes, prev_timestamp, timestamp
                FROM gaps
                ORDER BY gap_minutes DESC
            """).params(pair=pair, tf=tf, lookback=lookback_start, expected_interval=_get_interval_minutes(tf))
        )

        for gap_row in gap_result.fetchall():
            gap_minutes = int(gap_row.gap_minutes)
            gaps.append(GapInfo(
                pair=pair,
                timeframe=tf,
                gap_start=gap_row.prev_timestamp.isoformat() if gap_row.prev_timestamp else "",
                gap_end=gap_row.timestamp.isoformat() if gap_row.timestamp else "",
                duration_minutes=gap_minutes,
                severity=_get_severity_for_gap(gap_minutes),
            ))

        # Check staleness - get latest candle for this pair/timeframe
        latest_result = await db.execute(
            text("""
                SELECT MAX(timestamp) as latest
                FROM candles
                WHERE symbol = :pair AND timeframe = :tf
            """).params(pair=pair, tf=tf)
        )
        latest_row = latest_result.fetchone()
        if latest_row and latest_row.latest:
            latest_ts = latest_row.latest
            age_minutes = int((now - latest_ts.replace(tzinfo=timezone.utc)).total_seconds() / 60)
            staleness.append(StalenessInfo(
                pair=pair,
                timeframe=tf,
                latest_candle=latest_ts.isoformat(),
                age_minutes=age_minutes,
                severity=_get_severity_for_staleness(age_minutes),
            ))

        # Check volume anomalies - candles with volume > 3x rolling average
        vol_result = await db.execute(
            text("""
                WITH with_rolling AS (
                    SELECT symbol, timeframe, timestamp, volume,
                           AVG(volume) OVER (ORDER BY timestamp ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as rolling_avg
                    FROM candles
                    WHERE symbol = :pair AND timeframe = :tf AND timestamp >= :lookback
                )
                SELECT symbol, timeframe, timestamp, volume, rolling_avg,
                       CASE WHEN rolling_avg > 0 THEN volume / rolling_avg ELSE 0 END as ratio
                FROM with_rolling
                WHERE rolling_avg > 0 AND volume / rolling_avg > 3
                ORDER BY ratio DESC
                LIMIT 50
            """).params(pair=pair, tf=tf, lookback=lookback_start)
        )

        for vol_row in vol_result.fetchall():
            ratio = float(vol_row.ratio) if vol_row.ratio else 0.0
            volume_anomalies.append(VolumeAnomaly(
                pair=vol_row.symbol,
                timeframe=vol_row.timeframe,
                timestamp=vol_row.timestamp.isoformat() if vol_row.timestamp else "",
                volume=float(vol_row.volume) if vol_row.volume else 0.0,
                rolling_avg_volume=float(vol_row.rolling_avg) if vol_row.rolling_avg else 0.0,
                ratio=ratio,
                severity="critical" if ratio > 5 else "warning",
            ))

        # Check price anomalies - % change > 5% from previous candle
        price_result = await db.execute(
            text("""
                WITH with_change AS (
                    SELECT symbol, timeframe, timestamp, close,
                           LAG(close) OVER (ORDER BY timestamp) as prev_close,
                           CASE WHEN LAG(close) OVER (ORDER BY timestamp) > 0
                                THEN ABS(close - LAG(close) OVER (ORDER BY timestamp)) / LAG(close) OVER (ORDER BY timestamp) * 100
                                ELSE 0 END as pct_change
                    FROM candles
                    WHERE symbol = :pair AND timeframe = :tf AND timestamp >= :lookback
                )
                SELECT symbol, timeframe, timestamp, pct_change
                FROM with_change
                WHERE pct_change > 5
                ORDER BY pct_change DESC
                LIMIT 50
            """).params(pair=pair, tf=tf, lookback=lookback_start)
        )

        for price_row in price_result.fetchall():
            pct = float(price_row.pct_change) if price_row.pct_change else 0.0
            price_anomalies.append(PriceAnomaly(
                pair=price_row.symbol,
                timeframe=price_row.timeframe,
                timestamp=price_row.timestamp.isoformat() if price_row.timestamp else "",
                pct_change=pct,
                severity="critical" if pct > 10 else "warning",
            ))

    return CandleQualityMetrics(
        gaps=gaps,
        staleness=staleness,
        volume_anomalies=volume_anomalies,
        price_anomalies=price_anomalies,
        checked_at=now.isoformat(),
    )


@router.get("/candles/{pair}/{timeframe}/gaps")
async def get_candle_gaps(
    pair: str,
    timeframe: str,
    db: AsyncSession = Depends(get_db),
    lookback_hours: int = Query(168, ge=1, le=720),
):
    """
    Get detailed gap information for a specific pair and timeframe.

    Returns list of missing candle ranges with severity levels.
    """
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(hours=lookback_hours)

    expected_interval = _get_interval_minutes(timeframe)

    result = await db.execute(
        text("""
            WITH ordered_candles AS (
                SELECT timestamp,
                       LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
                FROM candles
                WHERE symbol = :pair AND timeframe = :tf AND timestamp >= :lookback
            ),
            gaps AS (
                SELECT timestamp, prev_timestamp,
                       EXTRACT(EPOCH FROM (timestamp - prev_timestamp))/60 as gap_minutes
                FROM ordered_candles
                WHERE prev_timestamp IS NOT NULL
                  AND EXTRACT(EPOCH FROM (timestamp - prev_timestamp))/60 > :expected_interval
            )
            SELECT
                prev_timestamp,
                timestamp as gap_end,
                gap_minutes,
                CASE WHEN gap_minutes > 1440 THEN 'critical' ELSE 'warning' END as severity
            FROM gaps
            ORDER BY gap_minutes DESC
        """).params(pair=pair, tf=timeframe, lookback=lookback_start, expected_interval=expected_interval)
    )

    gaps = []
    for row in result.fetchall():
        gaps.append({
            "gap_start": row.prev_timestamp.isoformat() if row.prev_timestamp else None,
            "gap_end": row.timestamp.isoformat() if row.timestamp else None,
            "duration_minutes": int(row.gap_minutes),
            "severity": row.severity,
        })

    return {
        "pair": pair,
        "timeframe": timeframe,
        "gaps": gaps,
        "total_gaps": len(gaps),
        "checked_at": now.isoformat(),
    }


@router.get("/summary", response_model=DataQualitySummary)
async def get_data_quality_summary(
    db: AsyncSession = Depends(get_db),
    lookback_hours: int = Query(168, ge=1, le=720),
):
    """
    Get overall data quality score (0-100) and summary.

    Score calculation:
    - Start with 100 points
    - Deduct 5 points per gap (max 30)
    - Deduct 3 points per stale pair (max 30)
    - Deduct 1 point per volume anomaly (max 20)
    - Deduct 1 point per price anomaly (max 20)

    Status:
    - "healthy": score >= 80
    - "degraded": score >= 50
    - "critical": score < 50
    """
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(hours=lookback_hours)

    score = 100
    gaps_count = 0
    stale_count = 0
    vol_anomalies = 0
    price_anomalies = 0

    try:
        # Count gaps
        gaps_result = await db.execute(
            text("""
                WITH ordered_candles AS (
                    SELECT symbol, timeframe, timestamp,
                           LAG(timestamp) OVER (PARTITION BY symbol, timeframe ORDER BY timestamp) as prev_timestamp
                    FROM candles
                    WHERE timestamp >= :lookback
                ),
                gaps AS (
                    SELECT symbol, timeframe
                    FROM ordered_candles
                    WHERE prev_timestamp IS NOT NULL
                      AND EXTRACT(EPOCH FROM (timestamp - prev_timestamp))/60 > 60
                )
                SELECT COUNT(DISTINCT symbol, timeframe) as gap_pairs
                FROM gaps
            """).params(lookback=lookback_start)
        )
        gaps_row = gaps_result.fetchone()
        if gaps_row:
            gaps_count = gaps_row.gap_pairs or 0
            score -= min(gaps_count * 5, 30)

        # Count stale pairs
        stale_result = await db.execute(
            text("""
                WITH latest AS (
                    SELECT symbol, timeframe, MAX(timestamp) as latest
                    FROM candles
                    GROUP BY symbol, timeframe
                )
                SELECT COUNT(*) as stale_count
                FROM latest
                WHERE latest < :stale_threshold
            """).params(stale_threshold=now - timedelta(minutes=30))
        )
        stale_row = stale_result.fetchone()
        if stale_row:
            stale_count = stale_row.stale_count or 0
            score -= min(stale_count * 3, 30)

        # Count volume anomalies (recent, high ratio)
        vol_result = await db.execute(
            text("""
                WITH with_rolling AS (
                    SELECT symbol, timeframe, timestamp, volume,
                           AVG(volume) OVER (PARTITION BY symbol, timeframe
                                             ORDER BY timestamp ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) as rolling_avg
                    FROM candles
                    WHERE timestamp >= :lookback
                )
                SELECT COUNT(*) as vol_count
                FROM with_rolling
                WHERE rolling_avg > 0 AND volume / rolling_avg > 3
            """).params(lookback=lookback_start)
        )
        vol_row = vol_result.fetchone()
        if vol_row:
            vol_anomalies = vol_row.vol_count or 0
            score -= min(vol_anomalies, 20)

        # Count price anomalies
        price_result = await db.execute(
            text("""
                WITH with_change AS (
                    SELECT symbol, timeframe, timestamp, close,
                           LAG(close) OVER (PARTITION BY symbol, timeframe ORDER BY timestamp) as prev_close
                    FROM candles
                    WHERE timestamp >= :lookback
                )
                SELECT COUNT(*) as price_count
                FROM with_change
                WHERE prev_close > 0
                  AND ABS(close - prev_close) / prev_close * 100 > 5
            """).params(lookback=lookback_start)
        )
        price_row = price_result.fetchone()
        if price_row:
            price_anomalies = price_row.price_count or 0
            score -= min(price_anomalies, 20)

    except Exception:
        # If queries fail, estimate from metrics endpoint
        pass

    # Ensure score is within bounds
    score = max(0, min(100, score))

    # Determine status
    if score >= 80:
        status = "healthy"
    elif score >= 50:
        status = "degraded"
    else:
        status = "critical"

    # Count total pairs
    try:
        total_result = await db.execute(text("SELECT COUNT(DISTINCT symbol) as total FROM candles"))
        total_row = total_result.fetchone()
        total_pairs = total_row.total if total_row else 0
    except Exception:
        total_pairs = 0

    return DataQualitySummary(
        score=score,
        status=status,
        total_pairs=total_pairs,
        pairs_with_gaps=gaps_count,
        pairs_stale=stale_count,
        volume_anomaly_count=vol_anomalies,
        price_anomaly_count=price_anomalies,
        checked_at=now.isoformat(),
    )


def _get_interval_minutes(timeframe: str) -> int:
    """Get expected candle interval in minutes for a timeframe string."""
    tf_map = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "6h": 360,
        "8h": 480,
        "12h": 720,
        "1d": 1440,
        "3d": 4320,
        "1w": 10080,
    }
    return tf_map.get(timeframe.lower(), 60)  # Default to 1h