"""Unit tests for the report generator module."""

import os

import pytest

from src.models import (
    APIAssessment,
    DatasetMetadata,
    QualityReport,
    SurgeConfig,
    SurgeResult,
)
from src.report_generator import generate_report


@pytest.fixture
def sample_datasets():
    return [
        DatasetMetadata(
            name="stock-tweets",
            source_platform="kaggle",
            record_count=50000,
            download_count=0,
            date_range=("2020-01-01", "2023-12-31"),
            columns=["text", "likes", "sentiment"],
            freshness_days=30,
            has_engagement_metrics=True,
            has_sentiment_fields=True,
            is_complete=True,
        ),
        DatasetMetadata(
            name="reddit-wsb",
            source_platform="huggingface",
            record_count=20000,
            download_count=0,
            date_range=("2021-01-01", "2023-06-30"),
            columns=["body", "upvotes"],
            freshness_days=180,
            has_engagement_metrics=True,
            has_sentiment_fields=False,
            is_complete=False,
        ),
    ]


@pytest.fixture
def sample_apis():
    return [
        APIAssessment(
            platform="twitter",
            rate_limits={"requests_per_minute": 60},
            endpoints=["/tweets/search", "/tweets/counts"],
            cost_tiers=[{"name": "Basic", "price": 100}],
            available_fields=["text", "likes", "retweets", "timestamp"],
            historical_access=True,
            estimated_collection_time_hours=5.5,
            estimated_cost_usd=150.0,
            supports_surge_label=True,
            paid_fields=[{"field": "full_archive", "tier": "Academic"}],
        ),
    ]


@pytest.fixture
def sample_quality_reports():
    return [
        QualityReport(
            dataset_name="stock-tweets",
            schema={"text": "str", "likes": "int", "sentiment": "float"},
            record_count=50000,
            ticker_count=25,
            missing_values={"text": 0.5, "likes": 2.0, "sentiment": 35.0},
            high_risk_columns=["sentiment"],
            date_range=("2020-01-01", "2023-12-31"),
            temporal_gaps=[("2022-03-01", "2022-03-15")],
            posting_frequency={"daily": 45.2},
            engagement_stats={
                "likes": {
                    "mean": 10.5,
                    "median": 3.0,
                    "p90": 25.0,
                    "p95": 50.0,
                    "p99": 200.0,
                }
            },
            sentiment_stats={"mean_polarity": 0.15, "std_polarity": 0.45},
            bullish_bearish_ratio=1.8,
            recommendation="suitable",
            risks=["Potential survivorship bias"],
        ),
    ]


@pytest.fixture
def sample_surge_results():
    return [
        SurgeResult(
            config=SurgeConfig(
                engagement_percentile=0.95,
                sentiment_std_devs=1.0,
                time_window_hours=24,
            ),
            surge_count=1200,
            total_posts=50000,
            surge_percentage=2.4,
            class_imbalance_ratio=40.7,
            is_viable=True,
        ),
        SurgeResult(
            config=SurgeConfig(
                engagement_percentile=0.99,
                sentiment_std_devs=1.5,
                time_window_hours=24,
            ),
            surge_count=150,
            total_posts=50000,
            surge_percentage=0.3,
            class_imbalance_ratio=332.3,
            is_viable=False,
        ),
    ]


@pytest.fixture
def sample_chart_paths():
    return [
        "output/charts/engagement_distributions.png",
        "output/charts/sentiment_histogram.png",
    ]


@pytest.fixture
def output_path(tmp_path):
    return str(tmp_path / "report.md")


class TestGenerateReport:
    """Tests for the generate_report function."""

    def test_returns_output_path(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """generate_report returns the output file path."""
        result = generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        assert result == output_path

    def test_creates_output_file(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """generate_report creates the report file on disk."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        assert os.path.exists(output_path)

    def test_report_contains_executive_summary(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains an executive summary section."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## Executive Summary" in content

    def test_report_contains_discovery_section(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains dataset discovery results."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## Dataset Discovery Results" in content

    def test_report_contains_api_feasibility(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains API feasibility findings."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## API Feasibility Findings" in content

    def test_report_contains_eda_statistics(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains EDA statistics section."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## EDA Statistics" in content

    def test_report_contains_surge_analysis(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains surge analysis results."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## Surge Analysis Results" in content

    def test_report_contains_recommendation(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Report contains final recommendation section."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "## Final Recommendation" in content

    def test_chart_references_use_markdown_image_syntax(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, output_path
    ):
        """Chart references use markdown image syntax ![alt](path)."""
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, output_path
        )
        content = _read_report(output_path)
        assert "![" in content
        assert "engagement_distributions.png" in content
        assert "sentiment_histogram.png" in content

    def test_chart_references_use_relative_paths(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, output_path
    ):
        """Chart paths in the report are relative to the report location."""
        # Use chart paths relative to the report's directory
        report_dir = os.path.dirname(output_path)
        charts_dir = os.path.join(report_dir, "charts")
        os.makedirs(charts_dir, exist_ok=True)

        chart_paths = [
            os.path.join(charts_dir, "test_chart.png"),
        ]
        # Create a dummy chart file
        with open(chart_paths[0], "w") as f:
            f.write("dummy")

        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, chart_paths, output_path
        )
        content = _read_report(output_path)
        # Should use relative path (charts/test_chart.png), not absolute
        assert "charts/test_chart.png" in content
        assert not any(
            line.startswith("![") and os.path.isabs(line.split("(")[1].rstrip(")"))
            for line in content.split("\n")
            if line.startswith("![") and "(" in line
        )

    def test_handles_empty_inputs(self, output_path):
        """generate_report handles all empty inputs gracefully."""
        generate_report([], [], [], [], [], output_path)
        content = _read_report(output_path)
        # All sections should still be present
        assert "## Executive Summary" in content
        assert "## Dataset Discovery Results" in content
        assert "## API Feasibility Findings" in content
        assert "## EDA Statistics" in content
        assert "## Surge Analysis Results" in content
        assert "## Final Recommendation" in content

    def test_creates_output_directory_if_missing(
        self, sample_datasets, sample_apis, sample_quality_reports,
        sample_surge_results, sample_chart_paths, tmp_path
    ):
        """generate_report creates the output directory if it doesn't exist."""
        nested_path = str(tmp_path / "nested" / "dir" / "report.md")
        generate_report(
            sample_datasets, sample_apis, sample_quality_reports,
            sample_surge_results, sample_chart_paths, nested_path
        )
        assert os.path.exists(nested_path)


def _read_report(path: str) -> str:
    """Helper to read report content."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
