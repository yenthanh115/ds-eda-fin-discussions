"""Ticker extraction module for the EDA Financial Discussions pipeline.

Extracts stock ticker symbols from text content when datasets lack an
explicit ticker column. Uses cashtag matching ($TSLA) and a curated list
of known tickers to identify stock mentions in post titles and body text.
"""

import re
from typing import Optional

import pandas as pd


# Curated set of common US stock tickers discussed on social media.
# Excludes very short or ambiguous tickers (e.g., "A", "I", "IT", "GO")
# that would produce excessive false positives.
KNOWN_TICKERS: set[str] = {
    # Mega-cap / meme stocks frequently discussed
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "TSLA", "META", "NVDA",
    "AMD", "INTC", "NFLX", "DIS", "PYPL", "SQ", "SHOP", "ROKU",
    # Meme / retail favorites
    "GME", "AMC", "BB", "BBBY", "PLTR", "WISH", "CLOV", "SOFI",
    "SPCE", "NIO", "LCID", "RIVN", "HOOD", "DKNG", "COIN",
    # Finance / banking
    "JPM", "BAC", "GS", "MS", "WFC", "C", "V", "MA",
    # Healthcare / pharma
    "JNJ", "PFE", "MRNA", "BNTX", "ABBV", "UNH", "LLY",
    # Energy
    "XOM", "CVX", "OXY", "BP", "COP",
    # Other large-cap
    "WMT", "COST", "TGT", "HD", "LOW", "NKE", "SBUX",
    "BA", "CAT", "DE", "MMM", "GE", "F", "GM",
    "CRM", "ORCL", "ADBE", "NOW", "SNOW", "UBER", "LYFT",
    "ZM", "DOCU", "CRWD", "NET", "DDOG", "MDB",
    # ETFs commonly discussed as tickers
    "SPY", "QQQ", "IWM", "DIA", "ARKK", "VTI", "VOO",
    # Additional retail-popular tickers
    "TWNK", "WKHS", "CLNE", "TTNP", "MVIS", "SENS", "TLRY",
    "SNDL", "CLOV", "CLVS", "RKT", "UWMC", "CRSR", "BNGO",
}

# Minimum ticker length to avoid false positives with common English words
_MIN_TICKER_LEN = 2

# Common English words that look like tickers but aren't
_FALSE_POSITIVE_WORDS: set[str] = {
    "CEO", "IPO", "ETF", "SEC", "FDA", "GDP", "CPI", "ATH", "DD",
    "EPS", "PE", "RSI", "MACD", "OTC", "NYSE", "IMO", "FYI",
    "YOLO", "FOMO", "HODL", "WSB", "OP", "TL", "DR", "TLDR",
    "US", "UK", "EU", "AI", "ML", "IT", "PM", "AM",
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL",
    "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "HAD",
    "HAS", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD",
    "SEE", "WAY", "WHO", "DID", "GET", "HIM", "LET", "SAY",
    "SHE", "TOO", "USE", "RUN", "BIG", "TOP", "LOW", "HIGH",
    "BUY", "PUT", "CALL", "LONG", "SHORT", "BULL", "BEAR",
    "RED", "GREEN", "MOON", "APE", "APES", "HOLD", "SELL",
}

# Regex for cashtag pattern: $TICKER
_CASHTAG_PATTERN = re.compile(r'\$([A-Z]{2,5})\b')

# Regex for standalone uppercase words (potential tickers)
_UPPERCASE_WORD_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')


def extract_tickers_from_text(text: str) -> list[str]:
    """Extract stock ticker symbols from a single text string.

    Uses two strategies:
    1. Cashtag matching: finds $TICKER patterns (high confidence)
    2. Known-ticker matching: finds uppercase words that match the curated ticker list

    Args:
        text: The text content to search for ticker mentions.

    Returns:
        A deduplicated list of ticker symbols found in the text.
        Returns empty list if text is None/empty or no tickers found.
    """
    if not text or not isinstance(text, str):
        return []

    found_tickers: set[str] = set()

    # Strategy 1: Cashtag matching (high confidence)
    cashtags = _CASHTAG_PATTERN.findall(text)
    for tag in cashtags:
        if tag not in _FALSE_POSITIVE_WORDS and len(tag) >= _MIN_TICKER_LEN:
            found_tickers.add(tag)

    # Strategy 2: Known-ticker matching from uppercase words
    # Convert text to handle mixed case by extracting only uppercase sequences
    uppercase_words = _UPPERCASE_WORD_PATTERN.findall(text)
    for word in uppercase_words:
        if word in KNOWN_TICKERS and word not in _FALSE_POSITIVE_WORDS:
            found_tickers.add(word)

    return sorted(found_tickers)


def extract_tickers_column(
    df: pd.DataFrame,
    text_cols: list[str],
    output_col: str = "ticker",
) -> pd.DataFrame:
    """Add a ticker column to a DataFrame by extracting tickers from text columns.

    For each row, concatenates the specified text columns and extracts ticker
    mentions. If multiple tickers are found, the first one (alphabetically) is
    used as the primary ticker. Rows with no detected tickers get a value of
    "UNKNOWN".

    Args:
        df: The input DataFrame.
        text_cols: List of column names containing text to search for tickers.
            Columns that don't exist in the DataFrame are silently skipped.
        output_col: Name of the output column to create. Defaults to "ticker".

    Returns:
        A new DataFrame with the ticker column added. The original DataFrame
        is not modified.
    """
    result = df.copy()

    # Filter to columns that actually exist
    available_cols = [col for col in text_cols if col in df.columns]

    if not available_cols:
        result[output_col] = "UNKNOWN"
        return result

    def _extract_for_row(row: pd.Series) -> str:
        combined_text = " ".join(
            str(row[col]) for col in available_cols
            if pd.notna(row[col])
        )
        tickers = extract_tickers_from_text(combined_text)
        if tickers:
            return tickers[0]  # Primary ticker (first alphabetically)
        return "UNKNOWN"

    result[output_col] = df.apply(_extract_for_row, axis=1)
    return result


def extract_all_tickers_column(
    df: pd.DataFrame,
    text_cols: list[str],
    output_col: str = "tickers_all",
) -> pd.DataFrame:
    """Add a column with all extracted tickers (comma-separated) for each row.

    Unlike extract_tickers_column which picks a single primary ticker, this
    function preserves all detected tickers per row.

    Args:
        df: The input DataFrame.
        text_cols: List of column names containing text to search for tickers.
        output_col: Name of the output column to create.

    Returns:
        A new DataFrame with the all-tickers column added.
    """
    result = df.copy()

    available_cols = [col for col in text_cols if col in df.columns]

    if not available_cols:
        result[output_col] = ""
        return result

    def _extract_all_for_row(row: pd.Series) -> str:
        combined_text = " ".join(
            str(row[col]) for col in available_cols
            if pd.notna(row[col])
        )
        tickers = extract_tickers_from_text(combined_text)
        return ",".join(tickers)

    result[output_col] = df.apply(_extract_all_for_row, axis=1)
    return result


def add_ticker_column_if_missing(
    df: pd.DataFrame,
    ticker_col: str = "ticker",
    text_cols: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Add a ticker column to the DataFrame if one doesn't already exist.

    This is the main entry point for the pipeline. If the DataFrame already
    has the specified ticker column, it is returned unchanged. Otherwise,
    ticker extraction is performed on text columns.

    Args:
        df: The input DataFrame.
        ticker_col: Name of the expected ticker column. Defaults to "ticker".
        text_cols: Text columns to search for tickers. If None, auto-detects
            text columns using common names (title, selftext, text, body, content).

    Returns:
        DataFrame with a ticker column present (either existing or newly extracted).
    """
    if ticker_col in df.columns:
        return df

    # Auto-detect text columns if not specified
    if text_cols is None:
        candidate_text_cols = [
            "title", "selftext", "text", "body", "content",
            "comment", "message", "clean_text", "Text",
        ]
        text_cols = [col for col in candidate_text_cols if col in df.columns]

    if not text_cols:
        # No text columns found — add UNKNOWN ticker column
        result = df.copy()
        result[ticker_col] = "UNKNOWN"
        return result

    return extract_tickers_column(df, text_cols, output_col=ticker_col)
