# Plan: Convert `src/` Python Scripts to a Portable Jupyter Notebook

## Goal

Create a **self-contained, portable notebook** that can be dropped into any project without depending on this repo's `src/` package. All logic lives directly in notebook cells.

---

## Feasibility

**Fully feasible.** The `src/` modules are:

- Pure Python functions with standard library + common data science deps (pandas, numpy, matplotlib, seaborn, textblob, vaderSentiment)
- No compiled extensions, no project-specific C bindings
- No shared state or singletons — each function takes explicit inputs and returns outputs
- Well-documented with type hints, easy to understand in isolation

---

## Portability Requirements

| Requirement | How It's Addressed |
|-------------|-------------------|
| No imports from `src/` | All function code copied directly into notebook cells |
| No path manipulation (`sys.path` hacks) | Not needed — everything is inline |
| Dependencies clearly stated | First cell lists `pip install` command for all required packages |
| No hardcoded file paths | Uses relative paths + user-configurable variables in a config cell |
| Dataset-agnostic | Functions work on any DataFrame with the right column types; config cell defines column mappings |
| Works outside this repo | Notebook is a single `.ipynb` file with zero external references |

---

## Notebook Structure

### `notebooks/eda_pipeline_portable.ipynb`

| # | Cell Type | Section | Content |
|---|-----------|---------|---------|
| 1 | Markdown | Title | Notebook title, description, prerequisites |
| 2 | Code | **Setup & Dependencies** | `pip install` command (commented), import statements |
| 3 | Code | **Configuration** | User-editable variables: data paths, column names, thresholds |
| 4 | Markdown | Section divider | --- |
| 5 | Markdown | **1. Data Loading** | Explanation |
| 6 | Code | | Load CSV/parquet, auto-detect delimiter, show shape & dtypes |
| 7 | Code | | Preview first rows, basic info |
| 8 | Markdown | Section divider | --- |
| 9 | Markdown | **2. Ticker Extraction** | Explanation |
| 10 | Code | | Define `KNOWN_TICKERS`, regex patterns, extraction functions |
| 11 | Code | | Apply ticker extraction, show distribution |
| 12 | Markdown | Section divider | --- |
| 13 | Markdown | **3. Data Quality Analysis** | Explanation |
| 14 | Code | | Define `analyze_structure()`, `compute_missing_values()` |
| 15 | Code | | Run structure analysis, display results |
| 16 | Code | | Missing value heatmap |
| 17 | Code | | Define `analyze_time_coverage()` |
| 18 | Code | | Run temporal analysis, show gaps |
| 19 | Code | | Define `compute_engagement_distributions()` |
| 20 | Code | | Run engagement stats, display percentile table |
| 21 | Code | | Define `analyze_sentiment()`, `assess_sentiment_reliability()` |
| 22 | Code | | Run sentiment analysis, show polarity breakdown |
| 23 | Code | | Define `catalog_risks()` |
| 24 | Code | | Run risk assessment, display findings |
| 25 | Markdown | Section divider | --- |
| 26 | Markdown | **4. Surge / Anomaly Detection** | Explanation |
| 27 | Code | | Define `normalize_engagement()`, `check_timestamp_resolution()` |
| 28 | Code | | Define `compute_surge_labels()`, `evaluate_surge_definitions()` |
| 29 | Code | | Run surge analysis across threshold grid |
| 30 | Code | | Display viability table, class imbalance metrics |
| 31 | Markdown | Section divider | --- |
| 32 | Markdown | **5. Visualization** | Explanation |
| 33 | Code | | Engagement distribution plots (inline) |
| 34 | Code | | Sentiment distribution plots (inline) |
| 35 | Code | | Surge frequency chart |
| 36 | Code | | Time series / posting frequency chart |
| 37 | Markdown | Section divider | --- |
| 38 | Markdown | **6. Dataset Comparison** (optional) | Explanation |
| 39 | Code | | Side-by-side comparison if multiple datasets loaded |
| 40 | Markdown | Section divider | --- |
| 41 | Markdown | **7. Summary & Recommendation** | Explanation |
| 42 | Code | | Scoring logic, suitability recommendation |
| 43 | Code | | Print final summary report |
| 44 | Markdown | Conclusion | Next steps, export notes |

---

## Portability Design Decisions

### 1. Inline All Code (No External Imports from src/)

Every function from the `src/` modules will be defined directly in notebook cells. This makes the notebook a single distributable file.

Functions will be organized in **"utility cells"** at the start of each section, clearly marked with comments like:

```python
# ─── Utility Functions (from dataset_quality module) ───────────────────────
```

### 2. Configuration Cell for Adaptability

A single config cell at the top lets users adapt the notebook to their own data:

```python
# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these to match your dataset
# ══════════════════════════════════════════════════════════════════════════════

DATA_PATH = "data/your_dataset.csv"        # Path to your CSV/parquet file
DATE_COL = None                             # Date column name (None = auto-detect)
TEXT_COL = None                             # Text column name (None = auto-detect)
TICKER_COL = None                           # Ticker column name (None = extract from text)
SENTIMENT_COL = None                        # Sentiment column (None = compute via VADER)
ENGAGEMENT_COLS = None                      # List of engagement columns (None = auto-detect)

# Surge detection thresholds
SURGE_PERCENTILES = [0.90, 0.95, 0.99]
SURGE_STD_DEVS = [0.5, 1.0, 1.5]
SURGE_WINDOW_HOURS = 24
MIN_POSITIVE_CLASS_PCT = 0.02

# Output
OUTPUT_DIR = "output"
CHART_FORMAT = "png"
```

### 3. Auto-Detection with Override

All column-detection logic (date, text, sentiment, engagement) is included inline. Users can either:
- Set `None` in config → auto-detection kicks in
- Provide explicit column names → skips detection

### 4. Minimal Dependencies

Only widely-available packages are required:

```
pandas
numpy
matplotlib
seaborn
textblob
vaderSentiment
```

No `kaggle`, `huggingface_hub`, or `praw` needed (those are for dataset discovery/collection, not analysis).

### 5. No API Calls

The dataset discovery (`dataset_discovery.py`) and API feasibility (`api_feasibility.py`) modules involve external API calls that require credentials. These are **excluded** from the portable notebook since:
- They require API keys (Kaggle, Reddit, Twitter)
- They're data collection, not analysis
- The portable notebook assumes the user already has their data

If needed, these can be added as an optional appendix section.

---

## Module-to-Notebook Mapping

| `src/` Module | Portable Notebook Section | Notes |
|---------------|--------------------------|-------|
| `models.py` | Config cell (dataclasses replaced with dicts/namedtuples) | Simplified — no need for full pipeline dataclasses |
| `dataset_discovery.py` | **Excluded** | Requires API keys, not portable |
| `api_feasibility.py` | **Excluded** | Requires API keys, not portable |
| `ticker_extraction.py` | Section 2 | Fully portable, pure Python + regex |
| `dataset_quality.py` | Section 3 | Core of the notebook |
| `surge_analysis.py` | Section 4 | Fully portable |
| `visualization.py` | Section 5 | Adapted for inline display (`plt.show()`) |
| `report_generator.py` | Section 7 (simplified) | Scoring + recommendation only, no file I/O |
| `main.py` | Config cell + loading cell | Loader helpers (delimiter detection, column detection) |

---

## Adaptations for Inline Notebook Use

| Original Pattern | Notebook Adaptation |
|-----------------|---------------------|
| `savefig(path)` then close | `plt.show()` inline, optional `savefig()` behind a flag |
| `PipelineConfig` dataclass | Simple variables in config cell |
| `PipelineResult` accumulator | Print/display results as they're computed |
| File-based report generation | Print markdown summary in final cell |
| Multi-dataset iteration | Loop with clear per-dataset headings |
| Error collection in lists | `try/except` with inline warnings |

---

## Execution Steps

1. **Create** `notebooks/eda_pipeline_portable.ipynb`
2. **Write setup cell** — pip install comment, all imports
3. **Write config cell** — user-editable variables with sensible defaults
4. **Write data loading cells** — include `_detect_delimiter()`, `_load_dataset()`, column detection helpers from `main.py`
5. **Write ticker extraction cells** — copy `KNOWN_TICKERS`, `extract_tickers_from_text()`, `add_ticker_column_if_missing()` from `ticker_extraction.py`
6. **Write data quality cells** — copy all functions from `dataset_quality.py`, add display formatting
7. **Write surge analysis cells** — copy from `surge_analysis.py`, add result tables
8. **Write visualization cells** — adapt `visualization.py` for inline display
9. **Write summary/recommendation cells** — simplified scoring from `report_generator.py`
10. **Add markdown narrative** — explain each section, what to look for, how to interpret
11. **Test** with sample data to verify it runs end-to-end in isolation
12. **Verify portability** — copy notebook to a fresh directory, install deps, confirm it works

---

## What the User Needs to Provide (in Another Project)

1. A CSV or parquet file with social media discussion data
2. Python 3.10+ environment
3. Install: `pip install pandas numpy matplotlib seaborn textblob vaderSentiment`
4. Edit the config cell to point to their data file

That's it. No cloning this repo, no package installation, no path manipulation.
