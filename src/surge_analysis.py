"""Surge analysis module for the EDA Financial Discussions pipeline.

This module provides functions to operationalize the surge definition,
normalize engagement metrics per ticker, compute surge labels, and
evaluate multiple surge definitions for class balance.
"""

import logging
from itertools import product

import numpy as np
import pandas as pd

from src.models import SurgeConfig, SurgeResult

logger = logging.getLogger(__name__)


def normalize_engagement(
    df: pd.DataFrame, metric_cols: list[str], ticker_col: str
) -> pd.DataFrame:
    """Normalize engagement metrics relative to each ticker's historical baseline.

    For each ticker, computes z-score normalization of engagement metrics
    using that ticker's own mean and standard deviation. This ensures that
    normalized values reflect each ticker's individual distribution rather
    than the global distribution across all tickers.

    For tickers with zero standard deviation (constant engagement), the
    normalized value is set to 0.0 (no deviation from baseline).

    Args:
        df: DataFrame containing engagement metrics and a ticker column.
        metric_cols: List of column names containing engagement metrics to normalize.
        ticker_col: Name of the column containing stock ticker symbols.

    Returns:
        A new DataFrame with the same index as the input, containing normalized
        versions of the specified metric columns. Normalized columns are named
        with a '_normalized' suffix (e.g., 'likes' -> 'likes_normalized').
        Original columns and other columns are preserved unchanged.

    Raises:
        ValueError: If ticker_col is not present in the DataFrame.
        ValueError: If any column in metric_cols is not present in the DataFrame.
    """
    if ticker_col not in df.columns:
        raise ValueError(
            f"Ticker column '{ticker_col}' not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )

    missing_cols = [col for col in metric_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Metric columns not found in DataFrame: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    if df.empty:
        result = df.copy()
        for col in metric_cols:
            result[f"{col}_normalized"] = pd.Series(dtype="float64")
        return result

    result = df.copy()

    for col in metric_cols:
        normalized_col = f"{col}_normalized"
        # Compute per-ticker mean and std
        grouped = df.groupby(ticker_col)[col]
        ticker_means = grouped.transform("mean")
        ticker_stds = grouped.transform("std", ddof=0)

        # Z-score normalization: (value - mean) / std
        # Where std is 0 (constant values), set normalized to 0.0
        normalized_values = pd.Series(0.0, index=df.index, dtype="float64")
        non_zero_std = ticker_stds > 0
        normalized_values[non_zero_std] = (
            (df[col][non_zero_std] - ticker_means[non_zero_std])
            / ticker_stds[non_zero_std]
        )

        result[normalized_col] = normalized_values

    return result


def check_timestamp_resolution(df: pd.DataFrame, timestamp_col: str) -> dict:
    """Check if timestamps support 24-hour window measurement.

    Analyzes the timestamp column to determine whether the data has sufficient
    temporal resolution to measure 24-hour windows for surge detection.

    Args:
        df: DataFrame containing a timestamp column.
        timestamp_col: Name of the column containing timestamps.

    Returns:
        A dictionary with:
            - 'sufficient': bool indicating if resolution supports 24-hour windows
            - 'resolution': str describing the detected resolution (e.g., 'seconds', 'days')
            - 'median_gap_hours': float median time gap between consecutive posts
            - 'min_gap_hours': float minimum time gap between consecutive posts
            - 'recommendation': str with guidance on feasibility

    Raises:
        ValueError: If timestamp_col is not present in the DataFrame.
        ValueError: If the column cannot be converted to datetime.
    """
    if timestamp_col not in df.columns:
        raise ValueError(
            f"Timestamp column '{timestamp_col}' not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )

    if df.empty or len(df) < 2:
        return {
            "sufficient": False,
            "resolution": "unknown",
            "median_gap_hours": float("nan"),
            "min_gap_hours": float("nan"),
            "recommendation": "Insufficient data to assess timestamp resolution.",
        }

    try:
        timestamps = pd.to_datetime(df[timestamp_col])
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Cannot convert column '{timestamp_col}' to datetime: {e}"
        )

    sorted_ts = timestamps.sort_values().reset_index(drop=True)
    diffs = sorted_ts.diff().dropna()

    if diffs.empty:
        return {
            "sufficient": False,
            "resolution": "unknown",
            "median_gap_hours": float("nan"),
            "min_gap_hours": float("nan"),
            "recommendation": "Cannot compute time differences.",
        }

    # Convert to hours
    gap_hours = diffs.dt.total_seconds() / 3600.0
    median_gap = float(gap_hours.median())
    min_gap = float(gap_hours.min())

    # Determine resolution
    if min_gap < 1.0 / 60:  # Less than 1 minute
        resolution = "seconds"
    elif min_gap < 1.0:  # Less than 1 hour
        resolution = "minutes"
    elif min_gap < 24.0:  # Less than 1 day
        resolution = "hours"
    else:
        resolution = "days"

    # Sufficient if we can distinguish within 24-hour windows
    # Need sub-day resolution to meaningfully measure 24-hour windows
    sufficient = resolution in ("seconds", "minutes", "hours")

    if sufficient:
        recommendation = (
            f"Timestamp resolution ({resolution}) is sufficient for 24-hour "
            f"window measurement. Median gap: {median_gap:.2f} hours."
        )
    else:
        recommendation = (
            f"Timestamp resolution ({resolution}) may be insufficient for precise "
            f"24-hour window measurement. Consider approximate windowing. "
            f"Median gap: {median_gap:.2f} hours."
        )

    return {
        "sufficient": sufficient,
        "resolution": resolution,
        "median_gap_hours": median_gap,
        "min_gap_hours": min_gap,
        "recommendation": recommendation,
    }


def compute_surge_labels(
    df: pd.DataFrame,
    config: SurgeConfig,
    engagement_cols: list[str],
    sentiment_col: str,
    timestamp_col: str,
    ticker_col: str,
) -> pd.Series:
    """Compute binary surge labels for each post.

    A post is labeled as a surge if:
    1. Its normalized engagement exceeds the configured percentile threshold
       (across any of the engagement columns), AND
    2. The sentiment shift exceeds the configured standard deviation threshold
       within the configured time window.

    Engagement is normalized per-ticker before applying the percentile threshold.
    Sentiment shift is computed as the absolute deviation from the ticker's mean
    sentiment within the time window preceding and including the post.

    Args:
        df: DataFrame containing engagement metrics, sentiment, timestamps,
            and ticker columns.
        config: SurgeConfig with engagement_percentile, sentiment_std_devs,
            and time_window_hours parameters.
        engagement_cols: List of column names containing engagement metrics.
        sentiment_col: Name of the column containing sentiment values.
        timestamp_col: Name of the column containing timestamps.
        ticker_col: Name of the column containing stock ticker symbols.

    Returns:
        A boolean Series with the same index as the input DataFrame, where
        True indicates the post is classified as a surge.

    Raises:
        ValueError: If required columns are missing from the DataFrame.
    """
    # Validate required columns
    required_cols = engagement_cols + [sentiment_col, timestamp_col, ticker_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Required columns not found in DataFrame: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    if df.empty:
        return pd.Series(dtype="bool")

    # Ensure timestamps are datetime
    working_df = df.copy()
    working_df[timestamp_col] = pd.to_datetime(working_df[timestamp_col])

    # Step 1: Normalize engagement per ticker
    normalized_df = normalize_engagement(working_df, engagement_cols, ticker_col)

    # Step 2: Compute engagement threshold
    # A post exceeds the engagement threshold if ANY normalized engagement
    # metric is above the configured percentile for its ticker
    norm_cols = [f"{col}_normalized" for col in engagement_cols]

    engagement_exceeds = pd.Series(False, index=df.index)
    for col in norm_cols:
        # Compute the percentile threshold per ticker
        percentile_thresholds = normalized_df.groupby(ticker_col)[col].transform(
            lambda x: x.quantile(config.engagement_percentile)
        )
        engagement_exceeds = engagement_exceeds | (
            normalized_df[col] >= percentile_thresholds
        )

    # Step 3: Compute sentiment shift within time window
    # For each post, compute whether the sentiment deviates significantly
    # from the ticker's mean sentiment within the time window
    sentiment_exceeds = pd.Series(False, index=df.index)

    # Compute per-ticker sentiment statistics
    ticker_sentiment_mean = working_df.groupby(ticker_col)[sentiment_col].transform("mean")
    ticker_sentiment_std = working_df.groupby(ticker_col)[sentiment_col].transform(
        lambda x: x.std(ddof=0)
    )

    # A post has a sentiment shift if its sentiment deviates from the ticker mean
    # by more than the configured number of standard deviations
    sentiment_deviation = (working_df[sentiment_col] - ticker_sentiment_mean).abs()

    # Handle case where std is 0 (constant sentiment) - no shift possible
    non_zero_std = ticker_sentiment_std > 0
    sentiment_exceeds[non_zero_std] = (
        sentiment_deviation[non_zero_std]
        > config.sentiment_std_devs * ticker_sentiment_std[non_zero_std]
    )

    # Step 4: Apply time window constraint
    # Check that the sentiment shift occurs within the configured time window
    # by verifying that there are other posts from the same ticker within the window
    time_window = pd.Timedelta(hours=config.time_window_hours)
    has_window_context = pd.Series(False, index=df.index)

    for ticker in working_df[ticker_col].unique():
        ticker_mask = working_df[ticker_col] == ticker
        ticker_timestamps = working_df.loc[ticker_mask, timestamp_col].sort_values()

        if len(ticker_timestamps) < 2:
            # Cannot compute time window with single post
            continue

        # For each post, check if there's at least one other post within the window
        for idx in ticker_timestamps.index:
            post_time = working_df.loc[idx, timestamp_col]
            window_start = post_time - time_window
            # Posts within the window (excluding the post itself)
            window_posts = ticker_timestamps[
                (ticker_timestamps >= window_start)
                & (ticker_timestamps <= post_time)
                & (ticker_timestamps.index != idx)
            ]
            if len(window_posts) > 0:
                has_window_context.loc[idx] = True

    # Surge = engagement exceeds threshold AND sentiment shift exceeds threshold
    # AND there is time window context available
    surge_labels = engagement_exceeds & sentiment_exceeds & has_window_context

    return surge_labels


def evaluate_surge_definitions(
    df: pd.DataFrame,
    percentiles: list[float],
    std_devs: list[float],
    engagement_cols: list[str],
    sentiment_col: str,
    timestamp_col: str,
    ticker_col: str,
) -> list[SurgeResult]:
    """Evaluate multiple surge definitions and report class balance.

    Iterates over all combinations of percentiles and standard deviation
    thresholds, computes surge labels for each combination, and reports
    the resulting class balance metrics. Flags definitions where the
    positive class (surge) represents less than 2% of total records as
    non-viable.

    Args:
        df: DataFrame containing engagement metrics, sentiment, timestamps,
            and ticker columns.
        percentiles: List of engagement percentile thresholds to evaluate
            (e.g., [0.90, 0.95, 0.99]).
        std_devs: List of sentiment standard deviation thresholds to evaluate
            (e.g., [0.5, 1.0, 1.5]).
        engagement_cols: List of column names containing engagement metrics.
        sentiment_col: Name of the column containing sentiment values.
        timestamp_col: Name of the column containing timestamps.
        ticker_col: Name of the column containing stock ticker symbols.

    Returns:
        A list of SurgeResult objects, one for each combination of percentile
        and standard deviation threshold. Each result includes surge count,
        total posts, surge percentage, class imbalance ratio, viability flag,
        and timestamp sufficiency.
    """
    results: list[SurgeResult] = []

    # Check timestamp resolution once (same for all combinations)
    ts_resolution = check_timestamp_resolution(df, timestamp_col)
    timestamp_sufficient = ts_resolution["sufficient"]

    total_posts = len(df)

    for percentile, std_dev in product(percentiles, std_devs):
        config = SurgeConfig(
            engagement_percentile=percentile,
            sentiment_std_devs=std_dev,
            time_window_hours=24,
        )

        # Compute surge labels for this configuration
        surge_labels = compute_surge_labels(
            df, config, engagement_cols, sentiment_col, timestamp_col, ticker_col
        )

        surge_count = int(surge_labels.sum())

        # Compute surge percentage
        if total_posts > 0:
            surge_percentage = (surge_count / total_posts) * 100.0
        else:
            surge_percentage = 0.0

        # Compute class imbalance ratio (non-surge : surge)
        non_surge_count = total_posts - surge_count
        if surge_count > 0:
            class_imbalance_ratio = non_surge_count / surge_count
        else:
            class_imbalance_ratio = float("inf")

        # Flag as non-viable if positive class < 2%
        is_viable = surge_percentage >= 2.0

        result = SurgeResult(
            config=config,
            surge_count=surge_count,
            total_posts=total_posts,
            surge_percentage=surge_percentage,
            class_imbalance_ratio=class_imbalance_ratio,
            is_viable=is_viable,
            timestamp_sufficient=timestamp_sufficient,
        )
        results.append(result)

        logger.info(
            f"Surge definition (p={percentile}, std={std_dev}): "
            f"{surge_count}/{total_posts} ({surge_percentage:.2f}%) "
            f"{'viable' if is_viable else 'NON-VIABLE'}"
        )

    return results
