"""API feasibility assessment module for the EDA Financial Discussions pipeline.

This module evaluates the feasibility of collecting stock discussion data
via X/Twitter and Reddit APIs, documenting rate limits, costs, available
fields, and whether each API supports surge label construction.
"""

import logging
from typing import Any

from src.models import APIAssessment

logger = logging.getLogger(__name__)


def _estimate_collection_time_hours(
    target_posts: int, requests_per_minute: float, posts_per_request: int
) -> float:
    """Estimate hours needed to collect target_posts given rate limits.

    Args:
        target_posts: Number of posts to collect.
        requests_per_minute: API rate limit in requests per minute.
        posts_per_request: Average posts returned per request.

    Returns:
        Estimated collection time in hours.
    """
    if requests_per_minute <= 0 or posts_per_request <= 0:
        return float("inf")
    effective_posts_per_minute = requests_per_minute * posts_per_request
    minutes_needed = target_posts / effective_posts_per_minute
    return minutes_needed / 60.0


def _estimate_collection_cost(
    target_posts: int, cost_per_request: float, posts_per_request: int
) -> float:
    """Estimate USD cost to collect target_posts.

    Args:
        target_posts: Number of posts to collect.
        cost_per_request: Cost in USD per API request.
        posts_per_request: Average posts returned per request.

    Returns:
        Estimated cost in USD.
    """
    if posts_per_request <= 0:
        return float("inf")
    requests_needed = target_posts / posts_per_request
    return requests_needed * cost_per_request


def _check_surge_label_support(available_fields: list[str]) -> bool:
    """Check if API fields support surge label construction.

    Surge label requires: at least one engagement metric, at least one
    sentiment-capable text field, and a timestamp field.

    Args:
        available_fields: List of field names available from the API.

    Returns:
        True if all three categories are present.
    """
    fields_lower = {f.lower() for f in available_fields}

    engagement_fields = {
        "likes", "retweets", "comments", "upvotes", "shares",
        "favorites", "score", "like_count", "retweet_count",
        "reply_count", "quote_count", "impression_count",
        "ups", "downs", "num_comments",
    }
    text_fields = {
        "text", "body", "content", "title", "selftext",
        "full_text", "tweet_text",
    }
    timestamp_fields = {
        "created_at", "timestamp", "date", "created_utc",
        "created", "posted_at",
    }

    has_engagement = bool(fields_lower & engagement_fields)
    has_text = bool(fields_lower & text_fields)
    has_timestamp = bool(fields_lower & timestamp_fields)

    return has_engagement and has_text and has_timestamp


def assess_twitter_api() -> APIAssessment:
    """Evaluate X/Twitter API feasibility for stock discussion data collection.

    Assesses rate limits, endpoints, cost tiers, available fields,
    historical access, and whether the API supports surge label construction.
    Documents estimated time and cost to collect 10,000 posts.

    Returns:
        APIAssessment with X/Twitter API evaluation results.
    """
    logger.info("Assessing X/Twitter API feasibility...")

    # X/Twitter API v2 specifications (as of 2024)
    platform = "twitter"

    rate_limits: dict[str, Any] = {
        "free_tier": {
            "tweets_per_month": 1500,
            "requests_per_15min": 15,
            "posts_per_request": 100,
        },
        "basic_tier": {
            "tweets_per_month": 10000,
            "requests_per_15min": 60,
            "posts_per_request": 100,
        },
        "pro_tier": {
            "tweets_per_month": 1_000_000,
            "requests_per_15min": 300,
            "posts_per_request": 100,
        },
    }

    endpoints = [
        "GET /2/tweets/search/recent",
        "GET /2/tweets/search/all (Academic/Pro)",
        "GET /2/tweets/:id",
        "GET /2/tweets/counts/recent",
        "GET /2/users/:id/tweets",
    ]

    cost_tiers: list[dict[str, Any]] = [
        {"tier": "Free", "cost_usd_monthly": 0, "tweet_cap": 1500},
        {"tier": "Basic", "cost_usd_monthly": 100, "tweet_cap": 10000},
        {"tier": "Pro", "cost_usd_monthly": 5000, "tweet_cap": 1_000_000},
        {"tier": "Enterprise", "cost_usd_monthly": 42000, "tweet_cap": 50_000_000},
    ]

    available_fields = [
        "text", "created_at", "like_count", "retweet_count",
        "reply_count", "quote_count", "impression_count",
        "author_id", "conversation_id", "lang",
    ]

    # Historical access: only available on Pro tier and above
    historical_access = False  # Not on Free/Basic

    # Estimate for 10,000 posts using Basic tier
    # Basic: 60 requests per 15 min = 4 req/min, 100 posts/request
    target_posts = 10_000
    requests_per_minute = 4.0  # Basic tier effective rate
    posts_per_request = 100
    cost_per_request = 100.0 / (10_000 / 100)  # $100/month for 10k tweets = $1/request

    estimated_time = _estimate_collection_time_hours(
        target_posts, requests_per_minute, posts_per_request
    )
    estimated_cost = _estimate_collection_cost(
        target_posts, cost_per_request, posts_per_request
    )

    supports_surge = _check_surge_label_support(available_fields)

    paid_fields: list[dict[str, str]] = [
        {
            "field": "impression_count",
            "tier": "Basic ($100/month)",
            "description": "Tweet impression/view counts",
        },
        {
            "field": "full archive search",
            "tier": "Pro ($5,000/month)",
            "description": "Historical tweet access beyond 7 days",
        },
        {
            "field": "quote_count",
            "tier": "Basic ($100/month)",
            "description": "Number of quote tweets",
        },
    ]

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



def assess_reddit_api() -> APIAssessment:
    """Evaluate Reddit API feasibility for stock discussion data collection.

    Assesses rate limits, endpoints, cost tiers, available fields,
    historical access, and whether the API supports surge label construction.
    Documents estimated time and cost to collect 10,000 posts.

    Returns:
        APIAssessment with Reddit API evaluation results.
    """
    logger.info("Assessing Reddit API feasibility...")

    platform = "reddit"

    # Reddit API specifications (via PRAW / official API, as of 2024)
    rate_limits: dict[str, Any] = {
        "oauth_tier": {
            "requests_per_minute": 100,
            "posts_per_request": 100,
            "daily_limit": None,  # No hard daily cap for OAuth apps
        },
        "free_tier_note": (
            "Reddit API is free for non-commercial use with OAuth. "
            "Commercial use requires paid access."
        ),
    }

    endpoints = [
        "GET /r/{subreddit}/search",
        "GET /r/{subreddit}/hot",
        "GET /r/{subreddit}/new",
        "GET /r/{subreddit}/top",
        "GET /comments/{article}",
        "GET /api/info",
        "GET /search (site-wide)",
    ]

    cost_tiers: list[dict[str, Any]] = [
        {
            "tier": "Free (non-commercial)",
            "cost_usd_monthly": 0,
            "rate_limit": "100 requests/min",
            "note": "Requires OAuth app registration",
        },
        {
            "tier": "Commercial",
            "cost_usd_monthly": "Contact Reddit",
            "rate_limit": "Higher limits available",
            "note": "Required for commercial data use since 2023 API changes",
        },
    ]

    available_fields = [
        "title", "selftext", "body", "created_utc", "score",
        "ups", "downs", "num_comments", "upvote_ratio",
        "author", "subreddit", "permalink", "url",
        "link_flair_text", "over_18", "is_self",
    ]

    # Historical access: Reddit allows searching back ~6 months via API,
    # Pushshift (third-party) provided full history but is now restricted
    historical_access = True  # Limited but available via subreddit listings

    # Estimate for 10,000 posts using free OAuth tier
    # 100 requests/min, 100 posts/request
    target_posts = 10_000
    requests_per_minute = 100.0
    posts_per_request = 100
    cost_per_request = 0.0  # Free for non-commercial

    estimated_time = _estimate_collection_time_hours(
        target_posts, requests_per_minute, posts_per_request
    )
    estimated_cost = _estimate_collection_cost(
        target_posts, cost_per_request, posts_per_request
    )

    supports_surge = _check_surge_label_support(available_fields)

    paid_fields: list[dict[str, str]] = [
        {
            "field": "full historical archive",
            "tier": "Commercial (contact Reddit)",
            "description": "Complete historical post/comment access beyond API limits",
        },
        {
            "field": "real-time streaming",
            "tier": "Commercial (contact Reddit)",
            "description": "Real-time firehose access to new posts/comments",
        },
    ]

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
