# Implementation Plan: EDA Financial Discussions

## Overview

This implementation plan breaks down the EDA Financial Discussions pipeline into incremental coding tasks. The pipeline is structured as Python scripts orchestrated by a single entry point (`main.py`), producing PNG charts and a markdown report. Each task builds on previous steps, ensuring no orphaned code.

## Tasks

- [ ] 1. Set up project structure and core data models
  - [x] 1.1 Create project directory structure and configuration
    - Create `src/` directory with `__init__.py`
    - Create `tests/test_properties/`, `tests/test_unit/`, `tests/test_integration/` directories with `__init__.py` files
    - Create `output/` directory for charts and reports
    - Create `notebooks/` directory
    - Create `requirements.txt` with pinned dependencies: pandas, numpy, matplotlib, seaborn, hypothesis, pytest, textblob, vaderSentiment, kaggle, huggingface_hub, praw, jupyter, ipykernel
    - Create `PipelineConfig` and `PipelineResult` dataclasses in `src/models.py`
    - _Requirements: 7.1, 7.2, 7.6, 7.7_

  - [x] 1.2 Define all core data model interfaces
    - Implement `DatasetMetadata`, `APIAssessment`, `QualityReport`, `SurgeConfig`, `SurgeResult`, and `PipelineError` dataclasses in `src/models.py`
    - Ensure all fields match the design document specifications
    - _Requirements: 1.3, 2.1, 2.2, 3.1, 4.1_

- [ ] 2. Implement Dataset Discovery module
  - [x] 2.1 Implement Kaggle dataset scanner
    - Create `src/dataset_discovery.py`
    - Implement `scan_kaggle(search_terms: list[str]) -> list[DatasetMetadata]` that searches Kaggle for stock discussion datasets
    - Record name, source platform, record count, date range, columns, and freshness for each dataset
    - Handle network errors gracefully, logging warnings and returning empty results
    - Report absence with search criteria if no datasets found
    - _Requirements: 1.1, 1.3, 1.5, 7.5_

  - [x] 2.2 Implement HuggingFace dataset scanner
    - Implement `scan_huggingface(search_terms: list[str]) -> list[DatasetMetadata]` in `src/dataset_discovery.py`
    - Record same metadata fields as Kaggle scanner
    - Handle network errors gracefully
    - Report absence with search criteria if no datasets found
    - _Requirements: 1.2, 1.3, 1.5, 7.5_

  - [ ] 2.3 Implement dataset completeness flagging
    - Implement `flag_incomplete_datasets(datasets: list[DatasetMetadata]) -> list[DatasetMetadata]`
    - Flag datasets missing engagement metrics OR sentiment-related fields as incomplete (`is_complete = False`)
    - _Requirements: 1.4_

  - [ ]* 2.4 Write property test for dataset completeness flagging
    - **Property 1: Dataset completeness flagging**
    - Use Hypothesis to generate arbitrary column name sets and verify `is_complete` is False iff engagement OR sentiment columns are missing
    - **Validates: Requirements 1.4**

  - [ ]* 2.5 Write property test for metadata extraction completeness
    - **Property 2: Metadata extraction completeness**
    - Use Hypothesis to generate mock API responses and verify all required fields in `DatasetMetadata` are populated and non-null
    - **Validates: Requirements 1.3**

- [ ] 3. Implement API Feasibility Assessment module
  - [ ] 3.1 Implement X/Twitter API assessment
    - Create `src/api_feasibility.py`
    - Implement `assess_twitter_api() -> APIAssessment` evaluating rate limits, endpoints, cost tiers, available fields, historical access
    - Document estimated time and cost to collect 10,000 posts
    - Document paid fields and pricing tiers
    - Assess whether API supports surge label construction
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [ ] 3.2 Implement Reddit API assessment
    - Implement `assess_reddit_api() -> APIAssessment` in `src/api_feasibility.py`
    - Evaluate rate limits, endpoints, cost tiers, available fields, historical access
    - Document estimated time and cost to collect 10,000 posts
    - Document paid fields and pricing tiers
    - Assess whether API supports surge label construction
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ]* 3.3 Write property test for API cost and time estimation
    - **Property 3: API collection cost and time estimation**
    - Use Hypothesis to generate valid rate limits and cost-per-request values, verify estimated time = N / effective_rate and cost = N * cost_per_request
    - **Validates: Requirements 2.3**

  - [ ]* 3.4 Write property test for surge label feasibility assessment
    - **Property 4: Surge label feasibility assessment**
    - Use Hypothesis to generate sets of API fields, verify `supports_surge_label` is True iff fields contain engagement metric + sentiment text + timestamp
    - **Validates: Requirements 2.5**

- [ ] 4. Checkpoint - Ensure discovery and API modules work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Dataset Quality Analysis module
  - [ ] 5.1 Implement dataset structure analysis
    - Create `src/dataset_quality.py`
    - Implement `analyze_structure(df) -> dict` documenting schema, column types, record count, unique ticker count
    - _Requirements: 3.1_

  - [ ] 5.2 Implement missing value computation
    - Implement `compute_missing_values(df) -> dict[str, float]` computing per-column missing percentages
    - Flag columns with >30% missing as high-risk
    - _Requirements: 3.2_

  - [ ]* 5.3 Write property test for missing value computation
    - **Property 5: Missing value computation and high-risk flagging**
    - Use Hypothesis to generate DataFrames with known null patterns, verify percentages match actual null counts / total rows, and high-risk flag triggers iff >30%
    - **Validates: Requirements 3.2**

  - [ ] 5.4 Implement time coverage analysis
    - Implement `analyze_time_coverage(df, date_col) -> dict` analyzing date range, gaps >7 days, posting frequency
    - _Requirements: 3.3_

  - [ ]* 5.5 Write property test for temporal gap detection
    - **Property 6: Temporal gap detection**
    - Use Hypothesis to generate sorted timestamp sequences, verify all gaps >7 days are identified and date range spans min to max
    - **Validates: Requirements 3.3**

  - [ ] 5.6 Implement engagement distribution computation
    - Implement `compute_engagement_distributions(df, metric_cols) -> dict` computing mean, median, 90th/95th/99th percentiles
    - _Requirements: 3.4_

  - [ ]* 5.7 Write property test for engagement statistics correctness
    - **Property 7: Engagement statistics correctness**
    - Use Hypothesis to generate non-empty numeric arrays, verify computed statistics match mathematically correct values
    - **Validates: Requirements 3.4**

  - [ ] 5.8 Implement sentiment analysis
    - Implement `analyze_sentiment(df, text_col) -> dict` performing sentiment distribution analysis and computing bullish-to-bearish ratio
    - Implement `assess_sentiment_reliability(df, text_col) -> dict` comparing at least two sentiment methods for inter-method agreement
    - _Requirements: 3.5, 3.9_

  - [ ] 5.9 Implement stock vs. general engagement comparison
    - Implement `compare_stock_vs_general(stock_df, general_df) -> dict` comparing engagement patterns
    - _Requirements: 3.8_

  - [ ] 5.10 Implement risk cataloging
    - Implement risk discovery logic that catalogs data quality issues, biases, temporal leakage risks, and coverage gaps
    - _Requirements: 3.10_

- [ ] 6. Implement Surge Analysis module
  - [ ] 6.1 Implement per-ticker engagement normalization
    - Create `src/surge_analysis.py`
    - Implement `normalize_engagement(df, metric_cols, ticker_col) -> DataFrame` normalizing engagement relative to each ticker's historical baseline
    - _Requirements: 4.2_

  - [ ]* 6.2 Write property test for per-ticker engagement normalization
    - **Property 9: Per-ticker engagement normalization**
    - Use Hypothesis to generate multi-ticker DataFrames, verify normalization is computed independently per ticker
    - **Validates: Requirements 4.2**

  - [ ] 6.3 Implement surge label computation
    - Implement `compute_surge_labels(df, config, engagement_cols, sentiment_col, timestamp_col, ticker_col) -> Series`
    - Surge = engagement exceeds configured percentile AND sentiment shift exceeds configured std dev threshold within time window
    - Implement `check_timestamp_resolution(df, timestamp_col) -> dict` to verify 24-hour window feasibility
    - _Requirements: 4.1, 4.4_

  - [ ]* 6.4 Write property test for surge label correctness
    - **Property 8: Surge label correctness**
    - Use Hypothesis to generate posts with known engagement ranks and sentiment shifts, verify surge label is True iff both thresholds exceeded
    - **Validates: Requirements 3.6, 4.1**

  - [ ] 6.5 Implement surge definition evaluation
    - Implement `evaluate_surge_definitions(df, percentiles, std_devs, ...) -> list[SurgeResult]`
    - Evaluate at percentiles [0.90, 0.95, 0.99] combined with std devs [0.5, 1.0, 1.5]
    - Report surge percentage and class imbalance for each combination
    - Flag definitions where positive class < 2%
    - _Requirements: 3.6, 3.7, 4.3_

  - [ ]* 6.6 Write property test for class balance computation
    - **Property 10: Class balance computation and viability flagging**
    - Use Hypothesis to generate boolean arrays, verify surge percentage = count(True) / total * 100, and non-viable iff < 2%
    - **Validates: Requirements 3.7, 4.3**

- [ ] 7. Checkpoint - Ensure quality and surge modules work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Visualization Engine
  - [ ] 8.1 Implement chart generation functions
    - Create `src/visualization.py`
    - Implement `generate_engagement_distributions(stats, output_dir) -> list[str]`
    - Implement `generate_sentiment_distributions(stats, output_dir) -> list[str]`
    - Implement `generate_surge_frequency(surge_data, output_dir) -> str`
    - Implement `generate_dataset_comparison(datasets, output_dir) -> str`
    - All charts include descriptive titles, axis labels, and legends
    - Save as PNG files, log output file paths to stdout
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 8.2 Create interactive exploration notebook
    - Create `notebooks/exploration.ipynb`
    - Include sections: Dataset Loading, Structure Analysis, Missing Values, Engagement Distributions, Sentiment Analysis, Surge Threshold Exploration
    - Import analysis functions from `src/` modules (dataset_quality, surge_analysis, visualization)
    - Include markdown cells explaining each analysis step
    - Include example code cells demonstrating each src/ function
    - _Requirements: 7.6_

- [ ] 9. Implement Report Generator
  - [ ] 9.1 Implement markdown report generation
    - Create `src/report_generator.py`
    - Implement `generate_report(discovery_results, api_assessments, quality_reports, surge_results, chart_paths, output_path) -> str`
    - Report contains: executive summary, dataset discovery results, API feasibility findings, EDA statistics, surge analysis results, final recommendation
    - Include inline references to chart files using relative paths
    - _Requirements: 6.1, 6.2_

  - [ ] 9.2 Implement recommendation logic
    - Implement `make_recommendation(quality_reports, api_assessments, surge_results) -> dict`
    - Recommend best data path (public dataset vs. API collection) with justification
    - Rank multiple viable options with trade-offs
    - Document gaps and next steps if no suitable path exists
    - _Requirements: 6.3, 6.4, 6.5_

  - [ ] 9.3 Implement dataset suitability decision logic
    - Implement logic that evaluates EDA objective pass/fail results
    - Produce go/no-go recommendation with justification
    - Flag dataset as unsuitable if 3+ objectives fail
    - _Requirements: 3.11, 3.12_

  - [ ]* 9.4 Write property test for dataset suitability decision
    - **Property 11: Dataset suitability decision**
    - Use Hypothesis to generate sets of EDA objective results (pass/fail), verify unsuitable recommendation iff 3+ objectives fail
    - **Validates: Requirements 3.11, 3.12**

  - [ ]* 9.5 Write property test for report section completeness
    - **Property 12: Report section completeness**
    - Use Hypothesis to generate pipeline results with varying chart paths, verify report contains all required sections and references every chart file
    - **Validates: Requirements 6.1, 6.2**

- [ ] 10. Implement Pipeline Orchestration
  - [ ] 10.1 Implement main entry point
    - Create `main.py` at project root
    - Implement `run_pipeline(config: PipelineConfig) -> PipelineResult` orchestrating all stages in sequence
    - Print progress messages indicating current analysis step
    - Handle stage failures gracefully: log errors, continue with remaining stages
    - Produce partial report if some stages fail
    - Wire all components together: discovery → quality → surge → visualization → report
    - _Requirements: 7.1, 7.3, 7.4, 7.5_

  - [ ] 10.2 Create shared test fixtures
    - Create `tests/conftest.py` with shared fixtures and Hypothesis generators
    - Include sample DataFrames, mock API responses, and test configurations
    - _Requirements: 7.1_

- [ ] 11. Final checkpoint - Ensure full pipeline works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The pipeline uses graceful degradation: individual stage failures don't halt the entire pipeline
- All core pipeline code is Python scripts per requirement 7.1
- The exploration notebook (`notebooks/exploration.ipynb`) provides an interactive interface for data scientists while the pipeline scripts remain the reproducible execution path

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "3.1", "3.2"] },
    { "id": 3, "tasks": ["2.3", "2.5", "3.3", "3.4"] },
    { "id": 4, "tasks": ["2.4"] },
    { "id": 5, "tasks": ["5.1", "5.2", "5.4", "5.6", "5.8", "5.9", "5.10"] },
    { "id": 6, "tasks": ["5.3", "5.5", "5.7"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["6.2", "6.3"] },
    { "id": 9, "tasks": ["6.4", "6.5"] },
    { "id": 10, "tasks": ["6.6"] },
    { "id": 11, "tasks": ["8.1", "8.2", "9.1", "9.2", "9.3"] },
    { "id": 12, "tasks": ["9.4", "9.5"] },
    { "id": 13, "tasks": ["10.1", "10.2"] }
  ]
}
```
