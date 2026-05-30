"""Shared test fixtures and Hypothesis strategies for the EDA Financial Discussions pipeline.

Provides reusable fixtures for:
- Sample DataFrames with stock discussion data (engagement metrics, timestamps, sentiment, tickers)
- Mock API responses (Kaggle, HuggingFace)
- Test configurations (PipelineConfig, SurgeConfig)
- Hypothesis strategies for generating test data models

These fixtures are available to all test files in test_properties/, test_unit/, and test_integration/.
"""

import numpy as np
import pandas as pd
import pytest
from hypothesis import strategies as st

from src.models import (
    APIAssessment,
    DatasetMetadata,
    PipelineConfig,
    PipelineError,
    PipelineResult,
    QualityReport,
    SurgeConfig,
    SurgeResult,
)


# ---------------------------------------------------------------------------
# Hypothesis Strategies for Data Models
# ---------------------------------------------------------------------------


@st.composite
def dataset_metadata_strategy(draw):
    """Hypothesis strategy for generating DatasetMetadata instances."""
    name = draw(st.text(min_size=3, max_size=30, alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="-_/"
    )))
    source_platform = draw(st.sampled_from(["kaggle", "huggingface"]))
    record_count = draw(st.integers(min_value=0, max_value=10_000_000))

    start_year = draw(st.integers(min_value=2018, max_value=2023))
    end_year = draw(st.integers(min_value=start_year, max_value=2024))
    date_range = (f"{start_year}-01-01", f"{end_year}-12-31")

    engagement_cols = draw(st.lists(
        st.sampled_from(["likes", "retweets", "comments", "upvotes", "shares", "score"]),
        min_size=0, max_size=3, unique=True,
    ))
    sentiment_cols = draw(st.lists(
        st.sampled_from(["sentiment", "polarity", "bullish", "bearish"]),
        min_size=0, max_size=2, unique=True,
    ))
    other_cols = draw(st.lists(
        st.sampled_from(["text", "timestamp", "ticker", "author", "title", "url"]),
        min_size=1, max_size=4, unique=True,
    ))
    columns = engagement_cols + sentiment_cols + other_cols

    freshness_days = draw(st.integers(min_value=0, max_value=1000))
    has_engagement = len(engagement_cols) > 0
    has_sentiment = len(sentiment_cols) > 0
    is_complete = has_engagement and has_sentiment

    return DatasetMetadata(
        name=name,
        source_platform=source_platform,
        record_count=record_count,
        download_count=0,
        date_range=date_range,
        columns=columns,
        freshness_days=freshness_days,
        has_engagement_metrics=has_engagement,
        has_sentiment_fields=has_sentiment,
        is_complete=is_complete,
    )


@st.composite
def api_assessment_strategy(draw):
    """Hypothesis strategy for generating APIAssessment instances."""
    platform = draw(st.sampled_from(["twitter", "reddit"]))
    rate_limits = {
        "requests_per_minute": draw(st.integers(min_value=1, max_value=1000)),
        "posts_per_request": draw(st.integers(min_value=1, max_value=100)),
    }
    endpoints = draw(st.lists(
        st.text(min_size=5, max_size=40, alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="/:_{}"
        )),
        min_size=1, max_size=5,
    ))

    cost_tiers = [
        {"tier": "Free", "cost_usd_monthly": 0},
        {"tier": "Basic", "cost_usd_monthly": draw(st.integers(min_value=10, max_value=500))},
    ]

    engagement_fields = draw(st.lists(
        st.sampled_from(["likes", "retweets", "score", "ups", "num_comments"]),
        min_size=0, max_size=3, unique=True,
    ))
    text_fields = draw(st.lists(
        st.sampled_from(["text", "body", "content", "title", "selftext"]),
        min_size=0, max_size=2, unique=True,
    ))
    timestamp_fields = draw(st.lists(
        st.sampled_from(["created_at", "timestamp", "created_utc"]),
        min_size=0, max_size=1, unique=True,
    ))
    available_fields = engagement_fields + text_fields + timestamp_fields

    historical_access = draw(st.booleans())
    estimated_time = draw(st.floats(min_value=0.01, max_value=1000.0))
    estimated_cost = draw(st.floats(min_value=0.0, max_value=50000.0))

    has_engagement = len(engagement_fields) > 0
    has_text = len(text_fields) > 0
    has_timestamp = len(timestamp_fields) > 0
    supports_surge = has_engagement and has_text and has_timestamp

    paid_fields = draw(st.lists(
        st.fixed_dictionaries({
            "field": st.sampled_from(["impression_count", "full_archive", "streaming"]),
            "tier": st.sampled_from(["Basic", "Pro", "Enterprise"]),
        }),
        min_size=0, max_size=3,
    ))

    return APIAssessment(
        platform=platform,
        rate_limits=rate_limits,
        endpoints=endpoints,
        cost_tiers=cost_tiers,
        available_fields=available_fields,
        historical_access=historical_access,
        estimated_collection_time_hours=estimated_time,
        estimated_cost_usd=estimated_cost,
        supports_surge_label=supports_surge,
        paid_fields=paid_fields,
    )


@st.composite
def quality_report_strategy(draw):
    """Hypothesis strategy for generating QualityReport instances."""
    dataset_name = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="-_"
    )))
    columns = draw(st.lists(
        st.sampled_from(["likes", "comments", "sentiment", "ticker", "text", "timestamp"]),
        min_size=2, max_size=6, unique=True,
    ))
    schema = {col: draw(st.sampled_from(["int64", "float64", "object", "datetime64"])) for col in columns}

    record_count = draw(st.integers(min_value=100, max_value=1_000_000))
    ticker_count = draw(st.integers(min_value=1, max_value=500))

    missing_values = {col: draw(st.floats(min_value=0.0, max_value=100.0)) for col in columns}
    high_risk_columns = [col for col, pct in missing_values.items() if pct > 30.0]

    start_year = draw(st.integers(min_value=2019, max_value=2022))
    date_range = (f"{start_year}-01-01", f"{start_year + 2}-12-31")
    temporal_gaps = draw(st.lists(
        st.tuples(
            st.just(f"{start_year}-06-01"),
            st.just(f"{start_year}-06-15"),
        ),
        min_size=0, max_size=3,
    ))

    posting_frequency = {"daily": draw(st.floats(min_value=0.1, max_value=1000.0))}
    engagement_stats = {
        "likes": {
            "mean": draw(st.floats(min_value=0.0, max_value=10000.0)),
            "median": draw(st.floats(min_value=0.0, max_value=5000.0)),
            "p90": draw(st.floats(min_value=0.0, max_value=20000.0)),
            "p95": draw(st.floats(min_value=0.0, max_value=30000.0)),
            "p99": draw(st.floats(min_value=0.0, max_value=50000.0)),
        }
    }
    sentiment_stats = {
        "mean_polarity": draw(st.floats(min_value=-1.0, max_value=1.0)),
        "std_polarity": draw(st.floats(min_value=0.0, max_value=1.0)),
    }
    bullish_bearish_ratio = draw(st.floats(min_value=0.1, max_value=10.0))

    num_objectives = draw(st.integers(min_value=0, max_value=6))
    all_objectives = [
        "prediction_target", "surge_definition", "positive_class",
        "stock_vs_general", "sentiment_reliability", "feature_availability",
    ]
    failing = draw(st.lists(
        st.sampled_from(all_objectives), min_size=0, max_size=num_objectives, unique=True,
    ))
    eda_answered = {obj: (obj not in failing) for obj in all_objectives}
    recommendation = "unsuitable" if len(failing) >= 3 else "suitable"

    return QualityReport(
        dataset_name=dataset_name,
        schema=schema,
        record_count=record_count,
        ticker_count=ticker_count,
        missing_values=missing_values,
        high_risk_columns=high_risk_columns,
        date_range=date_range,
        temporal_gaps=temporal_gaps,
        posting_frequency=posting_frequency,
        engagement_stats=engagement_stats,
        sentiment_stats=sentiment_stats,
        bullish_bearish_ratio=bullish_bearish_ratio,
        risks=draw(st.lists(st.text(min_size=5, max_size=50), min_size=0, max_size=5)),
        eda_questions_answered=eda_answered,
        failing_objectives=failing,
        recommendation=recommendation,
    )


@st.composite
def surge_result_strategy(draw):
    """Hypothesis strategy for generating SurgeResult instances."""
    percentile = draw(st.sampled_from([0.90, 0.95, 0.99]))
    std_devs = draw(st.sampled_from([0.5, 1.0, 1.5]))
    config = SurgeConfig(
        engagement_percentile=percentile,
        sentiment_std_devs=std_devs,
        time_window_hours=24,
    )

    total_posts = draw(st.integers(min_value=100, max_value=100_000))
    surge_count = draw(st.integers(min_value=0, max_value=total_posts))
    surge_percentage = (surge_count / total_posts) * 100.0 if total_posts > 0 else 0.0
    is_viable = surge_percentage >= 2.0
    class_imbalance = (
        (total_posts - surge_count) / surge_count if surge_count > 0 else float("inf")
    )

    return SurgeResult(
        config=config,
        surge_count=surge_count,
        total_posts=total_posts,
        surge_percentage=surge_percentage,
        class_imbalance_ratio=class_imbalance,
        is_viable=is_viable,
        timestamp_sufficient=draw(st.booleans()),
    )


# ---------------------------------------------------------------------------
# Pytest Fixtures - Sample DataFrames
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_stock_discussion_df():
    """Sample DataFrame with stock discussion data including engagement metrics,
    timestamps, sentiment, and tickers. Contains known patterns for testing."""
    np.random.seed(42)
    n = 100
    tickers = np.random.choice(["AAPL", "TSLA", "GOOG", "AMZN"], size=n)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="1h")

    likes = np.random.randint(1, 200, size=n)
    retweets = np.random.randint(0, 50, size=n)
    comments = np.random.randint(0, 30, size=n)
    sentiment = np.random.normal(0.0, 0.5, size=n)

    # Inject known surge patterns at specific indices
    surge_indices = [10, 30, 50, 70, 90]
    for idx in surge_indices:
        likes[idx] = 1000
        retweets[idx] = 200
        comments[idx] = 100
        sentiment[idx] = 2.5

    return pd.DataFrame({
        "ticker": tickers,
        "timestamp": timestamps,
        "likes": likes,
        "retweets": retweets,
        "comments": comments,
        "sentiment": sentiment,
        "text": [f"Stock discussion post {i} about {tickers[i]}" for i in range(n)],
    })


@pytest.fixture
def sample_df_with_missing_values():
    """Sample DataFrame with known missing value patterns for quality testing."""
    n = 50
    data = {
        "ticker": ["AAPL"] * n,
        "likes": [float(i) if i % 3 != 0 else None for i in range(n)],  # ~33% missing
        "comments": [float(i) for i in range(n)],  # 0% missing
        "sentiment": [0.5 if i % 5 != 0 else None for i in range(n)],  # 20% missing
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1D"),
    }
    return pd.DataFrame(data)



@pytest.fixture
def sample_df_with_temporal_gaps():
    """Sample DataFrame with known temporal gaps for time coverage testing."""
    # Create dates with intentional gaps > 7 days
    dates = (
        pd.date_range("2024-01-01", periods=10, freq="1D").tolist()
        + pd.date_range("2024-01-20", periods=10, freq="1D").tolist()  # 9-day gap
        + pd.date_range("2024-03-01", periods=10, freq="1D").tolist()  # 31-day gap
    )
    n = len(dates)
    return pd.DataFrame({
        "ticker": ["AAPL"] * n,
        "timestamp": dates,
        "likes": np.random.randint(1, 100, size=n),
        "sentiment": np.random.normal(0.0, 0.3, size=n),
    })


@pytest.fixture
def sample_multi_ticker_df():
    """Sample DataFrame with multiple tickers for normalization testing.
    Each ticker has distinct engagement distributions."""
    rows = []
    np.random.seed(123)
    for ticker, base_engagement in [("AAPL", 50), ("TSLA", 200), ("GOOG", 30)]:
        for i in range(30):
            rows.append({
                "ticker": ticker,
                "likes": base_engagement + np.random.randint(-10, 50),
                "comments": int(base_engagement * 0.3 + np.random.randint(0, 10)),
                "sentiment": np.random.normal(0.0, 0.4),
                "timestamp": pd.Timestamp("2024-01-01") + pd.Timedelta(hours=i),
            })
    return pd.DataFrame(rows)



# ---------------------------------------------------------------------------
# Pytest Fixtures - Mock API Responses
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_kaggle_search_results():
    """Mock Kaggle API search results for testing dataset discovery."""
    class MockKaggleDataset:
        def __init__(self, ref, title, download_count, last_updated):
            self.ref = ref
            self.title = title
            self.downloadCount = download_count
            self.lastUpdated = last_updated

    return [
        MockKaggleDataset(
            ref="user1/stock-twitter-sentiment",
            title="Stock Twitter Sentiment Dataset",
            download_count=50000,
            last_updated="2024-06-15T00:00:00Z",
        ),
        MockKaggleDataset(
            ref="user2/reddit-wallstreetbets",
            title="Reddit WallStreetBets Posts with Engagement",
            download_count=120000,
            last_updated="2024-03-01T00:00:00Z",
        ),
        MockKaggleDataset(
            ref="user3/financial-news-sentiment",
            title="Financial News Sentiment Analysis",
            download_count=30000,
            last_updated="2023-11-20T00:00:00Z",
        ),
    ]



@pytest.fixture
def mock_huggingface_search_results():
    """Mock HuggingFace API search results for testing dataset discovery."""
    class MockHFDataset:
        def __init__(self, dataset_id, downloads, last_modified, tags):
            self.id = dataset_id
            self.downloads = downloads
            self.lastModified = last_modified
            self.last_modified = last_modified
            self.tags = tags

    return [
        MockHFDataset(
            dataset_id="finance-org/stock-tweets-sentiment",
            downloads=25000,
            last_modified="2024-05-10T00:00:00Z",
            tags=["finance", "sentiment", "twitter"],
        ),
        MockHFDataset(
            dataset_id="nlp-lab/reddit-finance-discussions",
            downloads=8000,
            last_modified="2024-07-01T00:00:00Z",
            tags=["reddit", "finance", "engagement"],
        ),
    ]


# ---------------------------------------------------------------------------
# Pytest Fixtures - Test Configurations
# ---------------------------------------------------------------------------


@pytest.fixture
def default_pipeline_config():
    """Default PipelineConfig for testing."""
    return PipelineConfig()



@pytest.fixture
def custom_pipeline_config(tmp_path):
    """PipelineConfig with custom output directory for isolated test runs."""
    return PipelineConfig(
        output_dir=str(tmp_path / "test_output"),
        chart_format="png",
        kaggle_search_terms=["stock sentiment test"],
        huggingface_search_terms=["financial tweets test"],
        surge_percentiles=[0.90, 0.95],
        surge_std_devs=[0.5, 1.0],
        surge_window_hours=24,
        min_positive_class_pct=0.02,
    )


@pytest.fixture
def default_surge_config():
    """Default SurgeConfig for testing."""
    return SurgeConfig(
        engagement_percentile=0.95,
        sentiment_std_devs=1.0,
        time_window_hours=24,
    )


@pytest.fixture
def lenient_surge_config():
    """Lenient SurgeConfig that produces more surge labels."""
    return SurgeConfig(
        engagement_percentile=0.80,
        sentiment_std_devs=0.5,
        time_window_hours=24,
    )


@pytest.fixture
def strict_surge_config():
    """Strict SurgeConfig that produces fewer surge labels."""
    return SurgeConfig(
        engagement_percentile=0.99,
        sentiment_std_devs=1.5,
        time_window_hours=24,
    )



# ---------------------------------------------------------------------------
# Pytest Fixtures - Sample Quality and Surge Results
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_quality_report():
    """A sample QualityReport for testing report generation and decisions."""
    return QualityReport(
        dataset_name="stock-twitter-sentiment",
        schema={"likes": "int64", "comments": "int64", "sentiment": "float64",
                "ticker": "object", "timestamp": "datetime64"},
        record_count=50000,
        ticker_count=150,
        missing_values={"likes": 2.5, "comments": 5.0, "sentiment": 12.0,
                        "ticker": 0.0, "timestamp": 0.5},
        high_risk_columns=[],
        date_range=("2022-01-01", "2024-06-30"),
        temporal_gaps=[("2023-03-15", "2023-03-25")],
        posting_frequency={"daily": 55.2},
        engagement_stats={
            "likes": {"mean": 45.3, "median": 12.0, "p90": 120.0, "p95": 250.0, "p99": 800.0},
            "comments": {"mean": 8.1, "median": 3.0, "p90": 20.0, "p95": 35.0, "p99": 80.0},
        },
        sentiment_stats={"mean_polarity": 0.12, "std_polarity": 0.45},
        bullish_bearish_ratio=1.8,
        sentiment_reliability={"vader_textblob_agreement": 0.72},
        risks=["Heavy right-skew in engagement", "Possible bot activity in high-engagement posts"],
        eda_questions_answered={
            "prediction_target": True,
            "surge_definition": True,
            "positive_class": True,
            "stock_vs_general": True,
            "sentiment_reliability": True,
            "feature_availability": True,
        },
        failing_objectives=[],
        recommendation="suitable",
    )



@pytest.fixture
def sample_unsuitable_quality_report():
    """A QualityReport for a dataset that fails 3+ objectives (unsuitable)."""
    return QualityReport(
        dataset_name="poor-dataset",
        schema={"text": "object", "date": "object"},
        record_count=500,
        ticker_count=5,
        missing_values={"text": 45.0, "date": 60.0},
        high_risk_columns=["text", "date"],
        date_range=("2023-01-01", "2023-02-28"),
        temporal_gaps=[("2023-01-15", "2023-02-01")],
        posting_frequency={"daily": 8.9},
        engagement_stats={},
        sentiment_stats={"mean_polarity": 0.0, "std_polarity": 0.1},
        bullish_bearish_ratio=1.0,
        risks=["No engagement metrics", "Insufficient time coverage",
               "Too few records for modeling"],
        eda_questions_answered={
            "prediction_target": False,
            "surge_definition": False,
            "positive_class": False,
            "stock_vs_general": True,
            "sentiment_reliability": False,
            "feature_availability": True,
        },
        failing_objectives=["prediction_target", "surge_definition",
                            "positive_class", "sentiment_reliability"],
        recommendation="unsuitable",
    )


@pytest.fixture
def sample_surge_results():
    """Sample list of SurgeResult objects covering viable and non-viable definitions."""
    return [
        SurgeResult(
            config=SurgeConfig(engagement_percentile=0.90, sentiment_std_devs=0.5, time_window_hours=24),
            surge_count=150, total_posts=5000, surge_percentage=3.0,
            class_imbalance_ratio=32.33, is_viable=True,
        ),
        SurgeResult(
            config=SurgeConfig(engagement_percentile=0.95, sentiment_std_devs=1.0, time_window_hours=24),
            surge_count=80, total_posts=5000, surge_percentage=1.6,
            class_imbalance_ratio=61.5, is_viable=False,
        ),
        SurgeResult(
            config=SurgeConfig(engagement_percentile=0.99, sentiment_std_devs=1.5, time_window_hours=24),
            surge_count=12, total_posts=5000, surge_percentage=0.24,
            class_imbalance_ratio=415.67, is_viable=False,
        ),
    ]



@pytest.fixture
def sample_dataset_metadata_list():
    """Sample list of DatasetMetadata for testing discovery and report generation."""
    return [
        DatasetMetadata(
            name="user1/stock-twitter-sentiment",
            source_platform="kaggle",
            record_count=50000,
            download_count=0,
            date_range=("2022-01-01", "2024-06-30"),
            columns=["text", "likes", "retweets", "sentiment", "ticker", "timestamp"],
            freshness_days=30,
            has_engagement_metrics=True,
            has_sentiment_fields=True,
            is_complete=True,
        ),
        DatasetMetadata(
            name="finance-org/reddit-wsb",
            source_platform="huggingface",
            record_count=120000,
            download_count=0,
            date_range=("2021-01-01", "2024-03-15"),
            columns=["title", "body", "score", "num_comments", "created_utc"],
            freshness_days=90,
            has_engagement_metrics=True,
            has_sentiment_fields=False,
            is_complete=False,
        ),
        DatasetMetadata(
            name="user3/financial-news",
            source_platform="kaggle",
            record_count=10000,
            download_count=0,
            date_range=("2023-06-01", "2024-01-01"),
            columns=["headline", "sentiment", "polarity"],
            freshness_days=180,
            has_engagement_metrics=False,
            has_sentiment_fields=True,
            is_complete=False,
        ),
    ]



@pytest.fixture
def sample_api_assessments():
    """Sample list of APIAssessment objects for testing report generation."""
    return [
        APIAssessment(
            platform="twitter",
            rate_limits={"basic_tier": {"requests_per_15min": 60, "posts_per_request": 100}},
            endpoints=["GET /2/tweets/search/recent", "GET /2/tweets/:id"],
            cost_tiers=[
                {"tier": "Free", "cost_usd_monthly": 0, "tweet_cap": 1500},
                {"tier": "Basic", "cost_usd_monthly": 100, "tweet_cap": 10000},
            ],
            available_fields=["text", "created_at", "like_count", "retweet_count"],
            historical_access=False,
            estimated_collection_time_hours=0.42,
            estimated_cost_usd=100.0,
            supports_surge_label=True,
            paid_fields=[{"field": "impression_count", "tier": "Basic ($100/month)"}],
        ),
        APIAssessment(
            platform="reddit",
            rate_limits={"oauth_tier": {"requests_per_minute": 100, "posts_per_request": 100}},
            endpoints=["GET /r/{subreddit}/search", "GET /r/{subreddit}/new"],
            cost_tiers=[
                {"tier": "Free (non-commercial)", "cost_usd_monthly": 0, "rate_limit": "100 req/min"},
            ],
            available_fields=["title", "selftext", "body", "created_utc", "score", "num_comments"],
            historical_access=True,
            estimated_collection_time_hours=0.017,
            estimated_cost_usd=0.0,
            supports_surge_label=True,
            paid_fields=[{"field": "full historical archive", "tier": "Commercial"}],
        ),
    ]



@pytest.fixture
def sample_chart_paths(tmp_path):
    """Sample chart file paths for testing report generation.
    Creates actual empty PNG files so path validation works."""
    chart_dir = tmp_path / "output"
    chart_dir.mkdir(exist_ok=True)

    paths = [
        str(chart_dir / "engagement_distributions.png"),
        str(chart_dir / "sentiment_distributions.png"),
        str(chart_dir / "surge_frequency.png"),
        str(chart_dir / "dataset_comparison.png"),
    ]
    # Create empty files so they exist on disk
    for path in paths:
        open(path, "w").close()

    return paths


@pytest.fixture
def sample_pipeline_result(
    sample_dataset_metadata_list,
    sample_api_assessments,
    sample_quality_report,
    sample_surge_results,
):
    """A complete PipelineResult for testing end-to-end report generation."""
    return PipelineResult(
        datasets_discovered=sample_dataset_metadata_list,
        api_assessments=sample_api_assessments,
        quality_reports=[sample_quality_report],
        surge_results=sample_surge_results,
        chart_paths=["output/engagement_distributions.png", "output/sentiment_distributions.png"],
        report_path="output/eda_report.md",
        errors=[],
    )
