"""Unit tests for the visualization module."""

import os
import tempfile

import pandas as pd
import pytest

from src.models import DatasetMetadata
from src.visualization import (
    generate_dataset_comparison,
    generate_engagement_distributions,
    generate_sentiment_distributions,
    generate_surge_frequency,
)


@pytest.fixture
def tmp_output_dir():
    """Create a temporary directory for chart output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestGenerateEngagementDistributions:
    """Tests for generate_engagement_distributions."""

    def test_generates_png_for_each_metric(self, tmp_output_dir):
        stats = {
            "likes": {"mean": 10.0, "median": 5.0, "p90": 20.0, "p95": 30.0, "p99": 50.0},
            "retweets": {"mean": 3.0, "median": 1.0, "p90": 8.0, "p95": 12.0, "p99": 25.0},
        }
        paths = generate_engagement_distributions(stats, tmp_output_dir)

        assert len(paths) == 2
        for path in paths:
            assert path.endswith(".png")
            assert os.path.isfile(path)

    def test_returns_empty_list_for_empty_stats(self, tmp_output_dir):
        paths = generate_engagement_distributions({}, tmp_output_dir)
        assert paths == []

    def test_creates_output_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as base:
            output_dir = os.path.join(base, "nested", "charts")
            stats = {"likes": {"mean": 5.0, "median": 3.0, "p90": 10.0, "p95": 15.0, "p99": 20.0}}
            paths = generate_engagement_distributions(stats, output_dir)
            assert len(paths) == 1
            assert os.path.isdir(output_dir)

    def test_logs_file_path_to_stdout(self, tmp_output_dir, capsys):
        stats = {"comments": {"mean": 2.0, "median": 1.0, "p90": 5.0, "p95": 7.0, "p99": 10.0}}
        generate_engagement_distributions(stats, tmp_output_dir)
        captured = capsys.readouterr()
        assert "Chart saved:" in captured.out
        assert "engagement_distribution_comments.png" in captured.out


class TestGenerateSentimentDistributions:
    """Tests for generate_sentiment_distributions."""

    def test_generates_charts_with_valid_stats(self, tmp_output_dir):
        stats = {
            "polarity_scores": {"mean": 0.1, "median": 0.05, "std": 0.3},
            "bullish_count": 50,
            "bearish_count": 30,
            "neutral_count": 20,
            "bullish_bearish_ratio": 1.67,
            "total_analyzed": 100,
        }
        paths = generate_sentiment_distributions(stats, tmp_output_dir)

        assert len(paths) == 2
        for path in paths:
            assert path.endswith(".png")
            assert os.path.isfile(path)

    def test_returns_empty_for_no_data(self, tmp_output_dir):
        stats = {"total_analyzed": 0}
        paths = generate_sentiment_distributions(stats, tmp_output_dir)
        assert paths == []

    def test_returns_empty_for_empty_dict(self, tmp_output_dir):
        paths = generate_sentiment_distributions({}, tmp_output_dir)
        assert paths == []

    def test_logs_file_paths_to_stdout(self, tmp_output_dir, capsys):
        stats = {
            "polarity_scores": {"mean": 0.0, "median": 0.0, "std": 0.1},
            "bullish_count": 10,
            "bearish_count": 10,
            "neutral_count": 10,
            "bullish_bearish_ratio": 1.0,
            "total_analyzed": 30,
        }
        generate_sentiment_distributions(stats, tmp_output_dir)
        captured = capsys.readouterr()
        assert "Chart saved:" in captured.out


class TestGenerateSurgeFrequency:
    """Tests for generate_surge_frequency."""

    def test_generates_chart_with_valid_data(self, tmp_output_dir):
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        surge_flags = [True if i % 10 == 0 else False for i in range(100)]
        df = pd.DataFrame({"timestamp": dates, "surge": surge_flags})

        path = generate_surge_frequency(df, tmp_output_dir)

        assert path.endswith(".png")
        assert os.path.isfile(path)

    def test_handles_empty_dataframe(self, tmp_output_dir):
        df = pd.DataFrame()
        path = generate_surge_frequency(df, tmp_output_dir)
        assert path.endswith(".png")
        assert os.path.isfile(path)

    def test_logs_file_path_to_stdout(self, tmp_output_dir, capsys):
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        surge_flags = [True if i % 5 == 0 else False for i in range(30)]
        df = pd.DataFrame({"timestamp": dates, "surge": surge_flags})

        generate_surge_frequency(df, tmp_output_dir)
        captured = capsys.readouterr()
        assert "Chart saved:" in captured.out
        assert "surge_frequency.png" in captured.out


class TestGenerateDatasetComparison:
    """Tests for generate_dataset_comparison."""

    def test_generates_chart_with_multiple_datasets(self, tmp_output_dir):
        datasets = [
            DatasetMetadata(
                name="dataset_a",
                source_platform="kaggle",
                record_count=10000,
                date_range=("2022-01-01", "2023-01-01"),
                columns=["text", "likes", "sentiment"],
                freshness_days=30,
                has_engagement_metrics=True,
                has_sentiment_fields=True,
                is_complete=True,
            ),
            DatasetMetadata(
                name="dataset_b",
                source_platform="huggingface",
                record_count=5000,
                date_range=("2022-06-01", "2023-06-01"),
                columns=["text", "upvotes"],
                freshness_days=90,
                has_engagement_metrics=True,
                has_sentiment_fields=False,
                is_complete=False,
            ),
        ]

        path = generate_dataset_comparison(datasets, tmp_output_dir)

        assert path.endswith(".png")
        assert os.path.isfile(path)

    def test_handles_empty_dataset_list(self, tmp_output_dir):
        path = generate_dataset_comparison([], tmp_output_dir)
        assert path.endswith(".png")
        assert os.path.isfile(path)

    def test_logs_file_path_to_stdout(self, tmp_output_dir, capsys):
        datasets = [
            DatasetMetadata(
                name="test_ds",
                source_platform="kaggle",
                record_count=1000,
                date_range=("2023-01-01", "2023-12-31"),
                columns=["col1", "col2"],
                freshness_days=10,
                has_engagement_metrics=True,
                has_sentiment_fields=True,
                is_complete=True,
            ),
        ]
        generate_dataset_comparison(datasets, tmp_output_dir)
        captured = capsys.readouterr()
        assert "Chart saved:" in captured.out
        assert "dataset_comparison.png" in captured.out
