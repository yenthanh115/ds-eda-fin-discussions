"""Report generator module for the EDA Financial Discussions pipeline."""

import os
from datetime import datetime
from typing import Any

from src.models import APIAssessment, DatasetMetadata, QualityReport, SurgeResult


def generate_report(
    discovery_results: list[DatasetMetadata],
    api_assessments: list[APIAssessment],
    quality_reports: list[QualityReport],
    surge_results: list[SurgeResult],
    chart_paths: list[str],
    output_path: str,
) -> str:
    """Generate comprehensive markdown report. Returns file path.

    Args:
        discovery_results: List of discovered dataset metadata.
        api_assessments: List of API feasibility assessments.
        quality_reports: List of dataset quality analysis reports.
        surge_results: List of surge definition evaluation results.
        chart_paths: List of paths to generated chart files.
        output_path: Path where the markdown report will be written.

    Returns:
        The file path of the generated report.
    """
    sections = []

    # Title
    sections.append("# EDA Financial Discussions - Analysis Report\n")
    sections.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # Executive Summary
    sections.append(_generate_executive_summary(
        discovery_results, api_assessments, quality_reports, surge_results
    ))

    # Dataset Discovery Results
    sections.append(_generate_discovery_section(discovery_results))

    # API Feasibility Findings
    sections.append(_generate_api_feasibility_section(api_assessments))

    # EDA Statistics
    sections.append(_generate_eda_statistics_section(quality_reports))

    # Surge Analysis Results
    sections.append(_generate_surge_analysis_section(surge_results))

    # Charts
    sections.append(_generate_charts_section(chart_paths, output_path))

    # Final Recommendation
    sections.append(_generate_recommendation_section(
        quality_reports, api_assessments, surge_results
    ))

    report_content = "\n".join(sections)

    # Write report to file
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return output_path


def _generate_executive_summary(
    discovery_results: list[DatasetMetadata],
    api_assessments: list[APIAssessment],
    quality_reports: list[QualityReport],
    surge_results: list[SurgeResult],
) -> str:
    """Generate the executive summary section."""
    lines = []
    lines.append("## Executive Summary\n")

    total_datasets = len(discovery_results)
    complete_datasets = sum(1 for d in discovery_results if d.is_complete)
    suitable_datasets = sum(1 for q in quality_reports if q.recommendation == "suitable")
    viable_surges = sum(1 for s in surge_results if s.is_viable)
    total_surge_defs = len(surge_results)

    lines.append(
        "This report summarizes the exploratory data analysis conducted to identify "
        "suitable datasets for predicting engagement and sentiment surges in "
        "stock-related social media discussions.\n"
    )

    lines.append("### Key Findings\n")
    lines.append(f"- **Datasets discovered:** {total_datasets} "
                 f"({complete_datasets} complete with engagement + sentiment fields)")
    lines.append(f"- **API platforms assessed:** {len(api_assessments)}")
    lines.append(f"- **Quality reports generated:** {len(quality_reports)} "
                 f"({suitable_datasets} suitable)")
    lines.append(f"- **Surge definitions evaluated:** {total_surge_defs} "
                 f"({viable_surges} viable with ≥2% positive class)")
    lines.append("")

    return "\n".join(lines)


def _generate_discovery_section(discovery_results: list[DatasetMetadata]) -> str:
    """Generate the dataset discovery results section."""
    lines = []
    lines.append("## Dataset Discovery Results\n")

    if not discovery_results:
        lines.append("No datasets were discovered during the scan.\n")
        return "\n".join(lines)

    # Group by platform
    kaggle_datasets = [d for d in discovery_results if d.source_platform == "kaggle"]
    hf_datasets = [d for d in discovery_results if d.source_platform == "huggingface"]

    platforms = set(d.source_platform for d in discovery_results)
    lines.append(f"A total of **{len(discovery_results)}** datasets were discovered "
                 f"across {len(platforms)} platform(s).\n")

    if kaggle_datasets:
        lines.append("### Kaggle Datasets\n")
        lines.append(_format_dataset_table(kaggle_datasets))
        lines.append("")

    if hf_datasets:
        lines.append("### HuggingFace Datasets\n")
        lines.append(_format_dataset_table(hf_datasets))
        lines.append("")

    # Flag incomplete datasets
    incomplete = [d for d in discovery_results if not d.is_complete]
    if incomplete:
        lines.append("### Incomplete Datasets\n")
        lines.append("The following datasets are flagged as incomplete for surge prediction "
                     "(missing engagement metrics or sentiment fields):\n")
        for d in incomplete:
            missing = []
            if not d.has_engagement_metrics:
                missing.append("engagement metrics")
            if not d.has_sentiment_fields:
                missing.append("sentiment fields")
            lines.append(f"- **{d.name}** ({d.source_platform}): missing {', '.join(missing)}")
        lines.append("")

    return "\n".join(lines)


def _format_dataset_table(datasets: list[DatasetMetadata]) -> str:
    """Format a list of datasets as a markdown table."""
    lines = []
    lines.append("| Name | Records | Date Range | Freshness (days) | Complete |")
    lines.append("|------|---------|------------|------------------|----------|")
    for d in datasets:
        date_range = f"{d.date_range[0]} to {d.date_range[1]}"
        complete = "✓" if d.is_complete else "✗"
        lines.append(f"| {d.name} | {d.record_count:,} | {date_range} | {d.freshness_days} | {complete} |")
    return "\n".join(lines)


def _generate_api_feasibility_section(api_assessments: list[APIAssessment]) -> str:
    """Generate the API feasibility findings section."""
    lines = []
    lines.append("## API Feasibility Findings\n")

    if not api_assessments:
        lines.append("No API assessments were performed.\n")
        return "\n".join(lines)

    for assessment in api_assessments:
        lines.append(f"### {assessment.platform.title()} API\n")

        lines.append(f"- **Historical access:** {'Yes' if assessment.historical_access else 'No'}")
        lines.append(f"- **Supports surge label construction:** "
                     f"{'Yes' if assessment.supports_surge_label else 'No'}")
        lines.append(f"- **Estimated collection time:** {assessment.estimated_collection_time_hours:.1f} hours")
        lines.append(f"- **Estimated cost:** ${assessment.estimated_cost_usd:.2f}")
        lines.append(f"- **Endpoints available:** {len(assessment.endpoints)}")
        lines.append("")

        # Rate limits
        if assessment.rate_limits:
            lines.append("#### Rate Limits\n")
            for key, value in assessment.rate_limits.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        # Cost tiers
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

        # Paid fields
        if assessment.paid_fields:
            lines.append("#### Paid Fields\n")
            lines.append("The following fields require paid access:\n")
            for field_info in assessment.paid_fields:
                field_name = field_info.get("field", field_info.get("name", "Unknown"))
                tier_required = field_info.get("tier", field_info.get("access", "Unknown"))
                lines.append(f"- **{field_name}**: requires {tier_required}")
            lines.append("")

    return "\n".join(lines)


def _generate_eda_statistics_section(quality_reports: list[QualityReport]) -> str:
    """Generate the EDA statistics section."""
    lines = []
    lines.append("## EDA Statistics\n")

    if not quality_reports:
        lines.append("No quality analysis was performed.\n")
        return "\n".join(lines)

    for report in quality_reports:
        lines.append(f"### {report.dataset_name}\n")

        # Structure overview
        lines.append("#### Dataset Structure\n")
        lines.append(f"- **Records:** {report.record_count:,}")
        lines.append(f"- **Tickers:** {report.ticker_count}")
        lines.append(f"- **Columns:** {len(report.schema)}")
        lines.append(f"- **Date range:** {report.date_range[0]} to {report.date_range[1]}")
        lines.append(f"- **Recommendation:** {report.recommendation}")
        lines.append("")

        # Missing values
        if report.missing_values:
            lines.append("#### Missing Values\n")
            if report.high_risk_columns:
                lines.append(f"**High-risk columns (>30% missing):** "
                             f"{', '.join(report.high_risk_columns)}\n")
            lines.append("| Column | Missing % |")
            lines.append("|--------|-----------|")
            for col, pct in sorted(report.missing_values.items(), key=lambda x: x[1], reverse=True):
                if pct > 0:
                    flag = " ⚠️" if col in report.high_risk_columns else ""
                    lines.append(f"| {col} | {pct:.1f}%{flag} |")
            lines.append("")

        # Temporal gaps
        if report.temporal_gaps:
            lines.append("#### Temporal Gaps (>7 days)\n")
            for gap_start, gap_end in report.temporal_gaps:
                lines.append(f"- {gap_start} to {gap_end}")
            lines.append("")

        # Engagement statistics
        if report.engagement_stats:
            lines.append("#### Engagement Statistics\n")
            lines.append("| Metric | Mean | Median | P90 | P95 | P99 |")
            lines.append("|--------|------|--------|-----|-----|-----|")
            for metric, stats in report.engagement_stats.items():
                mean = stats.get("mean", 0)
                median = stats.get("median", 0)
                p90 = stats.get("p90", 0)
                p95 = stats.get("p95", 0)
                p99 = stats.get("p99", 0)
                lines.append(f"| {metric} | {mean:.1f} | {median:.1f} | "
                             f"{p90:.1f} | {p95:.1f} | {p99:.1f} |")
            lines.append("")

        # Sentiment statistics
        if report.sentiment_stats:
            lines.append("#### Sentiment Statistics\n")
            for stat_name, value in report.sentiment_stats.items():
                lines.append(f"- **{stat_name}:** {value:.3f}")
            lines.append(f"- **Bullish/Bearish ratio:** {report.bullish_bearish_ratio:.2f}")
            lines.append("")

        # Risks
        if report.risks:
            lines.append("#### Identified Risks\n")
            for risk in report.risks:
                lines.append(f"- {risk}")
            lines.append("")

        # Failing objectives
        if report.failing_objectives:
            lines.append("#### Failing EDA Objectives\n")
            for obj in report.failing_objectives:
                lines.append(f"- ❌ {obj}")
            lines.append("")

    return "\n".join(lines)


def _generate_surge_analysis_section(surge_results: list[SurgeResult]) -> str:
    """Generate the surge analysis results section."""
    lines = []
    lines.append("## Surge Analysis Results\n")

    if not surge_results:
        lines.append("No surge analysis was performed.\n")
        return "\n".join(lines)

    lines.append("Surge definitions were evaluated across multiple threshold combinations.\n")
    lines.append("| Engagement Percentile | Sentiment Std Devs | Window (hrs) | "
                 "Surge Count | Total Posts | Surge % | Imbalance Ratio | Viable |")
    lines.append("|----------------------|-------------------|--------------|"
                 "------------|-------------|---------|-----------------|--------|")

    for result in surge_results:
        viable = "✓" if result.is_viable else "✗"
        lines.append(
            f"| {result.config.engagement_percentile:.2f} "
            f"| {result.config.sentiment_std_devs:.1f} "
            f"| {result.config.time_window_hours} "
            f"| {result.surge_count:,} "
            f"| {result.total_posts:,} "
            f"| {result.surge_percentage:.2f}% "
            f"| {result.class_imbalance_ratio:.1f}:1 "
            f"| {viable} |"
        )

    lines.append("")

    # Summary
    viable_results = [r for r in surge_results if r.is_viable]
    if viable_results:
        lines.append(f"**{len(viable_results)} viable surge definition(s)** found "
                     f"(positive class ≥ 2%).\n")
        best = max(viable_results, key=lambda r: r.surge_percentage)
        lines.append(
            f"Best viable definition: engagement ≥ {best.config.engagement_percentile:.0%} "
            f"percentile + sentiment shift ≥ {best.config.sentiment_std_devs:.1f} std devs "
            f"→ {best.surge_percentage:.2f}% surge rate.\n"
        )
    else:
        lines.append("**No viable surge definitions found.** All evaluated combinations "
                     "produce fewer than 2% positive class instances.\n")

    # Timestamp sufficiency
    insufficient_ts = [r for r in surge_results if not r.timestamp_sufficient]
    if insufficient_ts:
        lines.append("> ⚠️ **Note:** Some surge definitions may be limited by insufficient "
                     "timestamp resolution for 24-hour window measurement.\n")

    return "\n".join(lines)


def _generate_charts_section(chart_paths: list[str], output_path: str) -> str:
    """Generate the charts section with inline image references using relative paths."""
    lines = []
    lines.append("## Visualizations\n")

    if not chart_paths:
        lines.append("No charts were generated.\n")
        return "\n".join(lines)

    report_dir = os.path.dirname(os.path.abspath(output_path))

    for chart_path in chart_paths:
        # Compute relative path from report location to chart
        abs_chart = os.path.abspath(chart_path)
        try:
            rel_path = os.path.relpath(abs_chart, report_dir)
        except ValueError:
            # On Windows, relpath fails if paths are on different drives.
            # Fall back to using the chart path as-is.
            rel_path = chart_path
        # Normalize to forward slashes for markdown compatibility
        rel_path = rel_path.replace("\\", "/")

        # Derive a descriptive name from the filename
        chart_name = os.path.splitext(os.path.basename(chart_path))[0]
        chart_title = chart_name.replace("_", " ").replace("-", " ").title()

        lines.append(f"### {chart_title}\n")
        lines.append(f"![{chart_title}]({rel_path})\n")

    return "\n".join(lines)


def _generate_recommendation_section(
    quality_reports: list[QualityReport],
    api_assessments: list[APIAssessment],
    surge_results: list[SurgeResult],
) -> str:
    """Generate the final recommendation section."""
    lines = []
    lines.append("## Final Recommendation\n")

    recommendation = make_recommendation(quality_reports, api_assessments, surge_results)

    recommended_path = recommendation["recommended_path"]
    if recommended_path == "none":
        lines.append("### No Suitable Path Identified\n")
    elif recommended_path == "public_dataset":
        lines.append(f"### Recommended Path: Public Dataset ({recommendation['recommended_source']})\n")
    elif recommended_path == "api_collection":
        lines.append(f"### Recommended Path: API Collection ({recommendation['recommended_source']})\n")
    else:
        lines.append(f"### Recommended Path: {recommended_path}\n")

    lines.append(f"{recommendation['justification']}\n")

    if recommendation.get("ranked_options"):
        lines.append("### Ranked Options\n")
        for option in recommendation["ranked_options"]:
            rank = option["rank"]
            lines.append(f"{rank}. **{option['name']}** (score: {option['score']:.3f})")
            if option.get("trade_offs"):
                for trade_off in option["trade_offs"]:
                    lines.append(f"   - {trade_off}")
        lines.append("")

    if recommendation.get("gaps"):
        lines.append("### Identified Gaps\n")
        for gap in recommendation["gaps"]:
            lines.append(f"- {gap}")
        lines.append("")

    if recommendation.get("next_steps"):
        lines.append("### Next Steps\n")
        for step in recommendation["next_steps"]:
            lines.append(f"- {step}")
        lines.append("")

    return "\n".join(lines)


def evaluate_dataset_suitability(objective_results: dict[str, bool]) -> dict[str, Any]:
    """Evaluate dataset suitability based on EDA objective pass/fail results.

    Produces a go/no-go recommendation with justification. A dataset is
    recommended as unsuitable if 3 or more objectives fail.

    Args:
        objective_results: Dictionary mapping EDA objective names to pass/fail
            booleans (True = pass, False = fail).

    Returns:
        Dictionary with:
            - recommendation: "suitable" or "unsuitable"
            - failing_objectives: list of objective names that failed
            - passing_objectives: list of objective names that passed
            - total_objectives: total number of objectives evaluated
            - failure_count: number of failing objectives
            - justification: human-readable justification string
    """
    failing_objectives = [
        name for name, passed in objective_results.items() if not passed
    ]
    passing_objectives = [
        name for name, passed in objective_results.items() if passed
    ]

    failure_count = len(failing_objectives)
    total_objectives = len(objective_results)

    # Dataset is unsuitable if 3 or more objectives fail
    if failure_count >= 3:
        recommendation = "unsuitable"
        justification = (
            f"Dataset is unsuitable: {failure_count} of {total_objectives} "
            f"EDA objectives failed (threshold: 3). "
            f"Failing objectives: {', '.join(failing_objectives)}."
        )
    else:
        recommendation = "suitable"
        if failure_count == 0:
            justification = (
                f"Dataset is suitable: all {total_objectives} EDA objectives passed."
            )
        else:
            justification = (
                f"Dataset is suitable: only {failure_count} of {total_objectives} "
                f"EDA objectives failed (threshold: 3). "
                f"Failing objectives: {', '.join(failing_objectives)}."
            )

    return {
        "recommendation": recommendation,
        "failing_objectives": failing_objectives,
        "passing_objectives": passing_objectives,
        "total_objectives": total_objectives,
        "failure_count": failure_count,
        "justification": justification,
    }


def _score_quality_report(report: QualityReport) -> dict:
    """Score a quality report on multiple dimensions.

    Returns a dict with scores (0-1) for each dimension and an overall score.
    """
    # Data completeness: penalize for high-risk columns
    total_cols = len(report.schema) if report.schema else 1
    high_risk_ratio = len(report.high_risk_columns) / max(total_cols, 1)
    completeness_score = 1.0 - min(high_risk_ratio, 1.0)

    # Record count score: more records = better (diminishing returns)
    if report.record_count >= 100_000:
        volume_score = 1.0
    elif report.record_count >= 10_000:
        volume_score = 0.8
    elif report.record_count >= 1_000:
        volume_score = 0.5
    else:
        volume_score = 0.2

    # Temporal coverage: penalize for gaps
    gap_count = len(report.temporal_gaps)
    if gap_count == 0:
        temporal_score = 1.0
    elif gap_count <= 3:
        temporal_score = 0.7
    elif gap_count <= 10:
        temporal_score = 0.4
    else:
        temporal_score = 0.2

    # Ticker diversity
    if report.ticker_count >= 50:
        diversity_score = 1.0
    elif report.ticker_count >= 10:
        diversity_score = 0.7
    elif report.ticker_count >= 3:
        diversity_score = 0.4
    else:
        diversity_score = 0.2

    # Risk penalty
    risk_count = len(report.risks)
    risk_score = max(0.0, 1.0 - (risk_count * 0.15))

    overall = (
        completeness_score * 0.25
        + volume_score * 0.20
        + temporal_score * 0.20
        + diversity_score * 0.15
        + risk_score * 0.20
    )

    return {
        "completeness": completeness_score,
        "volume": volume_score,
        "temporal": temporal_score,
        "diversity": diversity_score,
        "risk": risk_score,
        "overall": overall,
    }


def _score_api_assessment(assessment: APIAssessment) -> dict:
    """Score an API assessment on multiple dimensions.

    Returns a dict with scores (0-1) for each dimension and an overall score.
    """
    # Cost score: lower cost = better
    if assessment.estimated_cost_usd == 0.0:
        cost_score = 1.0
    elif assessment.estimated_cost_usd <= 50.0:
        cost_score = 0.8
    elif assessment.estimated_cost_usd <= 200.0:
        cost_score = 0.5
    elif assessment.estimated_cost_usd <= 1000.0:
        cost_score = 0.3
    else:
        cost_score = 0.1

    # Time score: faster collection = better
    if assessment.estimated_collection_time_hours <= 1.0:
        time_score = 1.0
    elif assessment.estimated_collection_time_hours <= 10.0:
        time_score = 0.7
    elif assessment.estimated_collection_time_hours <= 100.0:
        time_score = 0.4
    else:
        time_score = 0.2

    # Feasibility: supports surge label construction
    feasibility_score = 1.0 if assessment.supports_surge_label else 0.3

    # Historical access
    historical_score = 1.0 if assessment.historical_access else 0.3

    # Field availability: more fields = better
    field_count = len(assessment.available_fields)
    if field_count >= 10:
        field_score = 1.0
    elif field_count >= 5:
        field_score = 0.7
    else:
        field_score = 0.4

    overall = (
        cost_score * 0.25
        + time_score * 0.20
        + feasibility_score * 0.25
        + historical_score * 0.15
        + field_score * 0.15
    )

    return {
        "cost": cost_score,
        "time": time_score,
        "feasibility": feasibility_score,
        "historical": historical_score,
        "fields": field_score,
        "overall": overall,
    }


def _check_surge_viability(surge_results: list[SurgeResult]) -> dict:
    """Assess surge definition viability from results.

    Returns a dict with viability summary.
    """
    if not surge_results:
        return {
            "has_viable_definition": False,
            "viable_count": 0,
            "total_evaluated": 0,
            "best_surge_percentage": 0.0,
            "timestamp_sufficient": False,
        }

    viable = [r for r in surge_results if r.is_viable]
    best_pct = max((r.surge_percentage for r in surge_results), default=0.0)
    timestamp_ok = any(r.timestamp_sufficient for r in surge_results)

    return {
        "has_viable_definition": len(viable) > 0,
        "viable_count": len(viable),
        "total_evaluated": len(surge_results),
        "best_surge_percentage": best_pct,
        "timestamp_sufficient": timestamp_ok,
    }


def make_recommendation(
    quality_reports: list[QualityReport],
    api_assessments: list[APIAssessment],
    surge_results: list[SurgeResult],
) -> dict:
    """Determine best data path with justification.

    Evaluates public datasets (via quality reports) and API collection paths
    (via API assessments), considering surge analysis viability, to recommend
    the best data acquisition strategy.

    Args:
        quality_reports: Quality analysis results for discovered datasets.
        api_assessments: Feasibility assessments for collection APIs.
        surge_results: Results from surge definition evaluation.

    Returns:
        A dict containing:
        - recommended_path: "public_dataset" | "api_collection" | "none"
        - recommended_source: Name of the specific recommended source
        - justification: Explanation of why this path was chosen
        - ranked_options: List of all options ranked by score with trade-offs
        - gaps: List of identified gaps (empty if a suitable path exists)
        - next_steps: Suggested next steps (especially if no suitable path)
    """
    surge_viability = _check_surge_viability(surge_results)

    # Score all dataset options
    dataset_options = []
    for report in quality_reports:
        scores = _score_quality_report(report)
        dataset_options.append({
            "type": "public_dataset",
            "name": report.dataset_name,
            "scores": scores,
            "overall_score": scores["overall"],
            "trade_offs": _dataset_trade_offs(report, scores),
        })

    # Score all API options
    api_options = []
    for assessment in api_assessments:
        scores = _score_api_assessment(assessment)
        api_options.append({
            "type": "api_collection",
            "name": f"{assessment.platform} API",
            "scores": scores,
            "overall_score": scores["overall"],
            "trade_offs": _api_trade_offs(assessment, scores),
        })

    # Combine and rank all options
    all_options = dataset_options + api_options
    all_options.sort(key=lambda x: x["overall_score"], reverse=True)

    # Build ranked options list with trade-offs
    ranked_options = []
    for rank, option in enumerate(all_options, 1):
        ranked_options.append({
            "rank": rank,
            "type": option["type"],
            "name": option["name"],
            "score": round(option["overall_score"], 3),
            "trade_offs": option["trade_offs"],
        })

    # Determine gaps
    gaps = _identify_gaps(quality_reports, api_assessments, surge_viability)

    # Make the recommendation
    if not all_options:
        return {
            "recommended_path": "none",
            "recommended_source": "",
            "justification": (
                "No datasets or API paths were evaluated. "
                "Cannot make a recommendation without data sources to assess."
            ),
            "ranked_options": [],
            "gaps": gaps if gaps else ["No data sources available for evaluation"],
            "next_steps": [
                "Identify and catalog potential data sources",
                "Search for stock discussion datasets on Kaggle and HuggingFace",
                "Evaluate X/Twitter and Reddit API access options",
            ],
        }

    best_option = all_options[0]

    # Check if the best option meets minimum viability
    minimum_score_threshold = 0.4
    meets_minimum = best_option["overall_score"] >= minimum_score_threshold

    # Also check surge viability as a hard requirement
    surge_ok = surge_viability["has_viable_definition"] or not surge_results

    if not meets_minimum or (surge_results and not surge_ok):
        return {
            "recommended_path": "none",
            "recommended_source": "",
            "justification": _build_no_suitable_path_justification(
                best_option, surge_viability, meets_minimum
            ),
            "ranked_options": ranked_options,
            "gaps": gaps,
            "next_steps": _suggest_next_steps(gaps, surge_viability),
        }

    # Build justification for the recommended path
    justification = _build_justification(best_option, surge_viability)

    return {
        "recommended_path": best_option["type"],
        "recommended_source": best_option["name"],
        "justification": justification,
        "ranked_options": ranked_options,
        "gaps": gaps,
        "next_steps": _suggest_next_steps(gaps, surge_viability) if gaps else [],
    }


def _dataset_trade_offs(report: QualityReport, scores: dict) -> list[str]:
    """Generate trade-off descriptions for a dataset option."""
    trade_offs = []

    if scores["completeness"] >= 0.8:
        trade_offs.append("High data completeness with few missing values")
    elif scores["completeness"] < 0.5:
        trade_offs.append("Significant missing data may require imputation")

    if scores["volume"] >= 0.8:
        trade_offs.append("Large dataset suitable for model training")
    elif scores["volume"] < 0.5:
        trade_offs.append("Limited record count may constrain model performance")

    if scores["temporal"] >= 0.7:
        trade_offs.append("Good temporal coverage with minimal gaps")
    elif scores["temporal"] < 0.5:
        trade_offs.append("Temporal gaps may affect time-series analysis")

    if report.risks:
        trade_offs.append(f"{len(report.risks)} risk(s) identified: {', '.join(report.risks[:3])}")

    if not trade_offs:
        trade_offs.append("Moderate quality across all dimensions")

    return trade_offs


def _api_trade_offs(assessment: APIAssessment, scores: dict) -> list[str]:
    """Generate trade-off descriptions for an API option."""
    trade_offs = []

    if scores["cost"] >= 0.8:
        trade_offs.append("Low cost for data collection")
    elif scores["cost"] < 0.5:
        trade_offs.append(
            f"Estimated cost: ${assessment.estimated_cost_usd:.2f} for 10k posts"
        )

    if scores["time"] >= 0.7:
        trade_offs.append("Fast collection time")
    elif scores["time"] < 0.5:
        trade_offs.append(
            f"Collection time: ~{assessment.estimated_collection_time_hours:.1f} hours"
        )

    if assessment.supports_surge_label:
        trade_offs.append("Supports surge label construction")
    else:
        trade_offs.append("Insufficient fields for surge label construction")

    if not assessment.historical_access:
        trade_offs.append("No historical data access - requires prospective collection")

    if assessment.paid_fields:
        paid_names = [f["field"] if "field" in f else str(f) for f in assessment.paid_fields[:3]]
        trade_offs.append(f"Some fields require paid access: {', '.join(paid_names)}")

    if not trade_offs:
        trade_offs.append("Moderate feasibility across all dimensions")

    return trade_offs


def _identify_gaps(
    quality_reports: list[QualityReport],
    api_assessments: list[APIAssessment],
    surge_viability: dict,
) -> list[str]:
    """Identify gaps in available data paths."""
    gaps = []

    if not surge_viability["has_viable_definition"] and surge_viability["total_evaluated"] > 0:
        gaps.append(
            "No viable surge definition found - all evaluated definitions "
            f"produce <2% positive class (best: {surge_viability['best_surge_percentage']:.2f}%)"
        )

    if not surge_viability["timestamp_sufficient"] and surge_viability["total_evaluated"] > 0:
        gaps.append(
            "Timestamp resolution insufficient for 24-hour window measurement"
        )

    # Check if any dataset has high-risk columns
    for report in quality_reports:
        if len(report.high_risk_columns) > 3:
            gaps.append(
                f"Dataset '{report.dataset_name}' has {len(report.high_risk_columns)} "
                "high-risk columns (>30% missing)"
            )

    # Check if APIs lack surge label support
    apis_without_surge = [a for a in api_assessments if not a.supports_surge_label]
    if apis_without_surge and len(apis_without_surge) == len(api_assessments):
        gaps.append(
            "No evaluated API supports full surge label construction"
        )

    # Check if no historical access available
    apis_without_history = [a for a in api_assessments if not a.historical_access]
    if apis_without_history and len(apis_without_history) == len(api_assessments):
        gaps.append(
            "No API provides historical data access - prospective collection required"
        )

    return gaps


def _build_justification(option: dict, surge_viability: dict) -> str:
    """Build justification text for the recommended option."""
    parts = []

    if option["type"] == "public_dataset":
        parts.append(
            f"Recommend public dataset '{option['name']}' as the best data path."
        )
        scores = option["scores"]
        strengths = []
        if scores["completeness"] >= 0.7:
            strengths.append("good data completeness")
        if scores["volume"] >= 0.7:
            strengths.append("sufficient record volume")
        if scores["temporal"] >= 0.7:
            strengths.append("adequate temporal coverage")
        if strengths:
            parts.append(f"Key strengths: {', '.join(strengths)}.")
        parts.append(
            "Public datasets offer immediate availability without collection delays or API costs."
        )
    else:
        parts.append(
            f"Recommend API collection via '{option['name']}' as the best data path."
        )
        scores = option["scores"]
        strengths = []
        if scores["cost"] >= 0.7:
            strengths.append("reasonable cost")
        if scores["feasibility"] >= 0.7:
            strengths.append("supports surge label construction")
        if scores["historical"] >= 0.7:
            strengths.append("historical data access available")
        if strengths:
            parts.append(f"Key strengths: {', '.join(strengths)}.")
        parts.append(
            "API collection provides fresh, customizable data tailored to the prediction task."
        )

    if surge_viability["has_viable_definition"]:
        parts.append(
            f"Surge analysis confirms viable definitions exist "
            f"({surge_viability['viable_count']}/{surge_viability['total_evaluated']} "
            f"configurations produce ≥2% positive class)."
        )

    return " ".join(parts)


def _build_no_suitable_path_justification(
    best_option: dict, surge_viability: dict, meets_minimum: bool
) -> str:
    """Build justification for when no suitable path exists."""
    parts = ["No suitable data path meets minimum requirements for surge prediction."]

    if not meets_minimum:
        parts.append(
            f"The best available option ('{best_option['name']}') scored "
            f"{best_option['overall_score']:.2f}, below the minimum threshold of 0.4."
        )

    if not surge_viability["has_viable_definition"] and surge_viability["total_evaluated"] > 0:
        parts.append(
            "Additionally, no viable surge definition was found - all evaluated "
            "configurations produce insufficient positive class representation."
        )

    return " ".join(parts)


def _suggest_next_steps(gaps: list[str], surge_viability: dict) -> list[str]:
    """Suggest next steps based on identified gaps."""
    next_steps = []

    if not surge_viability["has_viable_definition"] and surge_viability["total_evaluated"] > 0:
        next_steps.append(
            "Explore alternative surge definitions with relaxed thresholds "
            "or composite engagement metrics"
        )
        next_steps.append(
            "Consider collecting more data to increase positive class representation"
        )

    if not surge_viability["timestamp_sufficient"] and surge_viability["total_evaluated"] > 0:
        next_steps.append(
            "Seek data sources with sub-daily timestamp resolution "
            "to enable 24-hour window analysis"
        )

    for gap in gaps:
        if "high-risk columns" in gap:
            next_steps.append(
                "Investigate imputation strategies for columns with high missing rates"
            )
            break

    for gap in gaps:
        if "No evaluated API supports" in gap:
            next_steps.append(
                "Evaluate additional APIs or data providers that offer "
                "engagement + sentiment + timestamp fields"
            )
            break

    for gap in gaps:
        if "prospective collection" in gap:
            next_steps.append(
                "Plan a prospective data collection campaign with sufficient lead time"
            )
            break

    if not next_steps:
        next_steps.append("Review and address identified gaps before proceeding")

    return next_steps
