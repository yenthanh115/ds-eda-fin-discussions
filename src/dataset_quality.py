"""Dataset quality analysis module for the EDA Financial Discussions pipeline.

This module provides functions to analyze the structure and quality of
candidate datasets, including schema documentation, missing values,
time coverage, engagement distributions, sentiment analysis, and risk cataloging.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def analyze_structure(df: pd.DataFrame, ticker_col: str = "ticker") -> dict[str, Any]:
    """Document dataset structure including schema, types, record count, and ticker count.

    Args:
        df: The DataFrame to analyze.
        ticker_col: Name of the column containing stock ticker symbols.

    Returns:
        Dictionary with keys:
        - schema: dict mapping column name -> dtype string
        - record_count: total number of rows
        - column_count: total number of columns
        - ticker_count: number of unique tickers (0 if ticker_col not present)
        - columns: list of column names
    """
    schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
    record_count = len(df)
    column_count = len(df.columns)

    ticker_count = 0
    if ticker_col in df.columns:
        ticker_count = df[ticker_col].nunique()

    return {
        "schema": schema,
        "record_count": record_count,
        "column_count": column_count,
        "ticker_count": ticker_count,
        "columns": list(df.columns),
    }



def compute_missing_values(df: pd.DataFrame) -> dict[str, Any]:
    """Compute per-column missing value percentages and flag high-risk columns.

    A column is flagged as high-risk if more than 30% of its values are missing.

    Args:
        df: The DataFrame to analyze.

    Returns:
        Dictionary with keys:
        - missing_percentages: dict mapping column name -> missing percentage (0-100)
        - high_risk_columns: list of column names with >30% missing
    """
    if len(df) == 0:
        return {
            "missing_percentages": {col: 0.0 for col in df.columns},
            "high_risk_columns": [],
        }

    total_rows = len(df)
    missing_percentages: dict[str, float] = {}
    high_risk_columns: list[str] = []

    for col in df.columns:
        missing_count = df[col].isna().sum()
        pct = (missing_count / total_rows) * 100.0
        missing_percentages[col] = pct
        if pct > 30.0:
            high_risk_columns.append(col)

    return {
        "missing_percentages": missing_percentages,
        "high_risk_columns": high_risk_columns,
    }



def analyze_time_coverage(
    df: pd.DataFrame, date_col: str
) -> dict[str, Any]:
    """Analyze time coverage including date range, gaps >7 days, and posting frequency.

    Args:
        df: The DataFrame to analyze.
        date_col: Name of the column containing date/timestamp values.

    Returns:
        Dictionary with keys:
        - date_range: tuple (min_date, max_date) as ISO date strings
        - temporal_gaps: list of tuples (gap_start, gap_end) for gaps > 7 days
        - posting_frequency: dict with 'posts_per_day' average and 'total_days' span
        - gap_count: number of gaps > 7 days found
    """
    if date_col not in df.columns:
        logger.warning("Date column '%s' not found in DataFrame.", date_col)
        return {
            "date_range": ("unknown", "unknown"),
            "temporal_gaps": [],
            "posting_frequency": {"posts_per_day": 0.0, "total_days": 0},
            "gap_count": 0,
        }

    # Convert to datetime, coercing errors
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()

    if len(dates) == 0:
        logger.warning("No valid dates found in column '%s'.", date_col)
        return {
            "date_range": ("unknown", "unknown"),
            "temporal_gaps": [],
            "posting_frequency": {"posts_per_day": 0.0, "total_days": 0},
            "gap_count": 0,
        }

    dates_sorted = dates.sort_values().reset_index(drop=True)
    min_date = dates_sorted.iloc[0]
    max_date = dates_sorted.iloc[-1]

    date_range = (min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d"))

    # Find temporal gaps > 7 days
    temporal_gaps: list[tuple[str, str]] = []
    seven_days = pd.Timedelta(days=7)

    for i in range(1, len(dates_sorted)):
        gap = dates_sorted.iloc[i] - dates_sorted.iloc[i - 1]
        if gap > seven_days:
            gap_start = dates_sorted.iloc[i - 1].strftime("%Y-%m-%d")
            gap_end = dates_sorted.iloc[i].strftime("%Y-%m-%d")
            temporal_gaps.append((gap_start, gap_end))

    # Compute posting frequency
    total_days = (max_date - min_date).days
    if total_days > 0:
        posts_per_day = len(dates) / total_days
    else:
        posts_per_day = float(len(dates))  # All posts on same day

    return {
        "date_range": date_range,
        "temporal_gaps": temporal_gaps,
        "posting_frequency": {
            "posts_per_day": posts_per_day,
            "total_days": total_days,
        },
        "gap_count": len(temporal_gaps),
    }
