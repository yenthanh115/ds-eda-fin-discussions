"""Property-based tests for report generator module.

Property 12: Report section completeness
- For any set of pipeline results, the generated markdown report SHALL contain
  all required sections and SHALL include relative path references to every
  chart file provided.

Feature: eda-fin-discussions, Property 12: Report section completeness

**Validates: Requirements 6.1, 6.2**
"""

import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import (
    APIAssessment,
    DatasetMetadata,
    QualityReport,
    SurgeConfig,
    SurgeResult,
)
from src.report_generator import generate_report


# --- Strategies for generating pipeline results ---

# Strategy for DatasetMetadata
_platform_strategy = st.sampled_from(["kaggle", "huggingface"])

_dataset_metadata_strategy = st.builds(
    DatasetMetadata,
    name=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-/"),
        min_size=1,
        max_size=30,
    ),
    source_platform=_platform_strategy,
    record_count=st.integers(min_value=100, max_value=1_000_000),
    date_range=st.tuples(
        st.just("2023-01-01"),
        st.just("2024-01-01"),
    ),
    columns=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=15),
        min_size=1,
        max_size=8,
    ),
    freshness_days=st.integers(min_value=1, max_value=365),
    has_engagement_metrics=st.booleans(),
    has_sentiment_fields=st.booleans(),
    is_complete=st.booleans(),
)

# Strategy for APIAssessment
_api_assessment_strategy = st.builds(
    APIAssessment,
    platform=st.sampled_from(["twitter", "reddit"]),
    rate_limits=st.just({"requests_per_minute": 60}),
    endpoints=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3),
    cost_tiers=st.just([{"name": "free", "limit": "500/month"}]),
    available_fields=st.lists(
        st.sampled_from(["text", "timestamp", "likes", "retweets", "sentiment", "author"]),
        min_size=1,
        max_size=6,
    ),
    historical_access=st.booleans(),
    estimated_collection_time_hours=st.floats(min_value=0.1, max_value=100.0),
    estimated_cost_usd=st.floats(min_value=0.0, max_value=500.0),
    supports_surge_label=st.booleans(),
    paid_fields=st.just([]),
)

# Strategy for QualityReport
_quality_report_strategy = st.builds(
    QualityReport,
    dataset_name=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=20,
    ),
    schema=st.just({"col1": "int64", "col2": "object"}),
    record_count=st.integers(min_value=100, max_value=500_000),
    ticker_count=st.integers(min_value=1, max_value=100),
    missing_values=st.just({"col1": 5.0, "col2": 12.0}),
    high_risk_columns=st.just([]),
    date_range=st.tuples(st.just("2023-01-01"), st.just("2024-01-01")),
    temporal_gaps=st.just([]),
    posting_frequency=st.just({"daily": 50.0}),
    engagement_stats=st.just({"likes": {"mean": 10.0, "median": 5.0, "p90": 30.0, "p95": 50.0, "p99": 100.0}}),
    sentiment_stats=st.just({"mean_polarity": 0.1}),
    bullish_bearish_ratio=st.floats(min_value=0.1, max_value=10.0),
    sentiment_reliability=st.just(None),
    risks=st.lists(st.text(min_size=1, max_size=30), max_size=3),
    eda_questions_answered=st.just({}),
    failing_objectives=st.just([]),
    recommendation=st.sampled_from(["suitable", "unsuitable"]),
)

# Strategy for SurgeResult
_surge_result_strategy = st.builds(
    SurgeResult,
    config=st.builds(
        SurgeConfig,
        engagement_percentile=st.sampled_from([0.90, 0.95, 0.99]),
        sentiment_std_devs=st.sampled_from([0.5, 1.0, 1.5]),
        time_window_hours=st.just(24),
    ),
    surge_count=st.integers(min_value=0, max_value=1000),
    total_posts=st.integers(min_value=100, max_value=10000),
    surge_percentage=st.floats(min_value=0.0, max_value=100.0),
    class_imbalance_ratio=st.floats(min_value=1.0, max_value=100.0),
    is_viable=st.booleans(),
    timestamp_sufficient=st.booleans(),
)

# Strategy for chart paths - generate valid-looking PNG file paths
_chart_path_strategy = st.lists(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=20,
    ).map(lambda name: f"output/charts/{name}.png"),
    min_size=0,
    max_size=5,
    unique=True,
)


# Required sections that must appear in every report
REQUIRED_SECTIONS = [
    "## Executive Summary",
    "## Dataset Discovery Results",
    "## API Feasibility Findings",
    "## EDA Statistics",
    "## Surge Analysis Results",
    "## Final Recommendation",
]


@pytest.mark.property_test
class TestReportSectionCompleteness:
    """Property 12: Report section completeness.

    For any set of pipeline results (discovery, API assessment, quality, surge,
    charts), the generated markdown report SHALL contain all required sections
    (executive summary, dataset discovery, API feasibility, EDA statistics,
    surge analysis, recommendation) and SHALL include relative path references
    to every chart file provided.

    Feature: eda-fin-discussions, Property 12: Report section completeness
    """

    @given(
        discovery_results=st.lists(_dataset_metadata_strategy, min_size=0, max_size=3),
        api_assessments=st.lists(_api_assessment_strategy, min_size=0, max_size=2),
        quality_reports=st.lists(_quality_report_strategy, min_size=0, max_size=2),
        surge_results=st.lists(_surge_result_strategy, min_size=0, max_size=3),
        chart_paths=_chart_path_strategy,
    )
    @settings(max_examples=100)
    def test_report_contains_all_required_sections(
        self,
        discovery_results: list[DatasetMetadata],
        api_assessments: list[APIAssessment],
        quality_reports: list[QualityReport],
        surge_results: list[SurgeResult],
        chart_paths: list[str],
    ):
        """The generated report SHALL contain all required sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.md")

            # Create chart files so relative path computation works
            for chart_path in chart_paths:
                abs_chart = os.path.join(tmpdir, chart_path)
                os.makedirs(os.path.dirname(abs_chart), exist_ok=True)
                with open(abs_chart, "w") as f:
                    f.write("fake chart")

            # Use chart paths relative to tmpdir
            chart_paths_abs = [os.path.join(tmpdir, cp) for cp in chart_paths]

            result_path = generate_report(
                discovery_results=discovery_results,
                api_assessments=api_assessments,
                quality_reports=quality_reports,
                surge_results=surge_results,
                chart_paths=chart_paths_abs,
                output_path=output_path,
            )

            assert result_path == output_path
            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                report_content = f.read()

            # Verify all required sections are present
            for section in REQUIRED_SECTIONS:
                assert section in report_content, (
                    f"Required section '{section}' not found in report"
                )

    @given(
        discovery_results=st.lists(_dataset_metadata_strategy, min_size=0, max_size=2),
        api_assessments=st.lists(_api_assessment_strategy, min_size=0, max_size=2),
        quality_reports=st.lists(_quality_report_strategy, min_size=0, max_size=2),
        surge_results=st.lists(_surge_result_strategy, min_size=0, max_size=2),
        chart_paths=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz_",
                min_size=1,
                max_size=20,
            ).map(lambda name: f"output/charts/{name}.png"),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_report_references_every_chart_file(
        self,
        discovery_results: list[DatasetMetadata],
        api_assessments: list[APIAssessment],
        quality_reports: list[QualityReport],
        surge_results: list[SurgeResult],
        chart_paths: list[str],
    ):
        """The report SHALL include relative path references to every chart file provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.md")

            # Create chart files so relative path computation works
            chart_paths_abs = []
            for chart_path in chart_paths:
                abs_chart = os.path.join(tmpdir, chart_path)
                os.makedirs(os.path.dirname(abs_chart), exist_ok=True)
                with open(abs_chart, "w") as f:
                    f.write("fake chart")
                chart_paths_abs.append(abs_chart)

            generate_report(
                discovery_results=discovery_results,
                api_assessments=api_assessments,
                quality_reports=quality_reports,
                surge_results=surge_results,
                chart_paths=chart_paths_abs,
                output_path=output_path,
            )

            with open(output_path, "r", encoding="utf-8") as f:
                report_content = f.read()

            # Every chart file should be referenced in the report
            # The report uses os.path.basename for the filename in the reference
            for chart_path in chart_paths_abs:
                # The chart filename should appear in the report content
                chart_basename = os.path.basename(chart_path)
                assert chart_basename in report_content, (
                    f"Chart file '{chart_basename}' (from path '{chart_path}') "
                    f"not referenced in report"
                )

    @given(
        chart_paths=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz_",
                min_size=1,
                max_size=20,
            ).map(lambda name: f"output/charts/{name}.png"),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_chart_references_use_relative_paths(
        self,
        chart_paths: list[str],
    ):
        """Chart references in the report SHALL use relative paths (not absolute)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.md")

            # Create chart files
            chart_paths_abs = []
            for chart_path in chart_paths:
                abs_chart = os.path.join(tmpdir, chart_path)
                os.makedirs(os.path.dirname(abs_chart), exist_ok=True)
                with open(abs_chart, "w") as f:
                    f.write("fake chart")
                chart_paths_abs.append(abs_chart)

            generate_report(
                discovery_results=[],
                api_assessments=[],
                quality_reports=[],
                surge_results=[],
                chart_paths=chart_paths_abs,
                output_path=output_path,
            )

            with open(output_path, "r", encoding="utf-8") as f:
                report_content = f.read()

            # Chart references should use relative paths (contain the chart
            # filename but NOT the full absolute tmpdir path)
            for chart_path_abs in chart_paths_abs:
                chart_basename = os.path.basename(chart_path_abs)
                # The absolute path prefix should NOT appear in the report
                # (the report should use relative paths)
                assert chart_basename in report_content, (
                    f"Chart '{chart_basename}' not found in report"
                )
                # Verify the reference uses a relative path format
                # by checking that the markdown image syntax uses a relative path
                # (relative paths don't start with a drive letter or /)
                lines_with_chart = [
                    line for line in report_content.split("\n")
                    if chart_basename in line and "![" in line
                ]
                for line in lines_with_chart:
                    # Extract the path from markdown image syntax ![alt](path)
                    start = line.index("](") + 2
                    end = line.index(")", start)
                    ref_path = line[start:end]
                    # Relative paths should not start with a drive letter (Windows)
                    # or be an absolute Unix path
                    assert not ref_path.startswith("/") or ref_path.startswith("../"), (
                        f"Chart reference '{ref_path}' appears to be absolute"
                    )
                    # On Windows, absolute paths start with drive letter like C:
                    assert ":" not in ref_path[:2], (
                        f"Chart reference '{ref_path}' appears to be an absolute Windows path"
                    )
