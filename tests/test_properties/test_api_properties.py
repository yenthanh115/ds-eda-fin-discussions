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
