"""Property-based tests for dataset suitability decision logic.

Property 11: Dataset suitability decision

Feature: eda-fin-discussions
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.report_generator import evaluate_dataset_suitability


# Strategy for generating EDA objective names
objective_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Pd", "Zs")),
    min_size=1,
    max_size=30,
)


@pytest.mark.property_test
class TestDatasetSuitabilityDecision:
    """Property 11: Dataset suitability decision.

    For any set of EDA objective results (pass/fail for each objective),
    the dataset SHALL be recommended as unsuitable if and only if three
    or more objectives have failed.

    Feature: eda-fin-discussions, Property 11: Dataset suitability decision
    **Validates: Requirements 3.11, 3.12**
    """

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=200)
    def test_unsuitable_iff_3_or_more_failures(self, data, num_objectives: int):
        """Dataset is unsuitable if and only if 3+ objectives fail."""
        # Generate unique objective names
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        # Generate pass/fail for each objective
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        failure_count = sum(1 for passed in results.values() if not passed)

        if failure_count >= 3:
            assert result["recommendation"] == "unsuitable", (
                f"Expected 'unsuitable' with {failure_count} failures, "
                f"got '{result['recommendation']}'"
            )
        else:
            assert result["recommendation"] == "suitable", (
                f"Expected 'suitable' with {failure_count} failures, "
                f"got '{result['recommendation']}'"
            )

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=200)
    def test_failure_count_matches_actual_failures(self, data, num_objectives: int):
        """Reported failure_count matches actual number of failed objectives."""
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        expected_failures = sum(1 for passed in results.values() if not passed)
        assert result["failure_count"] == expected_failures

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=200)
    def test_failing_objectives_list_correct(self, data, num_objectives: int):
        """failing_objectives contains exactly the objectives that failed."""
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        expected_failing = [name for name, passed in results.items() if not passed]
        assert sorted(result["failing_objectives"]) == sorted(expected_failing)

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=200)
    def test_passing_objectives_list_correct(self, data, num_objectives: int):
        """passing_objectives contains exactly the objectives that passed."""
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        expected_passing = [name for name, passed in results.items() if passed]
        assert sorted(result["passing_objectives"]) == sorted(expected_passing)

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=200)
    def test_total_objectives_equals_input_count(self, data, num_objectives: int):
        """total_objectives equals the number of objectives provided."""
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        assert result["total_objectives"] == num_objectives

    @given(
        data=st.data(),
        num_objectives=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_passing_plus_failing_equals_total(self, data, num_objectives: int):
        """passing + failing objectives partition the full set."""
        objectives = [f"objective_{i}" for i in range(num_objectives)]
        results = {
            name: data.draw(st.booleans())
            for name in objectives
        }

        result = evaluate_dataset_suitability(results)

        all_reported = sorted(result["failing_objectives"] + result["passing_objectives"])
        assert all_reported == sorted(objectives)

    def test_exactly_2_failures_is_suitable(self):
        """Boundary: exactly 2 failures results in 'suitable'."""
        results = {
            "obj_a": False,
            "obj_b": False,
            "obj_c": True,
            "obj_d": True,
            "obj_e": True,
        }
        result = evaluate_dataset_suitability(results)
        assert result["recommendation"] == "suitable"
        assert result["failure_count"] == 2

    def test_exactly_3_failures_is_unsuitable(self):
        """Boundary: exactly 3 failures results in 'unsuitable'."""
        results = {
            "obj_a": False,
            "obj_b": False,
            "obj_c": False,
            "obj_d": True,
            "obj_e": True,
        }
        result = evaluate_dataset_suitability(results)
        assert result["recommendation"] == "unsuitable"
        assert result["failure_count"] == 3

    def test_all_pass_is_suitable(self):
        """All objectives passing results in 'suitable'."""
        results = {
            "obj_a": True,
            "obj_b": True,
            "obj_c": True,
        }
        result = evaluate_dataset_suitability(results)
        assert result["recommendation"] == "suitable"
        assert result["failure_count"] == 0

    def test_all_fail_is_unsuitable(self):
        """All objectives failing results in 'unsuitable'."""
        results = {
            "obj_a": False,
            "obj_b": False,
            "obj_c": False,
            "obj_d": False,
        }
        result = evaluate_dataset_suitability(results)
        assert result["recommendation"] == "unsuitable"
        assert result["failure_count"] == 4
