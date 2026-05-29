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



def compute_engagement_distributions(
    df: pd.DataFrame, metric_cols: list[str]
) -> dict[str, dict[str, float]]:
    """Compute summary statistics for engagement metrics.

    For each metric column, computes mean, median, and percentiles
    (90th, 95th, 99th).

    Args:
        df: The DataFrame containing engagement data.
        metric_cols: List of column names with numeric engagement metrics.

    Returns:
        Dictionary mapping metric name -> {mean, median, p90, p95, p99}.
        Columns not found or non-numeric are skipped with a warning.
    """
    results: dict[str, dict[str, float]] = {}

    for col in metric_cols:
        if col not in df.columns:
            logger.warning("Engagement column '%s' not found in DataFrame.", col)
            continue

        series = pd.to_numeric(df[col], errors="coerce").dropna()

        if len(series) == 0:
            logger.warning("No valid numeric data in column '%s'.", col)
            continue

        results[col] = {
            "mean": float(series.mean()),
            "median": float(series.median()),
            "p90": float(series.quantile(0.90)),
            "p95": float(series.quantile(0.95)),
            "p99": float(series.quantile(0.99)),
        }

    return results



def analyze_sentiment(
    df: pd.DataFrame, text_col: str
) -> dict[str, Any]:
    """Perform sentiment distribution analysis and compute bullish-to-bearish ratio.

    Uses VADER sentiment analyzer to compute polarity scores for each text entry,
    then generates distribution statistics and the bullish/bearish ratio.

    Args:
        df: The DataFrame containing text data.
        text_col: Name of the column containing text content.

    Returns:
        Dictionary with keys:
        - polarity_scores: dict with mean, median, std of compound scores
        - bullish_count: number of positive sentiment posts (compound > 0.05)
        - bearish_count: number of negative sentiment posts (compound < -0.05)
        - neutral_count: number of neutral posts
        - bullish_bearish_ratio: ratio of bullish to bearish (inf if bearish=0)
        - total_analyzed: number of texts analyzed
    """
    if text_col not in df.columns:
        logger.warning("Text column '%s' not found in DataFrame.", text_col)
        return {
            "polarity_scores": {"mean": 0.0, "median": 0.0, "std": 0.0},
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "bullish_bearish_ratio": 0.0,
            "total_analyzed": 0,
        }

    texts = df[text_col].dropna().astype(str)
    if len(texts) == 0:
        logger.warning("No valid text data in column '%s'.", text_col)
        return {
            "polarity_scores": {"mean": 0.0, "median": 0.0, "std": 0.0},
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "bullish_bearish_ratio": 0.0,
            "total_analyzed": 0,
        }

    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        analyzer = SentimentIntensityAnalyzer()
    except ImportError:
        logger.warning(
            "vaderSentiment not available. Skipping sentiment analysis."
        )
        return {
            "polarity_scores": {"mean": 0.0, "median": 0.0, "std": 0.0},
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "bullish_bearish_ratio": 0.0,
            "total_analyzed": 0,
        }

    compound_scores = []
    for text in texts:
        scores = analyzer.polarity_scores(text)
        compound_scores.append(scores["compound"])

    import numpy as np

    scores_arr = np.array(compound_scores)

    bullish_count = int(np.sum(scores_arr > 0.05))
    bearish_count = int(np.sum(scores_arr < -0.05))
    neutral_count = int(len(scores_arr) - bullish_count - bearish_count)

    if bearish_count > 0:
        ratio = bullish_count / bearish_count
    else:
        ratio = float("inf") if bullish_count > 0 else 0.0

    return {
        "polarity_scores": {
            "mean": float(np.mean(scores_arr)),
            "median": float(np.median(scores_arr)),
            "std": float(np.std(scores_arr)),
        },
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "bullish_bearish_ratio": ratio,
        "total_analyzed": len(compound_scores),
    }


def assess_sentiment_reliability(
    df: pd.DataFrame, text_col: str
) -> dict[str, Any]:
    """Compare at least two sentiment methods for inter-method agreement.

    Compares VADER (lexicon-based) with TextBlob (pattern-based) to assess
    whether sentiment can be extracted reliably from the text content.

    Args:
        df: The DataFrame containing text data.
        text_col: Name of the column containing text content.

    Returns:
        Dictionary with keys:
        - agreement_rate: proportion of texts where both methods agree on polarity
        - correlation: Pearson correlation between the two methods' scores
        - vader_mean: mean VADER compound score
        - textblob_mean: mean TextBlob polarity score
        - methods_compared: list of method names used
        - total_compared: number of texts compared
    """
    if text_col not in df.columns:
        logger.warning("Text column '%s' not found in DataFrame.", text_col)
        return {
            "agreement_rate": 0.0,
            "correlation": 0.0,
            "vader_mean": 0.0,
            "textblob_mean": 0.0,
            "methods_compared": [],
            "total_compared": 0,
        }

    texts = df[text_col].dropna().astype(str).tolist()
    if len(texts) == 0:
        return {
            "agreement_rate": 0.0,
            "correlation": 0.0,
            "vader_mean": 0.0,
            "textblob_mean": 0.0,
            "methods_compared": [],
            "total_compared": 0,
        }

    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        from textblob import TextBlob
    except ImportError as e:
        logger.warning(
            "Sentiment libraries not available: %s. Cannot assess reliability.", e
        )
        return {
            "agreement_rate": 0.0,
            "correlation": 0.0,
            "vader_mean": 0.0,
            "textblob_mean": 0.0,
            "methods_compared": [],
            "total_compared": 0,
        }

    import numpy as np

    vader = SentimentIntensityAnalyzer()
    vader_scores = []
    textblob_scores = []

    for text in texts:
        vader_scores.append(vader.polarity_scores(text)["compound"])
        textblob_scores.append(TextBlob(text).sentiment.polarity)

    vader_arr = np.array(vader_scores)
    textblob_arr = np.array(textblob_scores)

    # Agreement: both positive, both negative, or both neutral
    def _polarity_class(score: float, threshold: float = 0.05) -> int:
        if score > threshold:
            return 1
        elif score < -threshold:
            return -1
        return 0

    agreements = sum(
        1
        for v, t in zip(vader_scores, textblob_scores)
        if _polarity_class(v) == _polarity_class(t)
    )
    agreement_rate = agreements / len(texts) if texts else 0.0

    # Pearson correlation
    if len(vader_arr) > 1 and np.std(vader_arr) > 0 and np.std(textblob_arr) > 0:
        correlation = float(np.corrcoef(vader_arr, textblob_arr)[0, 1])
    else:
        correlation = 0.0

    return {
        "agreement_rate": agreement_rate,
        "correlation": correlation,
        "vader_mean": float(np.mean(vader_arr)),
        "textblob_mean": float(np.mean(textblob_arr)),
        "methods_compared": ["vader", "textblob"],
        "total_compared": len(texts),
    }



def compare_stock_vs_general(
    stock_df: pd.DataFrame, general_df: pd.DataFrame, metric_cols: list[str] | None = None
) -> dict[str, Any]:
    """Compare engagement patterns between stock-specific and general discussions.

    Computes summary statistics for engagement metrics in both DataFrames
    and reports differences to validate that stock discussions exhibit
    distinct engagement behavior.

    Args:
        stock_df: DataFrame containing stock-specific discussion data.
        general_df: DataFrame containing general discussion data.
        metric_cols: List of engagement metric column names to compare.
            If None, auto-detects numeric columns present in both DataFrames.

    Returns:
        Dictionary with keys:
        - metrics_compared: list of metric names compared
        - stock_stats: dict of metric -> {mean, median, std}
        - general_stats: dict of metric -> {mean, median, std}
        - differences: dict of metric -> {mean_diff, median_diff, mean_ratio}
        - distinct_behavior: bool indicating if stock engagement differs notably
    """
    import numpy as np

    if metric_cols is None:
        # Auto-detect numeric columns present in both DataFrames
        stock_numeric = set(stock_df.select_dtypes(include="number").columns)
        general_numeric = set(general_df.select_dtypes(include="number").columns)
        metric_cols = sorted(stock_numeric & general_numeric)

    if not metric_cols:
        logger.warning("No common numeric columns found for comparison.")
        return {
            "metrics_compared": [],
            "stock_stats": {},
            "general_stats": {},
            "differences": {},
            "distinct_behavior": False,
        }

    stock_stats: dict[str, dict[str, float]] = {}
    general_stats: dict[str, dict[str, float]] = {}
    differences: dict[str, dict[str, float]] = {}

    notable_differences = 0

    for col in metric_cols:
        if col not in stock_df.columns or col not in general_df.columns:
            continue

        stock_series = pd.to_numeric(stock_df[col], errors="coerce").dropna()
        general_series = pd.to_numeric(general_df[col], errors="coerce").dropna()

        if len(stock_series) == 0 or len(general_series) == 0:
            continue

        s_mean = float(stock_series.mean())
        s_median = float(stock_series.median())
        s_std = float(stock_series.std()) if len(stock_series) > 1 else 0.0

        g_mean = float(general_series.mean())
        g_median = float(general_series.median())
        g_std = float(general_series.std()) if len(general_series) > 1 else 0.0

        stock_stats[col] = {"mean": s_mean, "median": s_median, "std": s_std}
        general_stats[col] = {"mean": g_mean, "median": g_median, "std": g_std}

        mean_diff = s_mean - g_mean
        median_diff = s_median - g_median
        mean_ratio = s_mean / g_mean if g_mean != 0 else float("inf")

        differences[col] = {
            "mean_diff": mean_diff,
            "median_diff": median_diff,
            "mean_ratio": mean_ratio,
        }

        # Consider notable if ratio > 1.5 or < 0.67 (50% difference)
        if mean_ratio > 1.5 or (mean_ratio < 0.67 and mean_ratio > 0):
            notable_differences += 1

    # Distinct behavior if at least half of metrics show notable differences
    compared_count = len(differences)
    distinct = (
        notable_differences >= max(1, compared_count // 2)
        if compared_count > 0
        else False
    )

    return {
        "metrics_compared": list(differences.keys()),
        "stock_stats": stock_stats,
        "general_stats": general_stats,
        "differences": differences,
        "distinct_behavior": distinct,
    }



def catalog_risks(
    df: pd.DataFrame,
    missing_result: dict[str, Any] | None = None,
    time_result: dict[str, Any] | None = None,
    date_col: str = "date",
    ticker_col: str = "ticker",
) -> list[str]:
    """Catalog data quality issues, biases, temporal leakage risks, and coverage gaps.

    Inspects the DataFrame and optional pre-computed analysis results to
    identify and document all discovered risks.

    Args:
        df: The DataFrame to analyze.
        missing_result: Pre-computed result from compute_missing_values (optional).
        time_result: Pre-computed result from analyze_time_coverage (optional).
        date_col: Name of the date/timestamp column.
        ticker_col: Name of the ticker column.

    Returns:
        List of risk description strings.
    """
    risks: list[str] = []

    # --- Data Quality Issues ---

    # Check for high-risk missing columns
    if missing_result and missing_result.get("high_risk_columns"):
        cols = missing_result["high_risk_columns"]
        risks.append(
            f"High missing data: columns {cols} have >30% missing values, "
            "which may bias analysis or require imputation."
        )

    # Check for very small dataset
    if len(df) < 1000:
        risks.append(
            f"Small dataset ({len(df)} rows): may be insufficient for "
            "reliable statistical analysis and surge detection."
        )

    # Check for duplicate rows
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        dup_pct = (dup_count / len(df)) * 100 if len(df) > 0 else 0
        risks.append(
            f"Duplicate rows detected: {dup_count} duplicates ({dup_pct:.1f}%), "
            "which may inflate engagement statistics."
        )

    # --- Temporal Leakage Risks ---

    # Check if date column exists and is sorted
    if date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if len(dates) > 0:
            # Check for future dates
            now = pd.Timestamp.now()
            future_count = (dates > now).sum()
            if future_count > 0:
                risks.append(
                    f"Future dates detected: {future_count} rows have dates "
                    "in the future, indicating potential data quality issues."
                )
    else:
        risks.append(
            f"No date column '{date_col}' found: temporal analysis and "
            "24-hour surge windowing cannot be performed."
        )

    # Check temporal gaps from pre-computed results
    if time_result and time_result.get("gap_count", 0) > 0:
        gap_count = time_result["gap_count"]
        risks.append(
            f"Temporal gaps: {gap_count} gaps >7 days detected, "
            "which may cause discontinuities in surge detection."
        )

    # --- Bias Risks ---

    # Check ticker distribution skew
    if ticker_col in df.columns:
        ticker_counts = df[ticker_col].value_counts()
        if len(ticker_counts) > 1:
            top_pct = (ticker_counts.iloc[0] / len(df)) * 100
            if top_pct > 50:
                risks.append(
                    f"Ticker imbalance: top ticker '{ticker_counts.index[0]}' "
                    f"represents {top_pct:.1f}% of data, which may bias "
                    "per-ticker normalization."
                )
    else:
        risks.append(
            f"No ticker column '{ticker_col}' found: per-ticker "
            "engagement normalization cannot be performed."
        )

    # --- Coverage Gaps ---

    # Check for limited time span
    if time_result and time_result.get("posting_frequency"):
        total_days = time_result["posting_frequency"].get("total_days", 0)
        if 0 < total_days < 90:
            risks.append(
                f"Short time span ({total_days} days): less than 3 months "
                "of data may not capture seasonal patterns in engagement."
            )

    return risks
