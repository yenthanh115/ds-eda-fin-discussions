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
