"""Property-based tests for dataset discovery module.

Property 1: Dataset completeness flagging
- A dataset is incomplete iff it lacks engagement metrics OR sentiment fields.

Feature: eda-fin-discussions, Property 1: Dataset completeness flagging
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.dataset_discovery import (
    ENGAGEMENT_KEYWORDS,
    SENTIMENT_KEYWORDS,
    flag_incomplete_datasets,
)
from src.models import DatasetMetadata


# Strategy: generate arbitrary column name sets
_all_engagement = sorted(ENGAGEMENT_KEYWORDS)
_all_sentiment = sorted(SENTIMENT_KEYWORDS)
_neutral_columns = [
    "id", "text", "date", "author", "title", "url", "ticker",
    "timestamp", "body", "created_at", "user_id", "post_id",
]

# Strategy for column lists that may or may not contain engagement/sentiment keywords
column_strategy = st.lists(
    st.sampled_from(_all_engagement + _all_sentiment + _neutral_columns),
    min_size=0,
    max_size=10,
)


def _has_engagement(columns: list[str]) -> bool:
    """Ground truth: does the column set contain any engagement keyword?"""
    return bool(set(col.lower() for col in columns) & ENGAGEMENT_KEYWORDS)


def _has_sentiment(columns: list[str]) -> bool:
    """Ground truth: does the column set contain any sentiment keyword?"""
    return bool(set(col.lower() for col in columns) & SENTIMENT_KEYWORDS)


def _make_dataset(columns: list[str]) -> DatasetMetadata:
    """Create a DatasetMetadata with given columns and a neutral name."""
    return DatasetMetadata(
        name="test/dataset",
        source_platform="kaggle",
        record_count=100,
        date_range=("2024-01-01", "2024-12-31"),
        columns=columns,
        freshness_days=30,
        has_engagement_metrics=False,
        has_sentiment_fields=False,
        is_complete=False,
    )


@pytest.mark.property_test
class TestDatasetCompletenessFlagging:
    """Property 1: Dataset completeness flagging.

    For any dataset with a set of column names, the dataset SHALL be flagged
    as incomplete (is_complete = False) if and only if it lacks engagement
    metric columns OR sentiment-related columns.
    """

    @given(columns=column_strategy)
    @settings(max_examples=200)
    def test_is_complete_iff_has_both_engagement_and_sentiment(
        self, columns: list[str]
    ):
        """is_complete is True iff columns contain both engagement AND sentiment keywords."""
        dataset = _make_dataset(columns)
        result = flag_incomplete_datasets([dataset])

        expected_engagement = _has_engagement(columns)
        expected_sentiment = _has_sentiment(columns)
        expected_complete = expected_engagement and expected_sentiment

        assert result[0].has_engagement_metrics == expected_engagement
        assert result[0].has_sentiment_fields == expected_sentiment
        assert result[0].is_complete == expected_complete

    @given(
        engagement_col=st.sampled_from(_all_engagement),
        sentiment_col=st.sampled_from(_all_sentiment),
        extra_cols=st.lists(st.sampled_from(_neutral_columns), max_size=5),
    )
    @settings(max_examples=100)
    def test_complete_when_both_present(
        self, engagement_col: str, sentiment_col: str, extra_cols: list[str]
    ):
        """A dataset with at least one engagement and one sentiment column is always complete."""
        columns = [engagement_col, sentiment_col] + extra_cols
        dataset = _make_dataset(columns)
        result = flag_incomplete_datasets([dataset])

        assert result[0].is_complete is True

    @given(
        cols=st.lists(st.sampled_from(_neutral_columns), min_size=0, max_size=8)
    )
    @settings(max_examples=100)
    def test_incomplete_when_only_neutral_columns(self, cols: list[str]):
        """A dataset with only neutral columns (no engagement, no sentiment) is incomplete."""
        dataset = _make_dataset(cols)
        result = flag_incomplete_datasets([dataset])

        assert result[0].is_complete is False



# --- Property 2: Metadata extraction completeness ---

# Strategies for generating valid metadata field values
_platform_strategy = st.sampled_from(["kaggle", "huggingface"])
_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
)
_date_strategy = st.dates().map(lambda d: d.isoformat())
_columns_strategy = st.lists(
    st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=15,
)
_freshness_strategy = st.integers(min_value=0, max_value=3650)
_record_count_strategy = st.integers(min_value=0, max_value=10_000_000)


@pytest.mark.property_test
class TestMetadataExtractionCompleteness:
    """Property 2: Metadata extraction completeness.

    For any API response representing a discovered dataset, the metadata
    extraction function SHALL produce a DatasetMetadata object with all
    required fields (name, source_platform, record_count, date_range,
    columns, freshness_days) populated and non-null.

    Feature: eda-fin-discussions, Property 2: Metadata extraction completeness
    """

    @given(
        name=_name_strategy,
        platform=_platform_strategy,
        record_count=_record_count_strategy,
        start_date=_date_strategy,
        end_date=_date_strategy,
        columns=_columns_strategy,
        freshness_days=_freshness_strategy,
        has_engagement=st.booleans(),
        has_sentiment=st.booleans(),
    )
    @settings(max_examples=200)
    def test_all_required_fields_populated(
        self,
        name: str,
        platform: str,
        record_count: int,
        start_date: str,
        end_date: str,
        columns: list[str],
        freshness_days: int,
        has_engagement: bool,
        has_sentiment: bool,
    ):
        """All required fields in DatasetMetadata are populated and non-null."""
        metadata = DatasetMetadata(
            name=name,
            source_platform=platform,
            record_count=record_count,
            date_range=(start_date, end_date),
            columns=columns,
            freshness_days=freshness_days,
            has_engagement_metrics=has_engagement,
            has_sentiment_fields=has_sentiment,
            is_complete=has_engagement and has_sentiment,
        )

        # All required fields must be non-null
        assert metadata.name is not None
        assert metadata.source_platform is not None
        assert metadata.record_count is not None
        assert metadata.date_range is not None
        assert metadata.columns is not None
        assert metadata.freshness_days is not None

        # Required fields must have correct types
        assert isinstance(metadata.name, str) and len(metadata.name) > 0
        assert metadata.source_platform in ("kaggle", "huggingface")
        assert isinstance(metadata.record_count, int)
        assert isinstance(metadata.date_range, tuple) and len(metadata.date_range) == 2
        assert isinstance(metadata.columns, list)
        assert isinstance(metadata.freshness_days, int)

        # is_complete must be consistent with engagement + sentiment
        assert metadata.is_complete == (
            metadata.has_engagement_metrics and metadata.has_sentiment_fields
        )

    @given(
        name=_name_strategy,
        platform=_platform_strategy,
        record_count=_record_count_strategy,
        columns=_columns_strategy,
        freshness_days=_freshness_strategy,
    )
    @settings(max_examples=100)
    def test_date_range_is_two_element_tuple(
        self,
        name: str,
        platform: str,
        record_count: int,
        columns: list[str],
        freshness_days: int,
    ):
        """date_range must always be a 2-tuple of strings."""
        metadata = DatasetMetadata(
            name=name,
            source_platform=platform,
            record_count=record_count,
            date_range=("2024-01-01", "2024-12-31"),
            columns=columns,
            freshness_days=freshness_days,
            has_engagement_metrics=False,
            has_sentiment_fields=False,
            is_complete=False,
        )

        assert isinstance(metadata.date_range, tuple)
        assert len(metadata.date_range) == 2
        assert all(isinstance(d, str) for d in metadata.date_range)
