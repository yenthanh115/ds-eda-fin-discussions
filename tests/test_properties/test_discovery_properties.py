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
