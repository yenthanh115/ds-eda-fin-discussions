"""Property-based tests for API feasibility assessment module.

Property 3: API collection cost and time estimation
Property 4: Surge label feasibility assessment

Feature: eda-fin-discussions
"""

import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.api_feasibility import (
    _estimate_collection_time_hours,
    _estimate_collection_cost,
    _check_surge_label_support,
)


@pytest.mark.property_test
class TestAPICollectionCostAndTime:
    """Property 3: API collection cost and time estimation.

    For any valid rate limit (requests/minute > 0) and cost per request (>= 0),
    the estimated collection time for N posts SHALL equal N divided by the
    effective request rate, and the estimated cost SHALL equal N multiplied
    by the cost per request.

    Feature: eda-fin-discussions, Property 3: API collection cost and time estimation
    """

    @given(
        target_posts=st.integers(min_value=1, max_value=1_000_000),
        requests_per_minute=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        posts_per_request=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=200)
    def test_estimated_time_equals_n_divided_by_effective_rate(
        self,
        target_posts: int,
        requests_per_minute: float,
        posts_per_request: int,
    ):
        """Estimated time = target_posts / (requests_per_minute * posts_per_request) / 60."""
        result = _estimate_collection_time_hours(
            target_posts, requests_per_minute, posts_per_request
        )

        effective_posts_per_minute = requests_per_minute * posts_per_request
        expected_minutes = target_posts / effective_posts_per_minute
        expected_hours = expected_minutes / 60.0

        assert math.isclose(result, expected_hours, rel_tol=1e-9)

    @given(
        target_posts=st.integers(min_value=1, max_value=1_000_000),
        cost_per_request=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        posts_per_request=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=200)
    def test_estimated_cost_equals_n_times_cost_per_request(
        self,
        target_posts: int,
        cost_per_request: float,
        posts_per_request: int,
    ):
        """Estimated cost = (target_posts / posts_per_request) * cost_per_request."""
        result = _estimate_collection_cost(
            target_posts, cost_per_request, posts_per_request
        )

        requests_needed = target_posts / posts_per_request
        expected_cost = requests_needed * cost_per_request

        assert math.isclose(result, expected_cost, rel_tol=1e-9)

    @given(
        target_posts=st.integers(min_value=1, max_value=1_000_000),
        posts_per_request=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_zero_cost_per_request_means_free(
        self,
        target_posts: int,
        posts_per_request: int,
    ):
        """If cost_per_request is 0, estimated cost is always 0."""
        result = _estimate_collection_cost(target_posts, 0.0, posts_per_request)
        assert result == 0.0

    @given(
        target_posts=st.integers(min_value=1, max_value=1_000_000),
        requests_per_minute=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        posts_per_request=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_time_is_always_positive(
        self,
        target_posts: int,
        requests_per_minute: float,
        posts_per_request: int,
    ):
        """Collection time is always positive for valid inputs."""
        result = _estimate_collection_time_hours(
            target_posts, requests_per_minute, posts_per_request
        )
        assert result > 0

    def test_invalid_rate_returns_infinity(self):
        """Zero or negative rate limit returns infinity."""
        assert _estimate_collection_time_hours(100, 0, 10) == float("inf")
        assert _estimate_collection_time_hours(100, -1, 10) == float("inf")
        assert _estimate_collection_cost(100, 1.0, 0) == float("inf")



# --- Property 4: Surge label feasibility assessment ---

# Define the field sets used by _check_surge_label_support
_engagement_fields = [
    "likes", "retweets", "comments", "upvotes", "shares",
    "favorites", "score", "like_count", "retweet_count",
    "reply_count", "quote_count", "impression_count",
    "ups", "downs", "num_comments",
]
_text_fields = [
    "text", "body", "content", "title", "selftext",
    "full_text", "tweet_text",
]
_timestamp_fields = [
    "created_at", "timestamp", "date", "created_utc",
    "created", "posted_at",
]
_neutral_fields = [
    "id", "author", "subreddit", "permalink", "url",
    "lang", "user_id", "flair", "is_self", "over_18",
]


@pytest.mark.property_test
class TestSurgeLabelFeasibility:
    """Property 4: Surge label feasibility assessment.

    For any set of available API fields, the surge label feasibility SHALL be
    True if and only if the field set contains at least one engagement metric,
    at least one sentiment-capable text field, and a timestamp field with
    sufficient resolution.

    Feature: eda-fin-discussions, Property 4: Surge label feasibility assessment
    """

    @given(
        engagement=st.lists(st.sampled_from(_engagement_fields), min_size=1, max_size=3),
        text=st.lists(st.sampled_from(_text_fields), min_size=1, max_size=2),
        timestamp=st.lists(st.sampled_from(_timestamp_fields), min_size=1, max_size=2),
        neutral=st.lists(st.sampled_from(_neutral_fields), min_size=0, max_size=4),
    )
    @settings(max_examples=200)
    def test_true_when_all_three_categories_present(
        self,
        engagement: list[str],
        text: list[str],
        timestamp: list[str],
        neutral: list[str],
    ):
        """supports_surge_label is True when engagement + text + timestamp all present."""
        fields = engagement + text + timestamp + neutral
        assert _check_surge_label_support(fields) is True

    @given(
        text=st.lists(st.sampled_from(_text_fields), min_size=1, max_size=2),
        timestamp=st.lists(st.sampled_from(_timestamp_fields), min_size=1, max_size=2),
        neutral=st.lists(st.sampled_from(_neutral_fields), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_false_when_missing_engagement(
        self,
        text: list[str],
        timestamp: list[str],
        neutral: list[str],
    ):
        """supports_surge_label is False when no engagement fields present."""
        fields = text + timestamp + neutral
        assert _check_surge_label_support(fields) is False

    @given(
        engagement=st.lists(st.sampled_from(_engagement_fields), min_size=1, max_size=3),
        timestamp=st.lists(st.sampled_from(_timestamp_fields), min_size=1, max_size=2),
        neutral=st.lists(st.sampled_from(_neutral_fields), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_false_when_missing_text(
        self,
        engagement: list[str],
        timestamp: list[str],
        neutral: list[str],
    ):
        """supports_surge_label is False when no text fields present."""
        fields = engagement + timestamp + neutral
        assert _check_surge_label_support(fields) is False

    @given(
        engagement=st.lists(st.sampled_from(_engagement_fields), min_size=1, max_size=3),
        text=st.lists(st.sampled_from(_text_fields), min_size=1, max_size=2),
        neutral=st.lists(st.sampled_from(_neutral_fields), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_false_when_missing_timestamp(
        self,
        engagement: list[str],
        text: list[str],
        neutral: list[str],
    ):
        """supports_surge_label is False when no timestamp fields present."""
        fields = engagement + text + neutral
        assert _check_surge_label_support(fields) is False

    @given(
        neutral=st.lists(st.sampled_from(_neutral_fields), min_size=0, max_size=8),
    )
    @settings(max_examples=100)
    def test_false_when_only_neutral_fields(self, neutral: list[str]):
        """supports_surge_label is False when only neutral fields present."""
        assert _check_surge_label_support(neutral) is False

    def test_empty_fields_returns_false(self):
        """Empty field list returns False."""
        assert _check_surge_label_support([]) is False
