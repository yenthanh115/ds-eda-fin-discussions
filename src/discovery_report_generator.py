"""Discovery report generator for the EDA Financial Discussions pipeline.

This module produces the Phase 1 output artifacts:
- A structured JSON file (discovery_report.json) for machine consumption
- A human-readable markdown report (discovery_report.md)

These reports contain all discovered dataset metadata, API feasibility
assessments, filtering criteria, and actionable next-steps.
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from src.models import APIAssessment, DatasetMetadata, DiscoveryReportData

logger = logging.getLogger(__name__)


def generate_discovery_report_json(
    data: DiscoveryReportData,
    output_path: str,
) -> str:
    """Write discovery results to JSON file.

    The JSON format includes:
    - datasets: list of DatasetMetadata serialized as dicts
    - api_assessments: list of APIAssessment serialized as dicts
    - search_config: search terms and filter configuration used
    - execution_timestamp: when the discovery was run
    - summary: {total, complete, incomplete, filtered_out} counts

    Args:
        data: DiscoveryReportData containing all Phase 1 results.
        output_path: Path where the JSON file will be written.

    Returns:
        The file path of the generated JSON report.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    report_dict = _serialize_discovery_data(data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info("Discovery report JSON written to: %s", output_path)
    return output_path


def generate_discovery_report_md(
    data: DiscoveryReportData,
    output_path: str,
) -> str:
    """Write discovery results as human-readable markdown.

    The markdown report includes:
    - Executive summary with key metrics
    - Per-platform dataset tables (Kaggle, HuggingFace)
    - Completeness analysis (which datasets have engagement + sentiment)
    - API feasibility summary
    - Filtering summary (what was removed and why)
    - Actionable next-steps for the data scientist

    Args:
        data: DiscoveryReportData containing all Phase 1 results.
        output_path: Path where the markdown file will be written.

    Returns:
        The file path of the generated markdown report.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    sections = []

    # Title
    sections.append("# Dataset Discovery Report\n")
    sections.append(f"*Generated: {data.execution_timestamp}*\n")

    # Executive Summary
    sections.append(_generate_executive_summary(data))

    # Per-platform dataset tables
    sections.append(_generate_dataset_tables(data.datasets))

    # Completeness analysis
    sections.append(_generate_completeness_analysis(data.datasets))

    # API Feasibility
    if data.api_assessments:
        sections.append(_generate_api_section(data.api_assessments))

    # Filtering summary
    sections.append(_generate_filtering_summary(data))

    # Next steps
    sections.append(_generate_next_steps(data))

    report_content = "\n".join(sections)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info("Discovery report markdown written to: %s", output_path)
    return output_path


def load_discovery_report(json_path: str) -> DiscoveryReportData:
    """Load a previously generated discovery report from JSON.

    Deserializes JSON back into DiscoveryReportData with full
    DatasetMetadata and APIAssessment objects.

    Args:
        json_path: Path to the discovery_report.json file.

    Returns:
        DiscoveryReportData with all fields populated.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    datasets = [
        DatasetMetadata(
            name=d["name"],
            source_platform=d["source_platform"],
            record_count=d["record_count"],
            download_count=d["download_count"],
            date_range=tuple(d["date_range"]),
            columns=d["columns"],
            freshness_days=d["freshness_days"],
            has_engagement_metrics=d["has_engagement_metrics"],
            has_sentiment_fields=d["has_sentiment_fields"],
            is_complete=d["is_complete"],
        )
        for d in raw.get("datasets", [])
    ]

    api_assessments = [
        APIAssessment(
            platform=a["platform"],
            rate_limits=a["rate_limits"],
            endpoints=a["endpoints"],
            cost_tiers=a["cost_tiers"],
            available_fields=a["available_fields"],
            historical_access=a["historical_access"],
            estimated_collection_time_hours=a["estimated_collection_time_hours"],
            estimated_cost_usd=a["estimated_cost_usd"],
            supports_surge_label=a["supports_surge_label"],
            paid_fields=a["paid_fields"],
        )
        for a in raw.get("api_assessments", [])
    ]

    return DiscoveryReportData(
        datasets=datasets,
        api_assessments=api_assessments,
        search_config=raw.get("search_config", {}),
        execution_timestamp=raw.get("execution_timestamp", ""),
        summary=raw.get("summary", {}),
    )


# ─── Serialization Helpers ──────────────────────────────────────────────────


def _serialize_discovery_data(data: DiscoveryReportData) -> dict[str, Any]:
    """Serialize DiscoveryReportData to a JSON-compatible dict."""
    return {
        "datasets": [
            {
                "name": d.name,
                "source_platform": d.source_platform,
                "record_count": d.record_count,
                "download_count": d.download_count,
                "date_range": list(d.date_range),
                "columns": d.columns,
                "freshness_days": d.freshness_days,
                "has_engagement_metrics": d.has_engagement_metrics,
                "has_sentiment_fields": d.has_sentiment_fields,
                "is_complete": d.is_complete,
            }
            for d in data.datasets
        ],
        "api_assessments": [
            {
                "platform": a.platform,
                "rate_limits": a.rate_limits,
                "endpoints": a.endpoints,
                "cost_tiers": a.cost_tiers,
                "available_fields": a.available_fields,
                "historical_access": a.historical_access,
                "estimated_collection_time_hours": a.estimated_collection_time_hours,
                "estimated_cost_usd": a.estimated_cost_usd,
                "supports_surge_label": a.supports_surge_label,
                "paid_fields": a.paid_fields,
            }
            for a in data.api_assessments
        ],
        "search_config": data.search_config,
        "execution_timestamp": data.execution_timestamp,
        "summary": data.summary,
    }


# ─── Markdown Section Generators ────────────────────────────────────────────


def _generate_executive_summary(data: DiscoveryReportData) -> str:
    """Generate the executive summary section."""
    lines = []
    lines.append("## Executive Summary\n")

    summary = data.summary
    total = summary.get("total", len(data.datasets))
    complete = summary.get("complete", sum(1 for d in data.datasets if d.is_complete))
    incomplete = summary.get("incomplete", total - complete)

    lines.append(
        "This report catalogs publicly available datasets discovered from Kaggle "
        "and HuggingFace that are relevant to stock-related social media discussion "
        "analysis and engagement/sentiment surge prediction.\n"
    )
    lines.append("### Key Metrics\n")
    lines.append(f"- **Total datasets discovered:** {total}")
    lines.append(f"- **Complete (engagement + sentiment):** {complete}")
    lines.append(f"- **Incomplete:** {incomplete}")

    platforms = set(d.source_platform for d in data.datasets)
    lines.append(f"- **Platforms searched:** {', '.join(sorted(platforms)) if platforms else 'none'}")

    if data.api_assessments:
        lines.append(f"- **API platforms assessed:** {len(data.api_assessments)}")

    filtered_out = summary.get("filtered_out", 0)
    if filtered_out > 0:
        lines.append(f"- **Datasets filtered out:** {filtered_out}")

    lines.append("")
    return "\n".join(lines)


def _generate_dataset_tables(datasets: list[DatasetMetadata]) -> str:
    """Generate per-platform dataset tables."""
    lines = []
    lines.append("## Discovered Datasets\n")

    if not datasets:
        lines.append("No datasets were discovered during the scan.\n")
        return "\n".join(lines)

    kaggle = [d for d in datasets if d.source_platform == "kaggle"]
    hf = [d for d in datasets if d.source_platform == "huggingface"]

    if kaggle:
        lines.append("### Kaggle\n")
        lines.append(_format_dataset_table(kaggle))
        lines.append("")

    if hf:
        lines.append("### HuggingFace\n")
        lines.append(_format_dataset_table(hf))
        lines.append("")

    return "\n".join(lines)


def _format_dataset_table(datasets: list[DatasetMetadata]) -> str:
    """Format a list of datasets as a markdown table."""
    lines = []
    lines.append("| Name | Records | Downloads | Date Range | Freshness (days) | Engagement | Sentiment | Complete |")
    lines.append("|------|---------|-----------|------------|------------------|------------|-----------|----------|")
    for d in datasets:
        date_range = f"{d.date_range[0]} to {d.date_range[1]}"
        engagement = "✓" if d.has_engagement_metrics else "✗"
        sentiment = "✓" if d.has_sentiment_fields else "✗"
        complete = "✓" if d.is_complete else "✗"
        lines.append(
            f"| {d.name} | {d.record_count:,} | {d.download_count:,} "
            f"| {date_range} | {d.freshness_days} | {engagement} | {sentiment} | {complete} |"
        )
    return "\n".join(lines)


def _generate_completeness_analysis(datasets: list[DatasetMetadata]) -> str:
    """Generate completeness analysis section."""
    lines = []
    lines.append("## Completeness Analysis\n")

    if not datasets:
        lines.append("No datasets to analyze.\n")
        return "\n".join(lines)

    complete = [d for d in datasets if d.is_complete]
    missing_engagement = [d for d in datasets if not d.has_engagement_metrics]
    missing_sentiment = [d for d in datasets if not d.has_sentiment_fields]
    missing_both = [d for d in datasets if not d.has_engagement_metrics and not d.has_sentiment_fields]

    lines.append(
        "A dataset is considered **complete** for surge prediction if it contains "
        "both engagement metrics (likes, comments, upvotes, etc.) AND sentiment fields "
        "(sentiment scores, polarity, bullish/bearish labels).\n"
    )

    lines.append(f"- **Complete datasets:** {len(complete)}")
    lines.append(f"- **Missing engagement metrics only:** {len(missing_engagement) - len(missing_both)}")
    lines.append(f"- **Missing sentiment fields only:** {len(missing_sentiment) - len(missing_both)}")
    lines.append(f"- **Missing both:** {len(missing_both)}")
    lines.append("")

    if missing_engagement:
        lines.append("### Datasets Missing Engagement Metrics\n")
        for d in missing_engagement:
            lines.append(f"- **{d.name}** ({d.source_platform})")
        lines.append("")

    if missing_sentiment:
        lines.append("### Datasets Missing Sentiment Fields\n")
        for d in missing_sentiment:
            lines.append(f"- **{d.name}** ({d.source_platform})")
        lines.append("")

    return "\n".join(lines)


def _generate_api_section(api_assessments: list[APIAssessment]) -> str:
    """Generate API feasibility summary section."""
    lines = []
    lines.append("## API Feasibility Assessment\n")

    for assessment in api_assessments:
        lines.append(f"### {assessment.platform.title()} API\n")
        lines.append(f"- **Historical access:** {'Yes' if assessment.historical_access else 'No'}")
        lines.append(f"- **Supports surge label construction:** "
                     f"{'Yes' if assessment.supports_surge_label else 'No'}")
        lines.append(f"- **Estimated collection time:** {assessment.estimated_collection_time_hours:.1f} hours")
        lines.append(f"- **Estimated cost:** ${assessment.estimated_cost_usd:.2f}")
        lines.append(f"- **Endpoints available:** {len(assessment.endpoints)}")
        lines.append("")

        if assessment.rate_limits:
            lines.append("#### Rate Limits\n")
            for key, value in assessment.rate_limits.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        if assessment.cost_tiers:
            lines.append("#### Cost Tiers\n")
            lines.append("| Tier | Details |")
            lines.append("|------|---------|")
            for tier in assessment.cost_tiers:
                tier_name = tier.get("name", tier.get("tier", "Unknown"))
                tier_details = ", ".join(
                    f"{k}: {v}" for k, v in tier.items() if k not in ("name", "tier")
                )
                lines.append(f"| {tier_name} | {tier_details} |")
            lines.append("")

        if assessment.paid_fields:
            lines.append("#### Paid Fields\n")
            for field_info in assessment.paid_fields:
                field_name = field_info.get("field", field_info.get("name", "Unknown"))
                tier_required = field_info.get("tier", field_info.get("access", "Unknown"))
                lines.append(f"- **{field_name}**: requires {tier_required}")
            lines.append("")

    return "\n".join(lines)


def _generate_filtering_summary(data: DiscoveryReportData) -> str:
    """Generate filtering summary section."""
    lines = []
    lines.append("## Filtering Summary\n")

    search_config = data.search_config
    if not search_config:
        lines.append("No filtering configuration recorded.\n")
        return "\n".join(lines)

    lines.append("### Search Terms Used\n")

    kaggle_terms = search_config.get("kaggle_search_terms", [])
    if kaggle_terms:
        lines.append("**Kaggle:**")
        for term in kaggle_terms:
            lines.append(f"- `{term}`")
        lines.append("")

    hf_terms = search_config.get("huggingface_search_terms", [])
    if hf_terms:
        lines.append("**HuggingFace:**")
        for term in hf_terms:
            lines.append(f"- `{term}`")
        lines.append("")

    # Filter criteria
    filter_config = search_config.get("filter_config", {})
    if filter_config:
        lines.append("### Filter Criteria Applied\n")
        lines.append(f"- **Require complete:** {filter_config.get('require_complete', False)}")
        lines.append(f"- **Minimum downloads:** {filter_config.get('min_downloads', 0)}")
        max_freshness = filter_config.get("max_freshness_days", -1)
        lines.append(f"- **Max freshness (days):** {'no limit' if max_freshness <= 0 else max_freshness}")
        lines.append(f"- **Minimum records:** {filter_config.get('min_records', 0)}")
        lines.append(f"- **Top-K limit:** {filter_config.get('top_k', 0)}")
        lines.append("")

    filtered_out = data.summary.get("filtered_out", 0)
    if filtered_out > 0:
        lines.append(f"**{filtered_out} dataset(s)** were removed by filtering.\n")

    return "\n".join(lines)


def _generate_next_steps(data: DiscoveryReportData) -> str:
    """Generate actionable next-steps section."""
    lines = []
    lines.append("## Next Steps\n")

    complete_count = sum(1 for d in data.datasets if d.is_complete)

    if complete_count > 0:
        lines.append("1. Download the complete dataset(s) listed above and place CSV files in `data/`")
        lines.append("2. Run Phase 2 analysis: `python main.py --phase analysis`")
        lines.append("3. Review the EDA report for quality assessment and surge viability")
    else:
        lines.append("No complete datasets were found. Consider the following options:\n")
        lines.append("1. **Download promising datasets** — Even incomplete datasets may contain "
                     "the needed columns once inspected (column detection from API metadata is imperfect)")
        lines.append("2. **Broaden search terms** — Add more specific terms to the configuration")
        lines.append("3. **Manual curation** — Search Kaggle/HuggingFace directly and add datasets "
                     "to `data/` manually")
        lines.append("4. **API collection** — If API feasibility looks good, consider collecting "
                     "fresh data via the assessed APIs")

    lines.append("")
    lines.append("Once datasets are placed in `data/`, run:\n")
    lines.append("```bash")
    lines.append("python main.py --phase analysis")
    lines.append("```\n")

    return "\n".join(lines)
