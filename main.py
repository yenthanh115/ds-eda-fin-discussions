"""Main entry point for the EDA Financial Discussions pipeline.

This script orchestrates all analysis stages in sequence:
1. Dataset Discovery (Kaggle, HuggingFace)
2. API Feasibility Assessment (X/Twitter, Reddit)
3. Dataset Quality Analysis
4. Surge Analysis
5. Visualization
6. Report Generation

Each stage is executed independently with graceful error handling.
If a stage fails, the pipeline logs the error and continues with
remaining stages, producing a partial report.
"""

import csv
import logging
import os
import sys
import time

import pandas as pd

from src.models import (
    DatasetStore,
    EnrichedDataset,
    PipelineConfig,
    PipelineError,
    PipelineResult,
    QualityReport,
    SurgeConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute all analysis stages in sequence.

    Orchestrates the full EDA pipeline: dataset discovery, API feasibility,
    quality analysis, surge analysis, visualization, and report generation.
    Each stage is wrapped in error handling so that failures in one stage
    do not prevent subsequent stages from executing.

    Args:
        config: PipelineConfig with all pipeline parameters.

    Returns:
        PipelineResult containing aggregated results from all stages,
        including any errors encountered.
    """
    result = PipelineResult()
    os.makedirs(config.output_dir, exist_ok=True)

    pipeline_start = time.perf_counter()
    stage_timings: dict[str, float] = {}

    # ─── Stage 1/6: Dataset Discovery ───────────────────────────────────
    print("Stage 1/6: Dataset Discovery...")
    t0 = time.perf_counter()
    result = _run_discovery_stage(config, result)
    stage_timings["Dataset Discovery"] = time.perf_counter() - t0

    # ─── Stage 2/6: API Feasibility Assessment ──────────────────────────
    print("Stage 2/6: API Feasibility Assessment...")
    t0 = time.perf_counter()
    result = _run_api_feasibility_stage(config, result)
    stage_timings["API Feasibility"] = time.perf_counter() - t0

    # ─── Dataset Preparation: Load & Enrich Once ────────────────────────
    print("Preparing datasets: Loading & enriching...")
    t0 = time.perf_counter()
    store = _load_and_enrich_datasets(config)
    stage_timings["Dataset Preparation"] = time.perf_counter() - t0
    print(f"  Loaded {len(store)} dataset(s)")
    if store.load_errors:
        result.errors.extend(store.load_errors)

    # ─── Stage 3/6: Dataset Quality Analysis ────────────────────────────
    print("Stage 3/6: Dataset Quality Analysis...")
    t0 = time.perf_counter()
    result, dataset_timings = _run_quality_stage(config, result, store)
    stage_timings["Dataset Quality"] = time.perf_counter() - t0

    # ─── Stage 4/6: Surge Analysis ──────────────────────────────────────
    print("Stage 4/6: Surge Analysis...")
    t0 = time.perf_counter()
    result = _run_surge_stage(config, result, store)
    stage_timings["Surge Analysis"] = time.perf_counter() - t0

    # ─── Stage 5/6: Visualization ───────────────────────────────────────
    print("Stage 5/6: Visualization...")
    t0 = time.perf_counter()
    result = _run_visualization_stage(config, result, store)
    stage_timings["Visualization"] = time.perf_counter() - t0

    # ─── Stage 6/6: Report Generation ───────────────────────────────────
    print("Stage 6/6: Report Generation...")
    t0 = time.perf_counter()
    # Compute total elapsed up to this point (report gen timing will be added after)
    pre_report_elapsed = time.perf_counter() - pipeline_start
    timing_info = {
        "stage_timings": stage_timings,
        "dataset_timings": dataset_timings,
        "total_elapsed": pre_report_elapsed,
    }
    result = _run_report_stage(config, result, timing_info)
    stage_timings["Report Generation"] = time.perf_counter() - t0

    total_elapsed = time.perf_counter() - pipeline_start

    # ─── Summary ────────────────────────────────────────────────────────
    _print_summary(result, stage_timings, total_elapsed)

    return result


def _run_discovery_stage(config: PipelineConfig, result: PipelineResult) -> PipelineResult:
    """Execute the dataset discovery stage."""
    try:
        from src.dataset_discovery import (
            flag_incomplete_datasets,
            scan_huggingface,
            scan_kaggle,
        )

        print("  Scanning Kaggle...")
        kaggle_datasets = scan_kaggle(config.kaggle_search_terms)
        print(f"  Found {len(kaggle_datasets)} Kaggle dataset(s)")

        print("  Scanning HuggingFace...")
        hf_datasets = scan_huggingface(config.huggingface_search_terms)
        print(f"  Found {len(hf_datasets)} HuggingFace dataset(s)")

        all_datasets = kaggle_datasets + hf_datasets
        all_datasets = flag_incomplete_datasets(all_datasets)

        complete_count = sum(1 for d in all_datasets if d.is_complete)
        print(f"  Total: {len(all_datasets)} datasets ({complete_count} complete)")

        result.datasets_discovered = all_datasets

    except Exception as e:
        error_msg = f"Dataset Discovery failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def _run_api_feasibility_stage(config: PipelineConfig, result: PipelineResult) -> PipelineResult:
    """Execute the API feasibility assessment stage."""
    try:
        from src.api_feasibility import assess_reddit_api, assess_twitter_api

        print("  Assessing X/Twitter API...")
        twitter_assessment = assess_twitter_api()
        print(f"  Twitter: supports_surge={twitter_assessment.supports_surge_label}, "
              f"cost=${twitter_assessment.estimated_cost_usd:.2f}")

        print("  Assessing Reddit API...")
        reddit_assessment = assess_reddit_api()
        print(f"  Reddit: supports_surge={reddit_assessment.supports_surge_label}, "
              f"cost=${reddit_assessment.estimated_cost_usd:.2f}")

        result.api_assessments = [twitter_assessment, reddit_assessment]

    except Exception as e:
        error_msg = f"API Feasibility Assessment failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def _run_quality_stage(config: PipelineConfig, result: PipelineResult, store: DatasetStore) -> tuple[PipelineResult, dict[str, float]]:
    """Execute the dataset quality analysis stage.

    Uses pre-loaded and enriched datasets from the DatasetStore rather than
    re-loading from disk. Column metadata (date_col, text_col, etc.) is
    already detected during the preparation phase.

    Returns:
        Tuple of (PipelineResult, dataset_timings dict mapping dataset name to seconds).
    """
    dataset_timings: dict[str, float] = {}
    try:
        from src.dataset_quality import (
            analyze_sentiment,
            analyze_structure,
            analyze_time_coverage,
            assess_sentiment_reliability,
            catalog_risks,
            compute_engagement_distributions,
            compute_missing_values,
        )
        from src.report_generator import evaluate_dataset_suitability

        if len(store) == 0:
            print("  No dataset files found for quality analysis. Skipping.")
            result.errors.append(
                "Dataset Quality Analysis: No dataset files found to analyze. "
                "Place CSV files in the project root or output directory."
            )
            return result, dataset_timings

        for ds in store:
            try:
                print(f"  Analyzing: {ds.name}")
                ds_start = time.perf_counter()
                df = ds.df

                # Structure analysis
                structure = analyze_structure(df)
                print(f"    Records: {structure['record_count']}, "
                      f"Columns: {structure['column_count']}")

                # Missing values
                missing = compute_missing_values(df)

                # Time coverage
                time_coverage = analyze_time_coverage(df, ds.date_col) if ds.date_col else {
                    "date_range": ("unknown", "unknown"),
                    "temporal_gaps": [],
                    "posting_frequency": {"posts_per_day": 0.0, "total_days": 0},
                    "gap_count": 0,
                }

                # Engagement distributions
                engagement_stats = compute_engagement_distributions(df, ds.engagement_cols)

                # Sentiment analysis
                sentiment_stats = {}
                bullish_bearish_ratio = 0.0
                sentiment_reliability = None

                if ds.text_col:
                    sentiment_result = analyze_sentiment(df, ds.text_col)
                    sentiment_stats = sentiment_result.get("polarity_scores", {})
                    bullish_bearish_ratio = sentiment_result.get("bullish_bearish_ratio", 0.0)

                    reliability = assess_sentiment_reliability(df, ds.text_col)
                    if reliability.get("total_compared", 0) > 0:
                        sentiment_reliability = {
                            "agreement_rate": reliability["agreement_rate"],
                            "correlation": reliability["correlation"],
                        }

                # Risk cataloging
                risks = catalog_risks(
                    df,
                    missing_result=missing,
                    time_result=time_coverage,
                    date_col=ds.date_col or "date",
                )

                # Evaluate suitability
                objective_results = _evaluate_eda_objectives(
                    structure, missing, time_coverage, engagement_stats,
                    sentiment_stats, ds.text_col, ds.engagement_cols
                )
                suitability = evaluate_dataset_suitability(objective_results)

                # Build QualityReport
                quality_report = QualityReport(
                    dataset_name=ds.name,
                    schema=structure["schema"],
                    record_count=structure["record_count"],
                    ticker_count=structure["ticker_count"],
                    missing_values=missing["missing_percentages"],
                    high_risk_columns=missing["high_risk_columns"],
                    date_range=time_coverage["date_range"],
                    temporal_gaps=time_coverage["temporal_gaps"],
                    posting_frequency=time_coverage["posting_frequency"],
                    engagement_stats=engagement_stats,
                    sentiment_stats=sentiment_stats,
                    bullish_bearish_ratio=bullish_bearish_ratio,
                    sentiment_reliability=sentiment_reliability,
                    risks=risks,
                    eda_questions_answered=objective_results,
                    failing_objectives=suitability["failing_objectives"],
                    recommendation=suitability["recommendation"],
                )
                result.quality_reports.append(quality_report)
                ds_elapsed = time.perf_counter() - ds_start
                dataset_timings[ds.name] = ds_elapsed
                print(f"    Recommendation: {suitability['recommendation']}")
                print(f"    ⏱ Dataset processed in {ds_elapsed:.2f}s")

            except Exception as e:
                error_msg = f"Quality analysis failed for {ds.path}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

    except Exception as e:
        error_msg = f"Dataset Quality Analysis stage failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result, dataset_timings


def _run_surge_stage(config: PipelineConfig, result: PipelineResult, store: DatasetStore) -> PipelineResult:
    """Execute the surge analysis stage.

    Uses pre-loaded and enriched datasets from the DatasetStore. Sentiment
    and ticker columns are already computed during the preparation phase.
    """
    try:
        from src.surge_analysis import (
            check_timestamp_resolution,
            evaluate_surge_definitions,
        )

        if len(store) == 0:
            print("  No dataset files found for surge analysis. Skipping.")
            result.errors.append(
                "Surge Analysis: No dataset files available for surge computation."
            )
            return result

        for ds in store:
            try:
                print(f"  Analyzing surges in: {ds.name}")
                surge_ds_start = time.perf_counter()

                # check if missing required columns for surge analysis
                if not ds.engagement_cols or not ds.sentiment_col or not ds.date_col or not ds.ticker_col:
                    missing_parts = []
                    if not ds.engagement_cols:
                        missing_parts.append(
                            "engagement (need one of: likes, retweets, comments, "
                            "upvotes, shares, favorites, score, num_comments, "
                            "comment_count, like_count, retweet_count, ups, downs)"
                        )
                    if not ds.sentiment_col:
                        missing_parts.append(
                            "sentiment (need one of: sentiment, polarity, "
                            "sentiment_score, compound, bullish, bearish)"
                        )
                    if not ds.date_col:
                        missing_parts.append(
                            "timestamp (need one of: date, timestamp, created_at, "
                            "created_utc, time, posted_at)"
                        )
                    if not ds.ticker_col:
                        missing_parts.append(
                            "ticker (need one of: ticker, symbol, stock, "
                            "stock_symbol)"
                        )
                    available_cols = ", ".join(ds.df.columns.tolist())
                    msg = (f"  Skipping {ds.name}: "
                           f"missing required columns for surge analysis.\n"
                           f"    Missing: {'; '.join(missing_parts)}\n"
                           f"    Available columns: {available_cols}")
                    print(msg)
                    result.errors.append(msg)
                    continue

                # Check timestamp resolution
                ts_resolution = check_timestamp_resolution(ds.df, ds.date_col)
                print(f"    Timestamp resolution: {ts_resolution['resolution']} "
                      f"(sufficient: {ts_resolution['sufficient']})")

                # Evaluate surge definitions
                surge_results = evaluate_surge_definitions(
                    ds.df,
                    percentiles=config.surge_percentiles,
                    std_devs=config.surge_std_devs,
                    engagement_cols=ds.engagement_cols,
                    sentiment_col=ds.sentiment_col,
                    timestamp_col=ds.date_col,
                    ticker_col=ds.ticker_col,
                )

                viable_count = sum(1 for r in surge_results if r.is_viable)
                print(f"    Evaluated {len(surge_results)} definitions, "
                      f"{viable_count} viable")
                surge_ds_elapsed = time.perf_counter() - surge_ds_start
                print(f"    ⏱ Surge analysis for dataset in {surge_ds_elapsed:.2f}s")

                result.surge_results.extend(surge_results)

            except Exception as e:
                error_msg = f"Surge analysis failed for {ds.path}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

    except Exception as e:
        error_msg = f"Surge Analysis stage failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def _run_visualization_stage(config: PipelineConfig, result: PipelineResult, store: DatasetStore) -> PipelineResult:
    """Execute the visualization stage.

    Uses pre-loaded and enriched datasets from the DatasetStore for surge
    frequency chart generation.
    """
    try:
        from src.visualization import (
            generate_dataset_comparison,
            generate_engagement_distributions,
            generate_sentiment_distributions,
            generate_surge_frequency,
        )

        chart_dir = os.path.join(config.output_dir, "charts")
        os.makedirs(chart_dir, exist_ok=True)

        # Engagement distribution charts
        if result.quality_reports:
            for report in result.quality_reports:
                if report.engagement_stats:
                    print(f"  Generating engagement charts for {report.dataset_name}...")
                    paths = generate_engagement_distributions(
                        report.engagement_stats, chart_dir
                    )
                    result.chart_paths.extend(paths)

                # Sentiment distribution charts
                if report.sentiment_stats:
                    print(f"  Generating sentiment charts for {report.dataset_name}...")
                    sentiment_data = {
                        "polarity_scores": report.sentiment_stats,
                        "bullish_count": 0,
                        "bearish_count": 0,
                        "neutral_count": 0,
                        "bullish_bearish_ratio": report.bullish_bearish_ratio,
                        "total_analyzed": report.record_count,
                    }
                    paths = generate_sentiment_distributions(sentiment_data, chart_dir)
                    result.chart_paths.extend(paths)

        # Surge frequency chart
        if result.surge_results:
            for ds in store:
                if ds.date_col and ds.engagement_cols and ds.sentiment_col and ds.ticker_col:
                    try:
                        from src.surge_analysis import compute_surge_labels

                        default_config = SurgeConfig(
                            engagement_percentile=0.95,
                            sentiment_std_devs=1.0,
                            time_window_hours=config.surge_window_hours,
                        )
                        surge_labels = compute_surge_labels(
                            ds.df, default_config, ds.engagement_cols,
                            ds.sentiment_col, ds.date_col, ds.ticker_col
                        )
                        surge_df = ds.df[[ds.date_col]].copy()
                        surge_df = surge_df.rename(columns={ds.date_col: "timestamp"})
                        surge_df["surge"] = surge_labels

                        print("  Generating surge frequency chart...")
                        path = generate_surge_frequency(surge_df, chart_dir)
                        result.chart_paths.append(path)
                        break  # Only generate for first viable dataset
                    except Exception as e:
                        logger.warning(f"Could not generate surge frequency chart: {e}")

        # Dataset comparison chart
        if result.datasets_discovered:
            print("  Generating dataset comparison chart...")
            path = generate_dataset_comparison(result.datasets_discovered, chart_dir)
            result.chart_paths.append(path)

        if not result.chart_paths:
            print("  No charts generated (insufficient data).")

    except Exception as e:
        error_msg = f"Visualization stage failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def _run_report_stage(config: PipelineConfig, result: PipelineResult, timing_info: dict | None = None) -> PipelineResult:
    """Execute the report generation stage."""
    try:
        from src.report_generator import generate_report

        report_path = os.path.join(config.output_dir, "eda_report.md")

        print(f"  Writing report to: {report_path}")
        generated_path = generate_report(
            discovery_results=result.datasets_discovered,
            api_assessments=result.api_assessments,
            quality_reports=result.quality_reports,
            surge_results=result.surge_results,
            chart_paths=result.chart_paths,
            output_path=report_path,
            timing_info=timing_info,
        )
        result.report_path = generated_path
        print(f"  Report generated: {generated_path}")

    except Exception as e:
        error_msg = f"Report Generation failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def _print_summary(result: PipelineResult, stage_timings: dict[str, float], total_elapsed: float) -> None:
    """Print a summary of the pipeline execution."""
    print("\n" + "=" * 60)
    print("Pipeline Execution Complete")
    print("=" * 60)
    print(f"  Datasets discovered: {len(result.datasets_discovered)}")
    print(f"  API assessments: {len(result.api_assessments)}")
    print(f"  Quality reports: {len(result.quality_reports)}")
    print(f"  Surge results: {len(result.surge_results)}")
    print(f"  Charts generated: {len(result.chart_paths)}")
    print(f"  Report: {result.report_path or 'Not generated'}")

    if result.errors:
        print(f"\n  Errors encountered: {len(result.errors)}")
        for error in result.errors:
            print(f"    - {error}")
    else:
        print("\n  No errors encountered.")

    # Timing breakdown
    print("\n  ⏱ Timing Breakdown:")
    for stage_name, elapsed in stage_timings.items():
        print(f"    {stage_name:<25} {elapsed:>8.2f}s")
    print(f"    {'─' * 35}")
    print(f"    {'TOTAL':<25} {total_elapsed:>8.2f}s")
    print("=" * 60)


# ─── Helper Functions ───────────────────────────────────────────────────────


def _load_and_enrich_datasets(config: PipelineConfig) -> DatasetStore:
    """Load all CSV files once and compute shared enrichments.

    Finds candidate CSV files, loads each one, runs column detection
    and enrichment (sentiment, ticker), and returns a populated
    DatasetStore ready for consumption by downstream stages.
    """
    store = DatasetStore()
    dataset_files = _find_dataset_files(config)

    if not dataset_files:
        logger.warning("No CSV dataset files found in search directories.")
        return store

    for filepath in dataset_files:
        try:
            df = _load_dataset(filepath)
            name = os.path.basename(filepath)

            # Detect columns
            date_col = _detect_date_column(df)
            text_col = _detect_text_column(df)
            engagement_cols = _detect_engagement_columns(df)
            sentiment_col = _detect_sentiment_column(df)
            ticker_col = _detect_ticker_column(df)

            # Compute sentiment if missing
            if not sentiment_col and text_col:
                sentiment_col = _compute_sentiment_column(df, text_col)
                if sentiment_col:
                    print(f"  [{name}] Computed sentiment from '{text_col}' column")

            enriched = EnrichedDataset(
                path=filepath,
                name=name,
                df=df,
                date_col=date_col,
                text_col=text_col,
                sentiment_col=sentiment_col,
                ticker_col=ticker_col,
                engagement_cols=engagement_cols,
            )
            store.add(enriched)
            logger.info(
                f"Enriched '{name}': date={date_col}, text={text_col}, "
                f"sentiment={sentiment_col}, ticker={ticker_col}, "
                f"engagement={engagement_cols}"
            )

        except Exception as e:
            error_msg = f"Failed to load/enrich dataset '{filepath}': {e}"
            logger.error(error_msg)
            store.load_errors.append(error_msg)

    return store


def _detect_delimiter(filepath: str, sample_size: int = 8192) -> str:
    """Detect the delimiter used in a CSV file by sniffing a sample.

    Args:
        filepath: Path to the CSV file.
        sample_size: Number of bytes to read for sniffing.

    Returns:
        The detected delimiter character. Defaults to ',' if detection fails.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            sample = f.read(sample_size)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        logger.warning(
            "Could not detect delimiter for '%s', defaulting to ','.", filepath
        )
        return ","


def _load_dataset(filepath: str) -> pd.DataFrame:
    """Load a CSV dataset with auto-detected delimiter.

    Args:
        filepath: Path to the CSV file.

    Returns:
        DataFrame loaded from the file.
    """
    sep = _detect_delimiter(filepath)
    logger.info("Loading '%s' with detected delimiter: %r", filepath, sep)
    return pd.read_csv(
        filepath, sep=sep, index_col=0, engine="python", on_bad_lines="warn"
    )


def _find_dataset_files(config: PipelineConfig) -> list[str]:
    """Find CSV dataset files in common locations, including subfolders.

    Recursively searches the project root, output directory, and 'data/'
    and 'datasets/' directories for CSV files that could be candidate datasets.

    Returns:
        List of file paths to CSV files found.
    """
    search_dirs = [
        ".",
        config.output_dir,
        "data",
        "datasets",
    ]

    csv_files: list[str] = []
    seen: set[str] = set()

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        for dirpath, _dirnames, filenames in os.walk(directory):
            for filename in filenames:
                if filename.lower().endswith(".csv"):
                    filepath = os.path.join(dirpath, filename)
                    abs_path = os.path.abspath(filepath)
                    if abs_path not in seen:
                        seen.add(abs_path)
                        csv_files.append(filepath)

    return csv_files


def _detect_date_column(df: pd.DataFrame) -> str | None:
    """Detect the most likely date/timestamp column in a DataFrame.

    Uses a three-tier strategy:
    1. Columns already typed as datetime (cheapest check).
    2. Name-based keyword matching.
    3. Dtype probe — samples object/string columns and attempts date parsing.
    """
    date_keywords = ["date", "timestamp", "created_at", "created_utc", "time", "posted_at"]

    # 1. Check for columns already typed as datetime
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    if len(datetime_cols) == 1:
        return datetime_cols[0]
    if len(datetime_cols) > 1:
        # Multiple datetime cols — prefer one with a date-related name
        for col in datetime_cols:
            if col.lower() in date_keywords or any(kw in col.lower() for kw in ["date", "time"]):
                return col
        return datetime_cols[0]

    # 2. Name-based keyword matching
    for col in df.columns:
        if col.lower() in date_keywords:
            return col
    for col in df.columns:
        if any(kw in col.lower() for kw in ["date", "time"]):
            return col

    # 3. Dtype probe — try parsing object/string columns as dates
    for col in df.select_dtypes(include=["object", "string"]).columns:
        sample = df[col].dropna().head(20)
        if len(sample) == 0:
            continue
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().sum() >= len(sample) * 0.8:
            return col

    return None


def _detect_engagement_columns(df: pd.DataFrame) -> list[str]:
    """Detect engagement metric columns in a DataFrame."""
    engagement_keywords = {
        "likes", "retweets", "comments", "upvotes", "shares",
        "favorites", "score", "num_comments", "comment_count",
        "like_count", "retweet_count", "ups", "downs",
    }
    found = []
    for col in df.columns:
        if col.lower() in engagement_keywords:
            found.append(col)
    return found


def _detect_text_column(df: pd.DataFrame) -> str | None:
    """Detect the most likely text content column in a DataFrame."""
    text_keywords = ["text", "body", "content", "title", "selftext", "comment", "message"]
    for col in df.columns:
        if col.lower() in text_keywords:
            return col
    return None


def _detect_sentiment_column(df: pd.DataFrame) -> str | None:
    """Detect the most likely sentiment column in a DataFrame."""
    sentiment_keywords = [
        "sentiment", "polarity", "sentiment_score", "compound",
        "bullish", "bearish",
    ]
    for col in df.columns:
        if col.lower() in sentiment_keywords:
            return col
    return None


def _compute_sentiment_column(df: pd.DataFrame, text_col: str) -> str | None:
    """Compute a sentiment column from text using VADER and add it to df in-place.

    Returns the name of the added column ('sentiment') on success, or None on failure.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        analyzer = SentimentIntensityAnalyzer()
    except ImportError:
        logger.warning("vaderSentiment not available. Cannot compute sentiment column.")
        return None

    if text_col not in df.columns:
        return None

    texts = df[text_col].fillna("")
    compound_scores = texts.apply(
        lambda t: analyzer.polarity_scores(str(t))["compound"]
    )
    df["sentiment"] = compound_scores
    return "sentiment"


def _detect_ticker_column(df: pd.DataFrame) -> str | None:
    """Detect the most likely stock ticker column in a DataFrame.

    If no explicit ticker column exists, attempts to extract tickers from
    text columns and adds a 'ticker' column to the DataFrame in-place.
    """
    ticker_keywords = ["ticker", "symbol", "stock", "stock_symbol"]
    for col in df.columns:
        if col.lower() in ticker_keywords:
            return col

    # No explicit ticker column found — attempt extraction from text
    try:
        from src.ticker_extraction import add_ticker_column_if_missing

        df_with_ticker = add_ticker_column_if_missing(df, ticker_col="ticker")
        # Update the original DataFrame in-place with the new column
        df["ticker"] = df_with_ticker["ticker"]

        # Check if extraction found any real tickers
        non_unknown = (df["ticker"] != "UNKNOWN").sum()
        if non_unknown > 0:
            logger.info(
                f"Extracted tickers from text for {non_unknown}/{len(df)} rows "
                f"({df['ticker'].nunique()} unique tickers)"
            )
            return "ticker"
        else:
            logger.warning("Ticker extraction found no tickers in text columns.")
            # Remove the all-UNKNOWN column — not useful for per-ticker normalization
            df.drop(columns=["ticker"], inplace=True)
            return None
    except Exception as e:
        logger.warning(f"Ticker extraction failed: {e}")
        return None


def _evaluate_eda_objectives(
    structure: dict,
    missing: dict,
    time_coverage: dict,
    engagement_stats: dict,
    sentiment_stats: dict,
    text_col: str | None,
    engagement_cols: list[str],
) -> dict[str, bool]:
    """Evaluate EDA objectives and return pass/fail for each.

    Maps to the EDA objectives defined in Requirement 3.
    """
    objectives: dict[str, bool] = {}

    # A. Dataset structure documented
    objectives["dataset_structure"] = structure.get("record_count", 0) > 0

    # B. Missing values computed
    objectives["missing_values"] = len(missing.get("missing_percentages", {})) > 0

    # C. Time coverage analyzed
    objectives["time_coverage"] = time_coverage.get("date_range", ("unknown",))[0] != "unknown"

    # D. Engagement distributions computed
    objectives["engagement_distributions"] = len(engagement_stats) > 0

    # E. Sentiment distributions available
    objectives["sentiment_distributions"] = bool(sentiment_stats) and text_col is not None

    # F. Surge definitions can be evaluated (need engagement + sentiment + time)
    objectives["surge_definitions"] = (
        len(engagement_cols) > 0
        and text_col is not None
        and time_coverage.get("date_range", ("unknown",))[0] != "unknown"
    )

    return objectives


if __name__ == "__main__":
    print("EDA Financial Discussions Pipeline")
    print("-" * 40)

    # Create default configuration
    pipeline_config = PipelineConfig()

    # Run the pipeline
    pipeline_result = run_pipeline(pipeline_config)

    # Exit with error code if there were fatal errors
    if pipeline_result.errors and not pipeline_result.report_path:
        sys.exit(1)
