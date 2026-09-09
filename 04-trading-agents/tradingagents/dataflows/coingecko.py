"""
CoinGecko 加密货币数据源
免费公开 API，无需代理，国内可直接访问
作为 Binance 的 fallback

用法: 作为 get_stock_data 的 vendor 实现
"""

import logging
from datetime import datetime
from typing import Annotated

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class CoinGeckoNotSupportedError(Exception):
    """CoinGecko 不支持该 ticker"""
    pass


COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# 币种 → CoinGecko coin_id
COINGECKO_ID_MAP = {
    "BTC-USD": "bitcoin",           "BTC": "bitcoin",
    "ETH-USD": "ethereum",          "ETH": "ethereum",
    "BNB-USD": "binancecoin",       "BNB": "binancecoin",
    "SOL-USD": "solana",            "SOL": "solana",
    "XRP-USD": "ripple",            "XRP": "ripple",
    "ADA-USD": "cardano",           "ADA": "cardano",
    "DOGE-USD": "dogecoin",         "DOGE": "dogecoin",
    "DOT-USD": "polkadot",          "DOT": "polkadot",
    "AVAX-USD": "avalanche-2",      "AVAX": "avalanche-2",
    "LINK-USD": "chainlink",        "LINK": "chainlink",
    "MATIC-USD": "matic-network",   "MATIC": "matic-network",
    "SUI-USD": "sui",               "SUI": "sui",
    "APT-USD": "aptos",             "APT": "aptos",
    "ARB-USD": "arbitrum",          "ARB": "arbitrum",
    "OP-USD": "optimism",           "OP": "optimism",
    "NEAR-USD": "near",             "NEAR": "near",
    "ATOM-USD": "cosmos",           "ATOM": "cosmos",
    "FIL-USD": "filecoin",          "FIL": "filecoin",
    "LTC-USD": "litecoin",          "LTC": "litecoin",
    "BCH-USD": "bitcoin-cash",      "BCH": "bitcoin-cash",
    "ETC-USD": "ethereum-classic",  "ETC": "ethereum-classic",
    "UNI-USD": "uniswap",           "UNI": "uniswap",
    "AAVE-USD": "aave",             "AAVE": "aave",
    "PEPE-USD": "pepe",             "PEPE": "pepe",
    "SHIB-USD": "shiba-inu",        "SHIB": "shiba-inu",
    "WIF-USD": "dogwifcoin",        "WIF": "dogwifcoin",
    "BONK-USD": "bonk",             "BONK": "bonk",
    "TON-USD": "the-open-network",  "TON": "the-open-network",
    "TRX-USD": "tron",              "TRX": "tron",
    "PAXG-USD": "pax-gold",         "PAXG": "pax-gold",
    "CYS-USD": "cysic",             "CYS": "cysic",
}


def resolve_coingecko_id(ticker: str) -> str:
    ticker_upper = ticker.upper().strip()
    return COINGECKO_ID_MAP.get(ticker_upper)


def get_coingecko_data(
    symbol: Annotated[str, "加密货币 ticker，如 BTC-USD, CYS-USD"],
    start_date: Annotated[str, "开始日期 YYYY-mm-dd"],
    end_date: Annotated[str, "结束日期 YYYY-mm-dd"],
) -> str:
    """从 CoinGecko 获取 OHLCV 数据"""
    coin_id = resolve_coingecko_id(symbol)
    if not coin_id:
        raise CoinGeckoNotSupportedError(f"CoinGecko 不支持 {symbol}")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    days = max(1, (end_dt - start_dt).days + 1)
    days = min(days, 365)

    url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": str(days)}

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"CoinGecko {coin_id} 失败: {e}")
        raise

    if not data or not isinstance(data, list):
        raise CoinGeckoNotSupportedError(f"CoinGecko {coin_id} 无数据")

    df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
    df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop(columns=["timestamp"])
    df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt + pd.Timedelta(days=1))]
    df = df.sort_values("Date")

    if df.empty:
        return f"# CoinGecko {symbol} ({coin_id}) 无数据 {start_date} → {end_date}\n"

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = df[col].round(6)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    csv_string = df[["Date", "Open", "High", "Low", "Close"]].to_csv(index=False)
    header = (
        f"# CoinGecko data for {symbol} ({coin_id})\n"
        f"# Period: {start_date} to {end_date}  Records: {len(df)}\n"
        f"# Retrieved: {datetime.now():%Y-%m-%d %H:%M:%S}  Source: CoinGecko\n\n"
    )
    return header + csv_string
