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
