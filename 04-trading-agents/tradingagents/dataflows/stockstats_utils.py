import time
import logging
import threading
import random

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from stockstats import wrap
from typing import Annotated
import os
from .config import get_config
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

# Global lock: prevent concurrent yfinance calls from hammering Yahoo
_yf_lock = threading.Lock()
_yf_last_call = 0.0
_YF_MIN_INTERVAL = 10.0  # minimum seconds between yfinance calls (increased for rate limiting)


def _yf_wait():
    """Acquire global lock and enforce minimum interval between calls."""
    global _yf_lock, _yf_last_call
    _yf_lock.acquire()
    elapsed = time.monotonic() - _yf_last_call
    if elapsed < _YF_MIN_INTERVAL:
        gap = _YF_MIN_INTERVAL - elapsed + random.uniform(0, 2)
        time.sleep(gap)


def _yf_release():
    global _yf_lock, _yf_last_call
    _yf_last_call = time.monotonic()
    _yf_lock.release()


def _get_yf_session():
    """Create a yfinance-compatible session with proxy support.

    curl_cffi on Windows has TLS issues with some proxies. When HTTPS_PROXY
    is set, fall back to a plain requests.Session so the proxy handles TLS
    to Yahoo Finance instead of curl_cffi's local TLS stack.
    """
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    if not proxy_url:
        return None  # let yfinance use its default curl_cffi session

    import requests as _requests
    session = _requests.Session()
    session.proxies = {"http": proxy_url, "https": proxy_url}
    # Set a realistic User-Agent so Yahoo doesn't block us
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    return session


def yf_ticker(symbol: str) -> yf.Ticker:
    """Create a yfinance Ticker with global rate-limit serialisation."""
    _yf_wait()
    try:
        session = _get_yf_session()
        return yf.Ticker(symbol, session=session)
    finally:
        _yf_release()


def yf_retry(func, max_retries=3, base_delay=10.0):
    """Execute a yfinance call with global serialisation and exponential backoff."""
    _yf_wait()
    try:
        for attempt in range(max_retries + 1):
            try:
                result = func()
                return result
            except YFRateLimitError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Yahoo Finance rate limited, retrying in {delay:.0f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                else:
                    raise
    finally:
        _yf_release()


def _ensure_date_column(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize the date column to ``Date``.

    Some yfinance builds leave the index unnamed (so ``reset_index()`` yields
    ``index``) or use ``Datetime`` for intraday data. Rename the first
    date-like column so indicators don't silently drop when it isn't ``Date``.
    """
    if "Date" in data.columns:
        return data
    for candidate in ("index", "Datetime", "date"):
        if candidate in data.columns:
            return data.rename(columns={candidate: "Date"})
    return data


def _clean_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock DataFrame for stockstats: parse dates, drop invalid rows, fill price gaps."""
    data = _ensure_date_column(data)
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=["Close"])
    data[price_cols] = data[price_cols].ffill().bfill()

    return data


def load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV data with caching, filtered to prevent look-ahead bias.

    Downloads 5 years of data up to today and caches per symbol. On
    subsequent calls the cache is reused. Rows after curr_date are
    filtered out so backtests never see future prices.

    For crypto tickers, tries Binance/CoinGecko first before falling back
    to Yahoo Finance.
    """
    # Reject ticker values that would escape the cache directory when
    # interpolated into the cache filename (e.g. ``../../tmp/x``).
    safe_symbol = safe_ticker_component(symbol)

    config = get_config()
    curr_date_dt = pd.to_datetime(curr_date)

    # Cache uses a fixed window (5y to today) so one file per symbol
    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today_date.strftime("%Y-%m-%d")

    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(
        config["data_cache_dir"],
        f"{safe_symbol}-YFin-data-{start_str}-{end_str}.csv",
    )

    if os.path.exists(data_file):
        data = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
    else:
        data = _download_ohlcv(symbol, start_str, end_str)
        if data is not None and not data.empty:
            data = _ensure_date_column(data.reset_index())
            data.to_csv(data_file, index=False, encoding="utf-8")

    if data is None or data.empty:
        return pd.DataFrame()

    data = _clean_dataframe(data)

    # Filter to curr_date to prevent look-ahead bias in backtesting
    data = data[data["Date"] <= curr_date_dt]

    return data


def _download_ohlcv(symbol: str, start_str: str, end_str: str):
    """Download OHLCV data.  Tries the vendor system (Binance/CoinGecko) for
    crypto tickers first, then falls back to yfinance for everything else.
    """
    # Try the vendor routing first (Binance → CoinGecko → Alpha Vantage → yfinance)
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        csv_str = route_to_vendor("get_stock_data", symbol, start_str, end_str)

        # Parse the CSV output back into a DataFrame
        import io
        lines = csv_str.strip().split("\n")
        # Skip comment lines (starting with #)
        data_lines = [l for l in lines if not l.startswith("#")]
        if data_lines:
            df = pd.read_csv(io.StringIO("\n".join(data_lines)))
            if not df.empty and "Open" in df.columns:
                # Normalise column names to match yfinance output
                if "Date" not in df.columns:
                    for col in ["timestamp", "time", "datetime"]:
                        if col in df.columns:
                            df = df.rename(columns={col: "Date"})
                            break
                logger.info("Downloaded %s via vendor system (%d rows)", symbol, len(df))
                return df
    except Exception:
        pass  # Fall through to yfinance

    # Fallback: yfinance direct download
    return yf_retry(lambda: yf.download(
        symbol,
        start=start_str,
        end=end_str,
        multi_level_index=False,
        progress=False,
        auto_adjust=True,
    ))


def filter_financials_by_date(data: pd.DataFrame, curr_date: str) -> pd.DataFrame:
    """Drop financial statement columns (fiscal period timestamps) after curr_date.

    yfinance financial statements use fiscal period end dates as columns.
    Columns after curr_date represent future data and are removed to
    prevent look-ahead bias.
    """
    if not curr_date or data.empty:
        return data
    cutoff = pd.Timestamp(curr_date)
    mask = pd.to_datetime(data.columns, errors="coerce") <= cutoff
    return data.loc[:, mask]


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        data = load_ohlcv(symbol, curr_date)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
