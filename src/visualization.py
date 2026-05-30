"""Visualization engine for the EDA Financial Discussions pipeline.

This module provides functions to generate charts for engagement distributions,
sentiment distributions, surge event frequency, and dataset comparisons.
All charts are saved as PNG files and include descriptive titles, axis labels,
and legends.
"""

import logging
import os

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for file output

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.models import DatasetMetadata

logger = logging.getLogger(__name__)


def generate_engagement_distributions(stats: dict, output_dir: str) -> list[str]:
    """Generate engagement metric distribution charts.

    Creates a bar chart for each engagement metric showing its summary
    statistics (mean, median, p90, p95, p99).

    Args:
        stats: Dictionary mapping metric name -> {mean, median, p90, p95, p99}.
            This is the output format from dataset_quality.compute_engagement_distributions.
        output_dir: Directory path where PNG files will be saved.

    Returns:
        List of file paths for the generated PNG charts.
    """
    os.makedirs(output_dir, exist_ok=True)
    file_paths: list[str] = []

    if not stats:
        logger.warning("No engagement statistics provided. Skipping chart generation.")
        return file_paths

    for metric_name, metric_stats in stats.items():
        fig, ax = plt.subplots(figsize=(8, 5))

        stat_names = ["mean", "median", "p90", "p95", "p99"]
        stat_values = [metric_stats.get(s, 0.0) for s in stat_names]
        stat_labels = ["Mean", "Median", "P90", "P95", "P99"]

        bars = ax.bar(stat_labels, stat_values, color=sns.color_palette("viridis", len(stat_labels)))

        ax.set_title(f"Engagement Distribution: {metric_name}", fontsize=14)
        ax.set_xlabel("Statistic", fontsize=12)
        ax.set_ylabel("Value", fontsize=12)
        ax.legend(bars, stat_labels, title="Statistics", loc="upper left")

        plt.tight_layout()

        filename = f"engagement_distribution_{metric_name}.png"
        filepath = os.path.join(output_dir, filename)
        fig.savefig(filepath, dpi=100, bbox_inches="tight")
        plt.close(fig)

        print(f"Chart saved: {filepath}")
        file_paths.append(filepath)

    return file_paths


def generate_sentiment_distributions(stats: dict, output_dir: str) -> list[str]:
    """Generate sentiment polarity distribution charts.

    Creates a bar chart showing sentiment class counts (bullish, bearish, neutral)
    and a summary statistics chart for polarity scores.

    Args:
        stats: Dictionary with sentiment analysis results containing:
            - polarity_scores: dict with mean, median, std
            - bullish_count: int
            - bearish_count: int
            - neutral_count: int
            - bullish_bearish_ratio: float
            - total_analyzed: int
            This is the output format from dataset_quality.analyze_sentiment.
        output_dir: Directory path where PNG files will be saved.

    Returns:
        List of file paths for the generated PNG charts.
    """
    os.makedirs(output_dir, exist_ok=True)
    file_paths: list[str] = []

    if not stats or stats.get("total_analyzed", 0) == 0:
        logger.warning("No sentiment statistics provided. Skipping chart generation.")
        return file_paths

    # Chart 1: Sentiment class distribution (bullish/bearish/neutral)
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ["Bullish", "Bearish", "Neutral"]
    counts = [
        stats.get("bullish_count", 0),
        stats.get("bearish_count", 0),
        stats.get("neutral_count", 0),
    ]
    colors = ["#2ecc71", "#e74c3c", "#95a5a6"]

    bars = ax.bar(categories, counts, color=colors)
    ax.set_title("Sentiment Class Distribution", fontsize=14)
    ax.set_xlabel("Sentiment Class", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.legend(bars, categories, title="Sentiment", loc="upper right")

    plt.tight_layout()

    filepath = os.path.join(output_dir, "sentiment_class_distribution.png")
    fig.savefig(filepath, dpi=100, bbox_inches="tight")
    plt.close(fig)

    print(f"Chart saved: {filepath}")
    file_paths.append(filepath)

    # Chart 2: Polarity score statistics
    polarity_scores = stats.get("polarity_scores", {})
    if polarity_scores:
        fig, ax = plt.subplots(figsize=(8, 5))

        score_names = ["Mean", "Median", "Std Dev"]
        score_values = [
            polarity_scores.get("mean", 0.0),
            polarity_scores.get("median", 0.0),
            polarity_scores.get("std", 0.0),
        ]
        colors_polarity = sns.color_palette("coolwarm", len(score_names))

        bars = ax.bar(score_names, score_values, color=colors_polarity)
        ax.set_title("Sentiment Polarity Score Statistics", fontsize=14)
        ax.set_xlabel("Statistic", fontsize=12)
        ax.set_ylabel("Score", fontsize=12)
        ax.legend(bars, score_names, title="Polarity Stats", loc="upper right")
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.5)

        plt.tight_layout()

        filepath = os.path.join(output_dir, "sentiment_polarity_stats.png")
        fig.savefig(filepath, dpi=100, bbox_inches="tight")
        plt.close(fig)

        print(f"Chart saved: {filepath}")
        file_paths.append(filepath)

    return file_paths


def generate_surge_frequency(surge_data: pd.DataFrame, output_dir: str) -> str:
    """Generate surge event frequency over time chart.

    Creates a line chart showing the count of surge events aggregated by
    time period (daily or weekly depending on data span).

    Args:
        surge_data: DataFrame containing at minimum a 'timestamp' column
            (datetime) and a 'surge' column (boolean). The 'surge' column
            indicates whether each post is classified as a surge event.
        output_dir: Directory path where the PNG file will be saved.

    Returns:
        File path of the generated PNG chart.
    """
    os.makedirs(output_dir, exist_ok=True)

    if surge_data.empty:
        logger.warning("Empty surge data provided. Generating empty chart.")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set_title("Surge Event Frequency Over Time", fontsize=14)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Surge Count", fontsize=12)
        ax.text(0.5, 0.5, "No data available", transform=ax.transAxes,
                ha="center", va="center", fontsize=12, color="gray")
        filepath = os.path.join(output_dir, "surge_frequency.png")
        fig.savefig(filepath, dpi=100, bbox_inches="tight")
        plt.close(fig)
        print(f"Chart saved: {filepath}")
        return filepath

    # Ensure proper column types
    working_df = surge_data.copy()

    # Detect timestamp column name
    timestamp_col = None
    for col_name in ["timestamp", "date", "created_at"]:
        if col_name in working_df.columns:
            timestamp_col = col_name
            break

    if timestamp_col is None:
        # Use first datetime column
        datetime_cols = working_df.select_dtypes(include=["datetime64"]).columns
        if len(datetime_cols) > 0:
            timestamp_col = datetime_cols[0]
        else:
            logger.warning("No timestamp column found in surge data.")
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.set_title("Surge Event Frequency Over Time", fontsize=14)
            ax.set_xlabel("Date", fontsize=12)
            ax.set_ylabel("Surge Count", fontsize=12)
            ax.text(0.5, 0.5, "No timestamp column available",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=12, color="gray")
            filepath = os.path.join(output_dir, "surge_frequency.png")
            fig.savefig(filepath, dpi=100, bbox_inches="tight")
            plt.close(fig)
            print(f"Chart saved: {filepath}")
            return filepath

    working_df[timestamp_col] = pd.to_datetime(working_df[timestamp_col], errors="coerce")

    # Detect surge column name
    surge_col = None
    for col_name in ["surge", "is_surge", "surge_label"]:
        if col_name in working_df.columns:
            surge_col = col_name
            break

    if surge_col is None:
        logger.warning("No surge column found in surge data.")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.set_title("Surge Event Frequency Over Time", fontsize=14)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Surge Count", fontsize=12)
        ax.text(0.5, 0.5, "No surge column available",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=12, color="gray")
        filepath = os.path.join(output_dir, "surge_frequency.png")
        fig.savefig(filepath, dpi=100, bbox_inches="tight")
        plt.close(fig)
        print(f"Chart saved: {filepath}")
        return filepath

    # Filter to surge events only
    surge_events = working_df[working_df[surge_col] == True].copy()

    # Determine aggregation period based on data span
    date_range = working_df[timestamp_col].max() - working_df[timestamp_col].min()
    if date_range.days > 180:
        freq = "W"
        freq_label = "Week"
    else:
        freq = "D"
        freq_label = "Day"

    # Aggregate surge counts by period
    surge_events = surge_events.set_index(timestamp_col)
    surge_counts = surge_events.resample(freq)[surge_col].count()

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(surge_counts.index, surge_counts.values,
            color="#e74c3c", linewidth=1.5, marker="o", markersize=3,
            label="Surge Events")
    ax.fill_between(surge_counts.index, surge_counts.values,
                    alpha=0.2, color="#e74c3c")

    ax.set_title("Surge Event Frequency Over Time", fontsize=14)
    ax.set_xlabel(f"Date ({freq_label}ly aggregation)", fontsize=12)
    ax.set_ylabel("Surge Event Count", fontsize=12)
    ax.legend(loc="upper right")

    plt.xticks(rotation=45)
    plt.tight_layout()

    filepath = os.path.join(output_dir, "surge_frequency.png")
    fig.savefig(filepath, dpi=100, bbox_inches="tight")
    plt.close(fig)

    print(f"Chart saved: {filepath}")
    return filepath


def generate_dataset_comparison(datasets: list[DatasetMetadata], output_dir: str) -> str:
    """Generate comparison chart of dataset characteristics across candidates.

    Creates a grouped bar chart comparing key characteristics (record count,
    freshness, completeness) across all candidate datasets.

    Args:
        datasets: List of DatasetMetadata objects to compare.
        output_dir: Directory path where the PNG file will be saved.

    Returns:
        File path of the generated PNG chart.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not datasets:
        logger.warning("No datasets provided for comparison. Generating empty chart.")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_title("Dataset Characteristics Comparison", fontsize=14)
        ax.set_xlabel("Dataset", fontsize=12)
        ax.set_ylabel("Value", fontsize=12)
        ax.text(0.5, 0.5, "No datasets available", transform=ax.transAxes,
                ha="center", va="center", fontsize=12, color="gray")
        filepath = os.path.join(output_dir, "dataset_comparison.png")
        fig.savefig(filepath, dpi=100, bbox_inches="tight")
        plt.close(fig)
        print(f"Chart saved: {filepath}")
        return filepath

    # Extract comparison data
    names = [ds.name for ds in datasets]
    record_counts = [ds.record_count for ds in datasets]
    freshness_days = [ds.freshness_days for ds in datasets]
    completeness = [1 if ds.is_complete else 0 for ds in datasets]
    column_counts = [len(ds.columns) for ds in datasets]

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Subplot 1: Record counts
    ax1 = axes[0, 0]
    bars1 = ax1.bar(names, record_counts, color=sns.color_palette("viridis", len(names)))
    ax1.set_title("Record Count by Dataset", fontsize=12)
    ax1.set_xlabel("Dataset", fontsize=10)
    ax1.set_ylabel("Records", fontsize=10)
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend(bars1, names, title="Datasets", loc="upper right", fontsize=8)

    # Subplot 2: Freshness (days since last update)
    ax2 = axes[0, 1]
    bars2 = ax2.bar(names, freshness_days, color=sns.color_palette("magma", len(names)))
    ax2.set_title("Data Freshness (Days Since Update)", fontsize=12)
    ax2.set_xlabel("Dataset", fontsize=10)
    ax2.set_ylabel("Days", fontsize=10)
    ax2.tick_params(axis="x", rotation=45)
    ax2.legend(bars2, names, title="Datasets", loc="upper right", fontsize=8)

    # Subplot 3: Completeness (has engagement + sentiment)
    ax3 = axes[1, 0]
    colors_complete = ["#2ecc71" if c == 1 else "#e74c3c" for c in completeness]
    bars3 = ax3.bar(names, completeness, color=colors_complete)
    ax3.set_title("Dataset Completeness", fontsize=12)
    ax3.set_xlabel("Dataset", fontsize=10)
    ax3.set_ylabel("Complete (1=Yes, 0=No)", fontsize=10)
    ax3.set_ylim(-0.1, 1.5)
    ax3.tick_params(axis="x", rotation=45)
    # Custom legend for completeness
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2ecc71", label="Complete"),
        Patch(facecolor="#e74c3c", label="Incomplete"),
    ]
    ax3.legend(handles=legend_elements, title="Status", loc="upper right")

    # Subplot 4: Column counts
    ax4 = axes[1, 1]
    bars4 = ax4.bar(names, column_counts, color=sns.color_palette("crest", len(names)))
    ax4.set_title("Available Columns by Dataset", fontsize=12)
    ax4.set_xlabel("Dataset", fontsize=10)
    ax4.set_ylabel("Column Count", fontsize=10)
    ax4.tick_params(axis="x", rotation=45)
    ax4.legend(bars4, names, title="Datasets", loc="upper right", fontsize=8)

    fig.suptitle("Dataset Characteristics Comparison", fontsize=16, y=1.02)
    plt.tight_layout()

    filepath = os.path.join(output_dir, "dataset_comparison.png")
    fig.savefig(filepath, dpi=100, bbox_inches="tight")
    plt.close(fig)

    print(f"Chart saved: {filepath}")
    return filepath
