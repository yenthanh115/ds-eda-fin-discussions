"""Core data models for the EDA Financial Discussions pipeline."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PipelineConfig:
    """Configuration for the full EDA pipeline."""

    output_dir: str = "output"
    chart_format: str = "png"
    kaggle_search_terms: list[str] = field(default_factory=lambda: [
        "stock twitter sentiment",
        "stock reddit discussion",
        "financial social media engagement",
    ])
    huggingface_search_terms: list[str] = field(default_factory=lambda: [
        "stock sentiment",
        "financial tweets",
        "reddit wallstreetbets",
    ])
    surge_percentiles: list[float] = field(default_factory=lambda: [0.90, 0.95, 0.99])
    surge_std_devs: list[float] = field(default_factory=lambda: [0.5, 1.0, 1.5])
    surge_window_hours: int = 24
    min_positive_class_pct: float = 0.02  # 2% threshold


@dataclass
class PipelineResult:
    """Aggregated results from the full pipeline."""

    datasets_discovered: list = field(default_factory=list)
    api_assessments: list = field(default_factory=list)
    quality_reports: list = field(default_factory=list)
    surge_results: list = field(default_factory=list)
    chart_paths: list[str] = field(default_factory=list)
    report_path: str = ""
    errors: list[str] = field(default_factory=list)
