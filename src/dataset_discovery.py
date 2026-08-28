"""Dataset discovery module for the EDA Financial Discussions pipeline.

This module provides functionality to search and discover datasets on Kaggle
and HuggingFace that are relevant to financial discussion analysis, including
stock sentiment, social media engagement, and related topics.
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

            # Extract download count
            download_count = getattr(dataset, "downloadCount", 0) or 0

            # Attempt to get actual record count from dataset size info
            record_count = 0
            total_bytes = getattr(dataset, "totalBytes", None)
            if total_bytes and total_bytes > 0:
                # Rough heuristic: estimate rows from file size (not reliable, but better than 0)
                # We'll try to get actual count from metadata below
                pass

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

            # Attempt to get column information and record count
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
                    # Try to get record count from file row count if available
                    for f in dataset_files.files:
                        file_rows = getattr(f, "rowCount", None) or getattr(f, "totalRows", None)
                        if file_rows and file_rows > 0:
                            record_count += file_rows
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
                download_count=download_count,
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


def scan_huggingface(search_terms: list[str]) -> list[DatasetMetadata]:
    """Search HuggingFace for datasets matching the given search terms.

    Uses the huggingface_hub library to discover datasets relevant to financial
    discussions, stock sentiment, and social media engagement analysis.
    Deduplicates results across search terms by dataset ID.

    Args:
        search_terms: List of search query strings to use when querying HuggingFace.

    Returns:
        List of DatasetMetadata objects for discovered datasets.
        Returns an empty list if network errors occur.

    Example:
        >>> datasets = scan_huggingface(["stock sentiment", "financial tweets"])
        >>> for ds in datasets:
        ...     print(f"{ds.name} - complete: {ds.is_complete}")
    """
    try:
        from huggingface_hub import HfApi, list_datasets
    except ImportError as e:
        logger.warning(
            "huggingface_hub not available: %s. Returning empty results.", e
        )
        return []

    seen_names: set[str] = set()
    datasets: list[DatasetMetadata] = []
    total_found = False

    for term in search_terms:
        try:
            results = list(list_datasets(search=term, limit=50))
        except Exception as e:
            logger.warning(
                "Network error searching HuggingFace for '%s': %s", term, e
            )
            continue

        if not results:
            continue

        total_found = True

        for dataset in results:
            # Use dataset id as unique identifier (e.g., "username/dataset-name")
            name = getattr(dataset, "id", None) or str(dataset)
            if name in seen_names:
                continue
            seen_names.add(name)

            # Extract download count
            download_count = 0
            if hasattr(dataset, "downloads"):
                download_count = getattr(dataset, "downloads", 0) or 0

            # Actual record count — will attempt to fetch from dataset card
            record_count = 0

            # Compute freshness from lastModified
            last_modified = getattr(dataset, "lastModified", None) or getattr(
                dataset, "last_modified", None
            )
            if last_modified:
                if isinstance(last_modified, str):
                    try:
                        last_modified = datetime.fromisoformat(
                            last_modified.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        last_modified = datetime.now(timezone.utc)
                freshness_days = _compute_freshness_days(last_modified)
                end_date = last_modified.strftime("%Y-%m-%d")
            else:
                freshness_days = -1
                end_date = "unknown"

            start_date = "unknown"
            date_range = (start_date, end_date)

            # HuggingFace datasets may expose column info via dataset card or features
            columns: list[str] = []
            try:
                api = HfApi()
                info = api.dataset_info(name)
                if hasattr(info, "card_data") and info.card_data:
                    # Some datasets expose features in card_data
                    features = getattr(info.card_data, "features", None)
                    if features and isinstance(features, dict):
                        columns = list(features.keys())
                    # Try to get record count from dataset_size or download_size
                    dataset_size = getattr(info.card_data, "dataset_size", None)
                    if dataset_size and isinstance(dataset_size, int):
                        record_count = dataset_size
                # Try dataset_info num_rows from config metadata
                if record_count == 0 and hasattr(info, "card_data") and info.card_data:
                    configs = getattr(info.card_data, "configs", None) or getattr(
                        info.card_data, "dataset_info", None
                    )
                    if configs and isinstance(configs, list):
                        for config in configs:
                            if isinstance(config, dict):
                                splits = config.get("splits", [])
                                if isinstance(splits, list):
                                    for split in splits:
                                        if isinstance(split, dict):
                                            num_rows = split.get("num_examples", 0) or split.get("num_rows", 0)
                                            record_count += num_rows
            except Exception:
                # Column info not readily available; fall back to title heuristics
                pass

            # Use dataset id or tags for title-based heuristics
            title = name
            tags = getattr(dataset, "tags", []) or []
            if tags:
                title = f"{name} {' '.join(tags)}"

            has_engagement = _check_engagement_metrics(columns, title)
            has_sentiment = _check_sentiment_fields(columns, title)
            is_complete = has_engagement and has_sentiment

            metadata = DatasetMetadata(
                name=name,
                source_platform="huggingface",
                record_count=record_count,
                download_count=download_count,
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
            "No datasets found on HuggingFace for search criteria: %s",
            search_terms,
        )

    return datasets


def flag_incomplete_datasets(
    datasets: list[DatasetMetadata],
) -> list[DatasetMetadata]:
    """Flag datasets that are missing engagement metrics or sentiment fields.

    A dataset is considered incomplete for surge prediction if it lacks either
    engagement metrics OR sentiment-related fields. This function updates the
    `is_complete` flag on each dataset accordingly.

    Args:
        datasets: List of DatasetMetadata objects to evaluate.

    Returns:
        The same list with `is_complete` flags updated. Datasets missing
        engagement metrics or sentiment fields will have `is_complete = False`.
    """
    for dataset in datasets:
        has_engagement = _check_engagement_metrics(
            dataset.columns, dataset.name
        )
        has_sentiment = _check_sentiment_fields(
            dataset.columns, dataset.name
        )
        dataset.has_engagement_metrics = has_engagement
        dataset.has_sentiment_fields = has_sentiment
        dataset.is_complete = has_engagement and has_sentiment

    return datasets


def filter_datasets(
    datasets: list[DatasetMetadata],
    *,
    require_complete: bool = False,
    min_download_count: int = 0,
    max_freshness_days: int = -1,
    min_record_count: int = 0,
    top_k: int = 0,
) -> list[DatasetMetadata]:
    """Filter and rank discovered datasets to reduce noise.

    Applies configurable criteria to remove low-quality or irrelevant datasets,
    then optionally ranks the remainder by a relevance score and returns only
    the top-k results.

    Filtering criteria (applied in order):
    - require_complete: Keep only datasets with both engagement + sentiment fields.
    - min_download_count: Keep only datasets with at least this many downloads.
    - max_freshness_days: Keep only datasets updated within this many days (ignored if <= 0).
    - min_record_count: Keep only datasets with at least this many records (ignored if 0
      since record_count is often unknown/0 from API metadata).

    Ranking (when top_k > 0):
    Datasets are scored by a weighted combination of:
    - Completeness (has both engagement + sentiment): +50 points
    - Has engagement OR sentiment: +20 points
    - Download popularity: log10(download_count + 1) * 10
    - Freshness: higher score for more recently updated datasets
    - Record count known: +10 bonus if record_count > 0

    Args:
        datasets: List of DatasetMetadata objects to filter.
        require_complete: If True, only keep datasets where is_complete=True.
        min_download_count: Minimum download count threshold.
        max_freshness_days: Maximum days since last update (<=0 means no limit).
        min_record_count: Minimum record count (0 means don't filter on this).
        top_k: If > 0, return only the top_k highest-scored datasets.

    Returns:
        Filtered (and optionally ranked/truncated) list of DatasetMetadata.
    """
    import math

    filtered = list(datasets)

    # Apply hard filters
    if require_complete:
        filtered = [d for d in filtered if d.is_complete]

    if min_download_count > 0:
        filtered = [d for d in filtered if d.download_count >= min_download_count]

    if max_freshness_days > 0:
        filtered = [
            d for d in filtered
            if d.freshness_days >= 0 and d.freshness_days <= max_freshness_days
        ]

    if min_record_count > 0:
        filtered = [d for d in filtered if d.record_count >= min_record_count]

    # Rank by relevance score if top_k is requested
    if top_k > 0 and len(filtered) > top_k:
        def _score(d: DatasetMetadata) -> float:
            score = 0.0
            # Completeness bonus
            if d.is_complete:
                score += 50.0
            elif d.has_engagement_metrics or d.has_sentiment_fields:
                score += 20.0
            # Download popularity (log scale)
            score += math.log10(d.download_count + 1) * 10.0
            # Freshness bonus (more recent = higher score, max 20 points)
            if d.freshness_days >= 0:
                # Cap at 730 days (2 years); anything older gets 0 freshness bonus
                capped_days = min(d.freshness_days, 730)
                score += 20.0 * (1.0 - capped_days / 730.0)
            # Record count bonus
            if d.record_count > 0:
                score += 10.0
            return score

        filtered.sort(key=_score, reverse=True)
        filtered = filtered[:top_k]

    return filtered
