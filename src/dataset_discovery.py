"""Kaggle dataset discovery module for the EDA Financial Discussions pipeline.

This module provides functionality to search and discover datasets on Kaggle
that are relevant to financial discussion analysis, including stock sentiment,
social media engagement, and related topics.
"""

import logging
from datetime import datetime, timezone

from src.models import DatasetMetadata

logger = logging.getLogger(__name__)

# Columns that indicate engagement metrics are present
ENGAGEMENT_KEYWORDS: set[str] = {
    "likes",
    "retweets",
    "comments",
    "upvotes",
    "shares",
    "favorites",
    "score",
    "num_comments",
    "comment_count",
    "like_count",
    "retweet_count",
}

# Columns that indicate sentiment fields are present
SENTIMENT_KEYWORDS: set[str] = {
    "sentiment",
    "polarity",
    "bullish",
    "bearish",
    "positive",
    "negative",
    "sentiment_score",
}


def _check_engagement_metrics(columns: list[str], title: str = "") -> bool:
    """Check if columns or title suggest engagement metrics are present.

    Args:
        columns: List of column names from the dataset.
        title: Dataset title used as fallback when columns are unavailable.

    Returns:
        True if engagement metrics are detected.
    """
    if columns:
        columns_lower = {col.lower() for col in columns}
        return bool(columns_lower & ENGAGEMENT_KEYWORDS)
    # Fallback: check title/description keywords
    title_lower = title.lower()
    return any(
        keyword in title_lower
        for keyword in ("engagement", "likes", "retweets", "comments", "upvotes")
    )


def _check_sentiment_fields(columns: list[str], title: str = "") -> bool:
    """Check if columns or title suggest sentiment fields are present.

    Args:
        columns: List of column names from the dataset.
        title: Dataset title used as fallback when columns are unavailable.

    Returns:
        True if sentiment fields are detected.
    """
    if columns:
        columns_lower = {col.lower() for col in columns}
        return bool(columns_lower & SENTIMENT_KEYWORDS)
    # Fallback: check title/description keywords
    title_lower = title.lower()
    return any(
        keyword in title_lower
        for keyword in ("sentiment", "polarity", "bullish", "bearish")
    )


def _compute_freshness_days(last_updated: datetime) -> int:
    """Compute the number of days since the dataset was last updated.

    Args:
        last_updated: The datetime when the dataset was last updated.

    Returns:
        Number of days since last update.
    """
    now = datetime.now(timezone.utc)
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    delta = now - last_updated
    return max(0, delta.days)


def scan_kaggle(search_terms: list[str]) -> list[DatasetMetadata]:
    """Search Kaggle for datasets matching the given search terms.

    Uses the Kaggle API to discover datasets relevant to financial discussions,
    stock sentiment, and social media engagement analysis. Deduplicates results
    across search terms by dataset name.

    Args:
        search_terms: List of search query strings to use when querying Kaggle.

    Returns:
        List of DatasetMetadata objects for discovered datasets.
        Returns an empty list if network or authentication errors occur.

    Example:
        >>> datasets = scan_kaggle(["stock twitter sentiment", "reddit finance"])
        >>> for ds in datasets:
        ...     print(f"{ds.name} - complete: {ds.is_complete}")
    """
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
    except Exception as e:
        logger.warning(
            "Failed to initialize Kaggle API: %s. Returning empty results.", e
        )
        return []

    seen_names: set[str] = set()
    datasets: list[DatasetMetadata] = []
    total_found = False

    for term in search_terms:
        try:
            results = api.dataset_list(search=term)
        except Exception as e:
            logger.warning(
                "Network error searching Kaggle for '%s': %s", term, e
            )
            continue

        if not results:
            continue

        total_found = True

        for dataset in results:
            # Use ref as the unique identifier (owner/dataset-name)
            name = getattr(dataset, "ref", None) or getattr(dataset, "title", str(dataset))
            if name in seen_names:
                continue
            seen_names.add(name)

            # Extract record count (downloadCount as proxy if totalBytes not available)
            record_count = getattr(dataset, "downloadCount", 0) or 0

            # Compute freshness from lastUpdated
            last_updated = getattr(dataset, "lastUpdated", None)
            if last_updated:
                if isinstance(last_updated, str):
                    try:
                        last_updated = datetime.fromisoformat(
                            last_updated.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        last_updated = datetime.now(timezone.utc)
                freshness_days = _compute_freshness_days(last_updated)
                end_date = last_updated.strftime("%Y-%m-%d")
            else:
                freshness_days = -1
                end_date = "unknown"

            # Date range: use lastUpdated as end, estimate start as unknown
            start_date = "unknown"
            date_range = (start_date, end_date)

            # Attempt to get column information
            columns: list[str] = []
            try:
                # Try to get dataset metadata for column info
                dataset_files = api.dataset_list_files(name)
                if hasattr(dataset_files, "files") and dataset_files.files:
                    # Column info from file metadata if available
                    for f in dataset_files.files:
                        if hasattr(f, "columns") and f.columns:
                            columns.extend(
                                col if isinstance(col, str) else getattr(col, "name", str(col))
                                for col in f.columns
                            )
                            break
            except Exception:
                # Column info not readily available from search API;
                # fall back to title-based heuristics
                pass

            title = getattr(dataset, "title", name) or name

            has_engagement = _check_engagement_metrics(columns, title)
            has_sentiment = _check_sentiment_fields(columns, title)
            is_complete = has_engagement and has_sentiment

            metadata = DatasetMetadata(
                name=name,
                source_platform="kaggle",
                record_count=record_count,
                date_range=date_range,
                columns=columns,
                freshness_days=freshness_days,
                has_engagement_metrics=has_engagement,
                has_sentiment_fields=has_sentiment,
                is_complete=is_complete,
            )
            datasets.append(metadata)

    if not total_found:
        logger.warning(
            "No datasets found on Kaggle for search criteria: %s", search_terms
        )

    return datasets
