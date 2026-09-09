"""
中国商品期货数据源（akshare / 新浪财经）
提供上期所/大商所/郑商所期货日K线数据

用法: 作为 get_stock_data 的 vendor 实现
"""

import logging
from datetime import datetime
from typing import Annotated

import pandas as pd

logger = logging.getLogger(__name__)


class ChinaFuturesNotSupportedError(Exception):
    """不支持该期货品种"""
    pass


# 上期所 (SHFE) 品种代码 → 中文名
SHFE_SYMBOLS = {
    "AU0": "沪金",
    "AG0": "沪银",
    "CU0": "沪铜",
    "AL0": "沪铝",
    "ZN0": "沪锌",
    "PB0": "沪铅",
    "NI0": "沪镍",
    "SN0": "沪锡",
    "RB0": "螺纹钢",
    "HC0": "热卷",
    "RU0": "橡胶",
    "BU0": "沥青",
    "FU0": "燃油",
    "SP0": "纸浆",
    "SS0": "不锈钢",
}

# 用户输入 → 期货代码映射
TICKER_TO_SYMBOL = {
    # 沪金
    "沪金": "AU0", "AU0": "AU0", "AU=F": "AU0",
    "SHFE-AU": "AU0", "GOLD-SHFE": "AU0",
    # 沪银
    "沪银": "AG0", "AG0": "AG0", "AG=F": "AG0",
    "SHFE-AG": "AG0", "SILVER-SHFE": "AG0",
    # 沪铜
    "沪铜": "CU0", "CU0": "CU0",
    # 沪铝
    "沪铝": "AL0", "AL0": "AL0",
    # 螺纹钢
    "螺纹钢": "RB0", "螺纹": "RB0", "RB0": "RB0",
    # 原油（上期所）
    "上海原油": "SC0", "SC0": "SC0",
}


def resolve_sina_symbol(ticker: str) -> str:
    """将用户输入的 ticker 转为新浪期货代码"""
    ticker_stripped = ticker.strip()
    if ticker_stripped in TICKER_TO_SYMBOL:
        return TICKER_TO_SYMBOL[ticker_stripped]
    if ticker_stripped in SHFE_SYMBOLS:
        return ticker_stripped
    return None


def is_china_futures_ticker(ticker: str) -> bool:
    """判断是否国内期货品种"""
    return resolve_sina_symbol(ticker) is not None


def get_china_futures_data(
    symbol: Annotated[str, "国内期货品种，如 沪金、AU0、沪银"],
    start_date: Annotated[str, "开始日期 YYYY-mm-dd"],
    end_date: Annotated[str, "结束日期 YYYY-mm-dd"],
) -> str:
    """从 akshare 获取国内期货日K线数据

    这是 get_stock_data 的 china_futures vendor 实现。
    """
    sina_symbol = resolve_sina_symbol(symbol)
    if not sina_symbol:
        raise ChinaFuturesNotSupportedError(
            f"国内期货不支持: {symbol}"
        )

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    try:
        import akshare as ak
        df = ak.futures_zh_daily_sina(symbol=sina_symbol)
    except Exception as e:
        logger.warning(f"akshare 期货 {sina_symbol} 失败: {e}")
        raise ConnectionError(f"akshare 期货数据不可用: {e}")

    if df is None or df.empty:
        return (
            f"# 国内期货 {symbol} ({sina_symbol}) 无数据\n"
            f"# {start_date} → {end_date}\n"
        )

    # akshare 返回列: date, open, high, low, close, volume, hold, settle
    df = df.rename(columns={
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })

    # 只保留需要的列
    keep_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in keep_cols if c in df.columns]]

    df["Date"] = pd.to_datetime(df["Date"])
    df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt + pd.Timedelta(days=1))]
    df = df.sort_values("Date")

    if df.empty:
        return (
            f"# 国内期货 {symbol} ({sina_symbol}) 无数据\n"
            f"# {start_date} → {end_date}\n"
        )

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col]).round(2)
    df["Volume"] = pd.to_numeric(df["Volume"]).astype(int)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    csv_string = df[["Date", "Open", "High", "Low", "Close", "Volume"]].to_csv(
        index=False
    )
    name = SHFE_SYMBOLS.get(sina_symbol, sina_symbol)
    header = (
        f"# 国内期货: {symbol} ({sina_symbol} / {name})\n"
        f"# 周期: {start_date} 至 {end_date}  记录数: {len(df)}\n"
        f"# 获取时间: {datetime.now():%Y-%m-%d %H:%M:%S}  来源: akshare/新浪财经\n\n"
    )
    return header + csv_string
