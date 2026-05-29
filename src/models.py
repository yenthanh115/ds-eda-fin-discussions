"""Core data models for the EDA Financial Discussions pipeline."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DatasetMetadata:
    """Metadata for a discovered dataset."""

    name: str
    source_platform: str  # "kaggle" | "huggingface"
    record_count: int
    date_range: tuple[str, str]  # (start, end) ISO dates
    columns: list[str]
    freshness_days: int
    has_engagement_metrics: bool
    has_sentiment_fields: bool
    is_complete: bool  # True if has both engagement + sentiment


@dataclass
class APIAssessment:
    """Feasibility assessment for a data collection API."""

    platform: str  # "twitter" | "reddit"
    rate_limits: dict[str, Any]
    endpoints: list[str]
    cost_tiers: list[dict[str, Any]]
    available_fields: list[str]
    historical_access: bool
    estimated_collection_time_hours: float
    estimated_cost_usd: float
    supports_surge_label: bool
    paid_fields: list[dict[str, str]]  # fields behind paywall


@dataclass
class QualityReport:
    """EDA quality analysis results for a dataset."""

    dataset_name: str
    schema: dict[str, str]  # column -> dtype
    record_count: int
    ticker_count: int
    missing_values: dict[str, float]  # column -> % missing
    high_risk_columns: list[str]  # >30% missing
    date_range: tuple[str, str]
    temporal_gaps: list[tuple[str, str]]  # gaps > 7 days
    posting_frequency: dict[str, float]  # period -> posts/day
    engagement_stats: dict[str, dict[str, float]]  # metric -> {mean, median, p90, p95, p99}
    sentiment_stats: dict[str, float]  # polarity stats
    bullish_bearish_ratio: float
    sentiment_reliability: Optional[dict[str, float]] = None
    risks: list[str] = field(default_factory=list)
    eda_questions_answered: dict[str, bool] = field(default_factory=dict)
    failing_objectives: list[str] = field(default_factory=list)
    recommendation: str = ""  # "suitable" | "unsuitable"


@dataclass
class SurgeConfig:
    """Configuration for a surge definition."""

    engagement_percentile: float  # e.g., 0.95
    sentiment_std_devs: float  # e.g., 1.0
    time_window_hours: int  # e.g., 24


@dataclass
class SurgeResult:
    """Results from applying a surge definition."""

    config: SurgeConfig
    surge_count: int
    total_posts: int
    surge_percentage: float
    class_imbalance_ratio: float
    is_viable: bool  # True if positive class >= 2%
    timestamp_sufficient: bool = True


@dataclass
class PipelineError:
    """Represents an error encountered during pipeline execution."""

    stage: str
    severity: str  # "warning" | "error" | "fatal"
    message: str
    recoverable: bool


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

    datasets_discovered: list["DatasetMetadata"] = field(default_factory=list)
    api_assessments: list["APIAssessment"] = field(default_factory=list)
    quality_reports: list["QualityReport"] = field(default_factory=list)
    surge_results: list["SurgeResult"] = field(default_factory=list)
    chart_paths: list[str] = field(default_factory=list)
    report_path: str = ""
    errors: list[str] = field(default_factory=list)
