"""
Binance 加密货币数据源
提供 OHLCV 价格数据（公开 API，无需认证）
国内需走代理访问

用法: 作为 get_stock_data 的 vendor 实现
"""

import logging
import os
from datetime import datetime
from typing import Annotated

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# 自定义异常：让 vendor fallback 机制能识别
class BinanceNotSupportedError(Exception):
    """Binance 不支持该 ticker（非加密货币或未映射）"""
    pass

# Binance API 地址
BINANCE_SPOT = "https://api.binance.com"          # 现货
BINANCE_FUTURES = "https://fapi.binance.com"      # 合约
BINANCE_SPOT_ALT = "https://api1.binance.com"
BINANCE_US = "https://api.binance.us"

# 只支持合约的交易对
FUTURES_ONLY = {
    "CYSUSDT",  # Cysic — 只有永续合约
}


def _get_session():
    """创建带代理的 requests session"""
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    session = requests.Session()
    if proxy_url:
        session.proxies = {"http": proxy_url, "https": proxy_url}
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    return session

# 币种名称 → Binance 交易对映射
CRYPTO_TO_BINANCE = {
    # 主流币（对 USDT）
    "BTC-USD": "BTCUSDT",     "BTC": "BTCUSDT",
    "ETH-USD": "ETHUSDT",     "ETH": "ETHUSDT",
    "BNB-USD": "BNBUSDT",     "BNB": "BNBUSDT",
    "SOL-USD": "SOLUSDT",     "SOL": "SOLUSDT",
    "XRP-USD": "XRPUSDT",     "XRP": "XRPUSDT",
    "ADA-USD": "ADAUSDT",     "ADA": "ADAUSDT",
    "DOGE-USD": "DOGEUSDT",   "DOGE": "DOGEUSDT",
    "DOT-USD": "DOTUSDT",     "DOT": "DOTUSDT",
    "AVAX-USD": "AVAXUSDT",   "AVAX": "AVAXUSDT",
    "LINK-USD": "LINKUSDT",   "LINK": "LINKUSDT",
    "MATIC-USD": "MATICUSDT", "MATIC": "MATICUSDT",
    "SUI-USD": "SUIUSDT",     "SUI": "SUIUSDT",
    "APT-USD": "APTUSDT",     "APT": "APTUSDT",
    "ARB-USD": "ARBUSDT",     "ARB": "ARBUSDT",
    "OP-USD": "OPUSDT",       "OP": "OPUSDT",
    "NEAR-USD": "NEARUSDT",   "NEAR": "NEARUSDT",
    "ATOM-USD": "ATOMUSDT",   "ATOM": "ATOMUSDT",
    "FIL-USD": "FILUSDT",     "FIL": "FILUSDT",
    "LTC-USD": "LTCUSDT",     "LTC": "LTCUSDT",
    "BCH-USD": "BCHUSDT",     "BCH": "BCHUSDT",
    "ETC-USD": "ETCUSDT",     "ETC": "ETCUSDT",
    "UNI-USD": "UNIUSDT",     "UNI": "UNIUSDT",
    "AAVE-USD": "AAVEUSDT",   "AAVE": "AAVEUSDT",
    "PEPE-USD": "PEPEUSDT",   "PEPE": "PEPEUSDT",
    "SHIB-USD": "SHIBUSDT",   "SHIB": "SHIBUSDT",
    "WIF-USD": "WIFUSDT",     "WIF": "WIFUSDT",
    "BONK-USD": "BONKUSDT",   "BONK": "BONKUSDT",
    "TON-USD": "TONUSDT",     "TON": "TONUSDT",
    "TRX-USD": "TRXUSDT",     "TRX": "TRXUSDT",
    # 比特币/以太坊 中文名
    "比特币": "BTCUSDT",       "以太坊": "ETHUSDT",
    "狗狗币": "DOGEUSDT",      "索拉纳": "SOLUSDT",
    "瑞波": "XRPUSDT",         "艾达": "ADAUSDT",
    # 黄金/白银（币安上有 PAXG 等代币化贵金属）
    "PAXG-USD": "PAXGUSDT",   "PAXG": "PAXGUSDT",
    "XAU-USD": "PAXGUSDT",    "XAU": "PAXGUSDT",

    # ===== Binance bStocks（代币化美股，2026年6月上线）=====
    # 交易对格式: XXXB/USDT，B 后缀代表 bStock
    # 映射同时支持 "NVDA-B"（标准格式）和 "NVDAB"（Binance 格式）+ 中文名
    "NVDA-B": "NVDABUSDT",  "NVDAB": "NVDABUSDT",  # NVIDIA 英伟达
    "AAPL-B": "AAPLBUSDT",  "AAPLB": "AAPLBUSDT",  # Apple 苹果
    "AMZN-B": "AMZNBUSDT",  "AMZNB": "AMZNBUSDT",  # Amazon 亚马逊
    "TSLA-B": "TSLABUSDT",  "TSLAB": "TSLABUSDT",  # Tesla 特斯拉
    "MSFT-B": "MSFTBUSDT",  "MSFTB": "MSFTBUSDT",  # Microsoft 微软
    "META-B": "METABUSDT",  "METAB": "METABUSDT",  # Meta
    "AMD-B":  "AMDBUSDT",   "AMDB":  "AMDBUSDT",   # AMD
    "INTC-B": "INTCBUSDT",  "INTCB": "INTCBUSDT",  # Intel 英特尔
    "MU-B":   "MUBUSDT",    "MUB":   "MUBUSDT",    # Micron 美光
    "SNDK-B": "SNDKBUSDT",  "SNDKB": "SNDKBUSDT",  # Sandisk 闪迪
    "PLTR-B": "PLTRBUSDT",  "PLTRB": "PLTRBUSDT",  # Palantir
    "DELL-B": "DELLBUSDT",  "DELLB": "DELLBUSDT",  # Dell 戴尔
    "GS-B":   "GSBUSDT",    "GSB":   "GSBUSDT",    # Goldman Sachs 高盛
    "PYPL-B": "PYPLBUSDT",  "PYPLB": "PYPLBUSDT",  # PayPal
    "NFLX-B": "NFLXBUSDT",  "NFLXB": "NFLXBUSDT",  # Netflix 奈飞
    "MSTR-B": "MSTRBUSDT",  "MSTRB": "MSTRBUSDT",  # MicroStrategy
    "CRCL-B": "CRCLBUSDT",  "CRCLB": "CRCLBUSDT",  # Circle (USDC发行商)
    # 中文名 → bStock ticker（只用-USDT后缀避免与普通美股冲突）
    "英伟达":   "NVDABUSDT", "苹果":   "AAPLBUSDT",
    "特斯拉":   "TSLABUSDT", "微软":   "MSFTBUSDT",
    "亚马逊":   "AMZNBUSDT", "amd":    "AMDBUSDT",
    "英特尔":   "INTCBUSDT", "美光":   "MUBUSDT",
    "闪迪":     "SNDKBUSDT", "戴尔":   "DELLBUSDT",
    # Binance 合约币（只有永续合约，走 fapi）
    "CYS-USD": "CYSUSDT",    "CYS": "CYSUSDT",
}

# 反向：Binance symbol → 标准 ticker
BINANCE_TO_TICKER = {v: k for k, v in CRYPTO_TO_BINANCE.items() if not any('一' <= c <= '鿿' for c in k)}


def resolve_binance_symbol(ticker: str) -> str:
    """将标准 ticker（如 BTC-USD、ETH）转换为 Binance 交易对（BTCUSDT）"""
    ticker_upper = ticker.upper().strip()
    if ticker_upper in CRYPTO_TO_BINANCE:
        return CRYPTO_TO_BINANCE[ticker_upper]

    # 尝试直接匹配（如已经是 BTCUSDT 格式）
    if ticker_upper.endswith("USDT") and len(ticker_upper) > 4:
        return ticker_upper

    # 移除 -USD 后缀尝试
    if "-USD" in ticker_upper:
        base = ticker_upper.replace("-USD", "")
        return f"{base}USDT"

    return None


def is_crypto_ticker(ticker: str) -> bool:
    """判断 ticker 是否是加密货币"""
    return resolve_binance_symbol(ticker) is not None


def _fetch_klines(symbol: str, interval: str, limit: int = 1000,
                  start_ms: int = None, end_ms: int = None) -> pd.DataFrame:
    """从 Binance 获取 K 线数据

    Args:
        symbol: Binance 交易对，如 BTCUSDT
        interval: K 线周期 (1d, 4h, 1h, 15m, etc.)
        limit: 最大 1000
        start_ms: 起始时间戳(毫秒)
        end_ms: 结束时间戳(毫秒)

    Returns:
        pd.DataFrame with columns: Open, High, Low, Close, Volume, Date
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": min(limit, 1000),
    }
    if start_ms:
        params["startTime"] = start_ms
    if end_ms:
        params["endTime"] = end_ms

    session = _get_session()

    # 合约币走 fapi，现货走 api
    if symbol in FUTURES_ONLY:
        endpoints = [(BINANCE_FUTURES, "/fapi/v1/klines")]
    else:
        endpoints = [
            (BINANCE_SPOT, "/api/v3/klines"),
            (BINANCE_SPOT_ALT, "/api/v3/klines"),
            (BINANCE_FUTURES, "/fapi/v1/klines"),  # 现货没有就试合约
        ]

    for base, path in endpoints:
        try:
            resp = session.get(f"{base}{path}", params=params, timeout=30)
            resp.raise_for_status()
            break
        except Exception as e:
            logger.debug(f"Binance {base}{path} 请求失败: {e}")
            continue
    else:
        raise ConnectionError(f"无法连接到 Binance API（已尝试所有端点）")

    data = resp.json()
    if not data:
        return pd.DataFrame()

    # Binance klines 格式:
    # [open_time, open, high, low, close, volume, close_time, quote_vol,
    #  trades, taker_buy_base, taker_buy_quote, ignore]
    df = pd.DataFrame(data, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "quote_vol", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    # 保留需要的列
    df = df[["Open", "High", "Low", "Close", "Volume", "open_time"]]
    df["Open"] = pd.to_numeric(df["Open"])
    df["High"] = pd.to_numeric(df["High"])
    df["Low"] = pd.to_numeric(df["Low"])
    df["Close"] = pd.to_numeric(df["Close"])
    df["Volume"] = pd.to_numeric(df["Volume"])

    # 时间转换
    df["Date"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.drop(columns=["open_time"])

    return df


def _fetch_range(symbol: str, start_date: str, end_date: str,
                 interval: str = "1d") -> pd.DataFrame:
    """分页获取日期范围内的所有 K 线数据

    Binance API 每次最多 1000 条，用循环分页拉取。
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    all_frames = []
    current_start = start_ms

    while current_start < end_ms:
        df = _fetch_klines(symbol, interval, limit=1000,
                           start_ms=current_start, end_ms=end_ms)

        if df.empty:
            break

        all_frames.append(df)

        # 下一页从最后一条数据之后开始
        last_time = pd.to_datetime(df["Date"].iloc[-1])
        current_start = int(last_time.timestamp() * 1000) + 1

        # 防止无限循环
        if len(df) < 2:
            break

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.drop_duplicates(subset=["Date"])
    result = result.sort_values("Date")
    return result


def get_binance_crypto_data(
    symbol: Annotated[str, "加密货币 ticker，如 BTC-USD, ETH-USD"],
    start_date: Annotated[str, "开始日期 YYYY-mm-dd"],
    end_date: Annotated[str, "结束日期 YYYY-mm-dd"],
) -> str:
    """从币安获取加密货币 OHLCV 数据

    这是 get_stock_data 的 binance_crypto vendor 实现。
    对于不支持的币种，返回空字符串让调用方 fallback 到其他 vendor。
    """
    binance_symbol = resolve_binance_symbol(symbol)
    if not binance_symbol:
        raise BinanceNotSupportedError(f"Binance vendor does not support ticker: {symbol}")

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    logger.info(f"Binance: 获取 {binance_symbol} ({symbol}) {start_date} → {end_date}")

    try:
        data = _fetch_range(binance_symbol, start_date, end_date, interval="1d")
    except Exception as e:
        logger.warning(f"Binance {binance_symbol} 获取失败: {e}")
        raise

    if data.empty:
        return (
            f"# Binance crypto data for {symbol} ({binance_symbol})\n"
            f"# No data found in range {start_date} to {end_date}\n"
        )

    # 格式化输出，与 yfinance 格式兼容
    # 保留 Date, Open, High, Low, Close, Volume
    output_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    output = data[output_cols].copy()
    output["Date"] = output["Date"].dt.strftime("%Y-%m-%d")

    # 数值四舍五入
    for col in ["Open", "High", "Low", "Close"]:
        output[col] = output[col].round(4)
    output["Volume"] = output["Volume"].round(2)

    csv_string = output.to_csv(index=False)

    header = (
        f"# Binance crypto data for {symbol} ({binance_symbol})\n"
        f"# Period: {start_date} to {end_date}\n"
        f"# Total records: {len(data)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"# Source: Binance public API\n\n"
    )

    return header + csv_string
