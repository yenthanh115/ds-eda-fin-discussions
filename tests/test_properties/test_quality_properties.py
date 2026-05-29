"""Property-based tests for dataset quality analysis module.

Property 5: Missing value computation and high-risk flagging
Property 6: Temporal gap detection
Property 7: Engagement statistics correctness

Feature: eda-fin-discussions
"""

import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.extra.pandas import column, data_frames

from src.dataset_quality import compute_missing_values


# --- Property 5: Missing value computation and high-risk flagging ---


@pytest.mark.property_test
class TestMissingValueComputation:
    """Property 5: Missing value computation and high-risk flagging.

    For any DataFrame, the computed missing value percentage for each column
    SHALL equal the actual count of null/NaN values divided by total rows,
    and a column SHALL be flagged as high-risk if and only if its missing
    percentage exceeds 30%.

    Feature: eda-fin-discussions, Property 5: Missing value computation and high-risk flagging
    """

    @given(
        num_rows=st.integers(min_value=1, max_value=100),
        num_cols=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_missing_percentage_matches_actual_null_count(
        self, num_rows: int, num_cols: int, data
    ):
        """Computed missing % equals actual null count / total rows * 100."""
        # Generate a DataFrame with random null patterns
        col_names = [f"col_{i}" for i in range(num_cols)]
        df_data = {}
        for col_name in col_names:
            # Generate a mask of which values are null
            null_mask = data.draw(
                st.lists(
                    st.booleans(), min_size=num_rows, max_size=num_rows
                )
            )
            values = []
            for is_null in null_mask:
                if is_null:
                    values.append(None)
                else:
                    values.append(1.0)
            df_data[col_name] = values

        df = pd.DataFrame(df_data)
        result = compute_missing_values(df)

        for col_name in col_names:
            actual_nulls = df[col_name].isna().sum()
            expected_pct = (actual_nulls / num_rows) * 100.0
            computed_pct = result["missing_percentages"][col_name]
            assert math.isclose(computed_pct, expected_pct, rel_tol=1e-9)

    @given(
        num_rows=st.integers(min_value=1, max_value=100),
        num_cols=st.integers(min_value=1, max_value=5),
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_high_risk_flag_iff_above_30_percent(
        self, num_rows: int, num_cols: int, data
    ):
        """Column is high-risk iff missing percentage > 30%."""
        col_names = [f"col_{i}" for i in range(num_cols)]
        df_data = {}
        for col_name in col_names:
            null_mask = data.draw(
                st.lists(
                    st.booleans(), min_size=num_rows, max_size=num_rows
                )
            )
            values = []
            for is_null in null_mask:
                if is_null:
                    values.append(None)
                else:
                    values.append(1.0)
            df_data[col_name] = values

        df = pd.DataFrame(df_data)
        result = compute_missing_values(df)

        for col_name in col_names:
            pct = result["missing_percentages"][col_name]
            if pct > 30.0:
                assert col_name in result["high_risk_columns"], (
                    f"{col_name} has {pct}% missing but not in high_risk_columns"
                )
            else:
                assert col_name not in result["high_risk_columns"], (
                    f"{col_name} has {pct}% missing but IS in high_risk_columns"
                )

    def test_empty_dataframe_returns_no_high_risk(self):
        """Empty DataFrame (0 rows) returns 0% missing and no high-risk columns."""
        df = pd.DataFrame({"a": pd.Series([], dtype=float), "b": pd.Series([], dtype=float)})
        result = compute_missing_values(df)
        assert result["missing_percentages"]["a"] == 0.0
        assert result["missing_percentages"]["b"] == 0.0
        assert result["high_risk_columns"] == []

    def test_all_null_column_is_high_risk(self):
        """A column that is 100% null is always high-risk."""
        df = pd.DataFrame({"a": [None, None, None, None, None]})
        result = compute_missing_values(df)
        assert result["missing_percentages"]["a"] == 100.0
        assert "a" in result["high_risk_columns"]

    def test_exactly_30_percent_is_not_high_risk(self):
        """A column with exactly 30% missing is NOT high-risk (threshold is >30%)."""
        # 3 out of 10 = exactly 30%
        df = pd.DataFrame({"a": [None, None, None, 4, 5, 6, 7, 8, 9, 10]})
        result = compute_missing_values(df)
        assert math.isclose(result["missing_percentages"]["a"], 30.0)
        assert "a" not in result["high_risk_columns"]



# --- Property 6: Temporal gap detection ---

from src.dataset_quality import analyze_time_coverage


@pytest.mark.property_test
class TestTemporalGapDetection:
    """Property 6: Temporal gap detection.

    For any sorted sequence of timestamps, the time coverage analysis SHALL
    identify all consecutive pairs where the gap exceeds 7 days, and the
    reported date range SHALL span from the minimum to maximum timestamp.

    Feature: eda-fin-discussions, Property 6: Temporal gap detection
    """

    @given(
        dates=st.lists(
            st.dates(
                min_value=pd.Timestamp("2020-01-01").date(),
                max_value=pd.Timestamp("2025-12-31").date(),
            ),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=200)
    def test_date_range_spans_min_to_max(self, dates):
        """Reported date range spans from minimum to maximum timestamp."""
        df = pd.DataFrame({"date": [d.isoformat() for d in dates]})
        result = analyze_time_coverage(df, "date")

        sorted_dates = sorted(dates)
        expected_min = sorted_dates[0].isoformat()
        expected_max = sorted_dates[-1].isoformat()

        assert result["date_range"] == (expected_min, expected_max)

    @given(
        dates=st.lists(
            st.dates(
                min_value=pd.Timestamp("2020-01-01").date(),
                max_value=pd.Timestamp("2025-12-31").date(),
            ),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=200)
    def test_all_gaps_exceeding_7_days_are_identified(self, dates):
        """All consecutive pairs with gap > 7 days are identified."""
        import datetime

        df = pd.DataFrame({"date": [d.isoformat() for d in dates]})
        result = analyze_time_coverage(df, "date")

        sorted_dates = sorted(dates)
        expected_gaps = []
        for i in range(1, len(sorted_dates)):
            gap = (sorted_dates[i] - sorted_dates[i - 1]).days
            if gap > 7:
                expected_gaps.append(
                    (sorted_dates[i - 1].isoformat(), sorted_dates[i].isoformat())
                )

        assert result["temporal_gaps"] == expected_gaps

    @given(
        base_date=st.dates(
            min_value=pd.Timestamp("2020-01-01").date(),
            max_value=pd.Timestamp("2024-01-01").date(),
        ),
        num_days=st.integers(min_value=2, max_value=30),
    )
    @settings(max_examples=100)
    def test_no_gaps_when_consecutive_days(self, base_date, num_days):
        """No gaps detected when dates are consecutive days."""
        import datetime

        dates = [base_date + datetime.timedelta(days=i) for i in range(num_days)]
        df = pd.DataFrame({"date": [d.isoformat() for d in dates]})
        result = analyze_time_coverage(df, "date")

        assert result["temporal_gaps"] == []
        assert result["gap_count"] == 0

    def test_single_large_gap_detected(self):
        """A single gap of 30 days is detected."""
        df = pd.DataFrame({"date": ["2024-01-01", "2024-01-31"]})
        result = analyze_time_coverage(df, "date")

        assert result["temporal_gaps"] == [("2024-01-01", "2024-01-31")]
        assert result["gap_count"] == 1

    def test_exactly_7_days_is_not_a_gap(self):
        """A gap of exactly 7 days is NOT flagged (threshold is >7)."""
        df = pd.DataFrame({"date": ["2024-01-01", "2024-01-08"]})
        result = analyze_time_coverage(df, "date")

        assert result["temporal_gaps"] == []
        assert result["gap_count"] == 0
