"""
TradingAgents 飞书机器人
使用 WebSocket 长连接，无需公网 IP，本地即可运行

使用方法:
    python feishu_bot.py

前置准备:
    1. 在飞书开放平台 (open.feishu.cn) 创建企业自建应用
    2. 开启机器人能力，获取 App ID 和 App Secret
    3. 权限管理开启: im:message, im:message:send_as_bot, im:chat:readonly
    4. 事件订阅: 订阅 im.message.receive_v1 事件
    5. 发布应用，将机器人添加到飞书群
    6. 在 .env 中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET
"""

import asyncio
import concurrent.futures
import datetime
import json
import logging
import os
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

import lark_oapi as lark
from dotenv import load_dotenv
from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

# ---- 代理配置（访问 Yahoo Finance 等海外数据源）----
PROXY_URL = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or "http://127.0.0.1:9567"
os.environ["HTTP_PROXY"] = PROXY_URL
os.environ["HTTPS_PROXY"] = PROXY_URL
os.environ["NO_PROXY"] = "localhost,127.0.0.1,.feishu.cn,.feishu.cn"

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from feishu_card_builder import (
    build_progress_card,
    build_error_card,
    build_report_card,
    build_help_card,
    build_full_report_md,
)

# ---- 日志 ----
LOG_FILE = Path(__file__).parent / "feishu_bot.log"

# 自定义 StreamHandler，容忍 GBK 编码错误（Windows 终端无法输出 emoji）
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            pass  # 跳过无法编码的 emoji 字符

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        SafeStreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("feishu_bot")

# ---- 配置 ----
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

if not APP_ID or not APP_SECRET:
    logger.error("❌ 请在 .env 中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    logger.error("   获取方式: 飞书开放平台 → 应用 → 凭证与基础信息")
    sys.exit(1)

# ---- 初始化 TradingAgents ----
# ---- 分析模式预设 ----
ANALYSIS_MODES = {
    "fast": {
        "deep_think_llm": "deepseek-v4-flash",
        "quick_think_llm": "deepseek-v4-flash",
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "news_article_limit": 5,
        "global_news_article_limit": 3,
    },
    "deep": {
        "deep_think_llm": "deepseek-v4-pro",
        "quick_think_llm": "deepseek-v4-flash",
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
        "news_article_limit": 20,
        "global_news_article_limit": 10,
    },
    # Leap 竞赛模式：质量优先，深度思考 + 多轮辩论 + 操作建议
    "leap": {
        "deep_think_llm": "deepseek-v4-pro",
        "quick_think_llm": "deepseek-v4-pro",
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 2,
        "news_article_limit": 20,
        "global_news_article_limit": 10,
    },
}

current_mode = "fast"  # 默认快速模式

# ---- The Leap 模拟交易大赛（加密版）标的 ----
# 下一届: BTCUSDC, ETHUSDC, SOLUSDC, LTCUSDC, XRPUSDC, DOGEUSDC
LEAP_TICKERS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "LTC-USD",
    "XRP-USD",
    "DOGE-USD",
]
LEAP_TICKER_NAMES = ["比特币", "以太坊", "SOL", "LTC", "瑞波", "狗狗币"]

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "deepseek"
config["output_language"] = "Chinese"
config.update(ANALYSIS_MODES[current_mode])

# ---- 数据源配置：Binance → CoinGecko → 新浪期货 → Alpha Vantage → Yahoo Finance ----
config["data_vendors"] = {
    "core_stock_apis": "binance_crypto,coingecko,china_futures,alpha_vantage,yfinance",
    "technical_indicators": "alpha_vantage,yfinance",
    "fundamental_data": "alpha_vantage,yfinance",
    "news_data": "alpha_vantage,yfinance",
}

logger.info(f"🤖 TradingAgents 飞书机器人启动中...")
logger.info(f"   LLM: {config['llm_provider']} / {config['deep_think_llm']} / {config['quick_think_llm']}")
logger.info(f"   数据源: Binance → CoinGecko → 新浪期货 → Alpha Vantage → Yahoo Finance")
logger.info(f"   App ID: {APP_ID[:8]}***")

# ---- 飞书 API Client ----
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.WARNING) \
    .build()

# ---- 线程池（用于运行阻塞的分析任务）----
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def send_card(chat_id: str, card_data: dict) -> None:
    """发送飞书卡片消息到指定群聊"""
    try:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(json.dumps(card_data, ensure_ascii=False))
                    .build()
            ).build()

        client.im.v1.message.create(request)
    except Exception as e:
        logger.error(f"发送卡片消息失败: {e}")


def send_long_text(chat_id: str, title: str, content: str) -> None:
    """发送长文本消息（分段发送，每段不超过 25KB）"""
    try:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        MAX_LEN = 25000
        remaining = content
        part_num = 0

        while remaining:
            part_num += 1
            if len(remaining) <= MAX_LEN:
                chunk = remaining
                remaining = ""
            else:
                split_pos = remaining.rfind('\n', 0, MAX_LEN)
                if split_pos == -1:
                    split_pos = MAX_LEN
                chunk = remaining[:split_pos]
                remaining = remaining[split_pos:]

            label = f"{title} ({part_num})" if part_num > 1 or remaining else title
            text_json = json.dumps({"text": f"{label}\n\n{chunk}"}, ensure_ascii=False)

            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                        .receive_id(chat_id)
                        .msg_type("text")
                        .content(text_json)
                        .build()
                ).build()

            client.im.v1.message.create(request)

    except Exception as e:
        logger.error(f"发送长文本失败: {e}")


def send_as_file(chat_id: str, filename: str, content: str) -> None:
    """将报告保存为文件并发送到飞书群"""
    import tempfile
    try:
        from lark_oapi.api.im.v1 import CreateFileRequest, CreateFileRequestBody, CreateMessageRequest, CreateMessageRequestBody

        # 写入临时文件
        tmp_path = Path(tempfile.gettempdir()) / filename
        tmp_path.write_text(content, encoding="utf-8")
        logger.info(f"临时文件: {tmp_path} ({tmp_path.stat().st_size} bytes)")

        # 上传文件到飞书
        with open(tmp_path, "rb") as f:
            upload_req = CreateFileRequest.builder() \
                .request_body(
                    CreateFileRequestBody.builder()
                        .file_name(filename)
                        .file_type("stream")
                        .file(f)
                        .build()
                ).build()
            upload_resp = client.im.v1.file.create(upload_req)
            file_key = upload_resp.data.file_key if upload_resp.data else ""
            logger.info(f"文件上传: code={upload_resp.code}, file_key={file_key}")

        if not file_key:
            logger.error("文件上传失败，回退到文本发送")
            send_long_text(chat_id, filename, content)
            return

        # 发送文件消息
        file_content = json.dumps({"file_key": file_key}, ensure_ascii=False)
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("file")
                    .content(file_content)
                    .build()
            ).build()
        r = client.im.v1.message.create(request)
        logger.info(f"文件消息发送: code={r.code}")

        # 清理临时文件
        try:
            tmp_path.unlink()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"发送文件失败: {e}")
        # 回退到文本发送
        send_long_text(chat_id, filename, content)


def send_text(chat_id: str, text: str) -> None:
    """发送文本消息到指定群聊"""
    try:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": text}))
                    .build()
            ).build()

        client.im.v1.message.create(request)
    except Exception as e:
        logger.error(f"发送文本消息失败: {e}")


# 常见股票名称映射（中文名 → 代码）
# 数据源: 加密货币走币安 (binance_crypto vendor), 美股走 Yahoo Finance
STOCK_NAMES = {
    # ===== 加密货币（币安数据源优先）=====
    # 主流币
    "比特币": "BTC-USD", "以太坊": "ETH-USD", "以太": "ETH-USD",
    "狗狗币": "DOGE-USD", "索拉纳": "SOL-USD", "sol": "SOL-USD",
    "瑞波": "XRP-USD", "艾达": "ADA-USD", "bnb": "BNB-USD",
    "link": "LINK-USD", "dot": "DOT-USD", "avax": "AVAX-USD",
    "matic": "MATIC-USD", "pol": "MATIC-USD",
    "sui": "SUI-USD", "apt": "APT-USD", "arb": "ARB-USD",
    "op": "OP-USD", "near": "NEAR-USD", "atom": "ATOM-USD",
    "fil": "FIL-USD", "ltc": "LTC-USD", "bch": "BCH-USD",
    "etc": "ETC-USD", "uni": "UNI-USD", "aave": "AAVE-USD",
    "pepe": "PEPE-USD", "shib": "SHIB-USD", "wif": "WIF-USD",
    "bonk": "BONK-USD", "ton": "TON-USD", "trx": "TRX-USD",
    # 代币化黄金
    "黄金": "PAXG-USD", "paxg": "PAXG-USD", "xau": "PAXG-USD",
    # ===== Binance bStocks（币安代币化美股，走币安数据源）=====
    "nvda代币": "NVDAB", "英伟达代币": "NVDAB",
    "aapl代币": "AAPLB", "苹果代币": "AAPLB",
    "tsla代币": "TSLAB", "特斯拉代币": "TSLAB",
    "msft代币": "MSFTB", "微软代币": "MSFTB",
    "amzn代币": "AMZNB", "亚马逊代币": "AMZNB",
    "美光代币": "MUB", "闪迪代币": "SNDKB",
    "intc代币": "INTCB", "英特尔代币": "INTCB",
    "amd代币": "AMDB",
    "meta代币": "METAB", "pltr代币": "PLTRB",
    "dell代币": "DELLB", "戴尔代币": "DELLB",
    "高盛代币": "GSB", "nflx代币": "NFLXB",
    # 同时也支持直接用 bStock ticker
    "nvda-b": "NVDAB", "aapl-b": "AAPLB", "tsla-b": "TSLAB",
    "msft-b": "MSFTB", "amzn-b": "AMZNB", "mu-b": "MUB",
    # ===== 美股科技 =====",
    "苹果": "AAPL", "特斯拉": "TSLA", "英伟达": "NVDA", "微软": "MSFT",
    "谷歌": "GOOGL", "亚马逊": "AMZN", "meta": "META", "奈飞": "NFLX",
    "amd": "AMD", "英特尔": "INTC", "台积电": "TSM", "高通": "QCOM",
    "美光": "MU", "博通": "AVGO", "德州仪器": "TXN", "英伟达": "NVDA",
    "snap": "SNAP", "优步": "UBER", "airbnb": "ABNB", "zoom": "ZM",
    "palantir": "PLTR", "甲骨文": "ORCL", "ibm": "IBM", "惠普": "HPQ",
    "戴尔": "DELL", "思科": "CSCO", "salesforce": "CRM", "adobe": "ADBE",
    # 闪迪已被西部数据收购
    "西部数据": "WDC", "希捷": "STX",
    # 金融
    "摩根大通": "JPM", "高盛": "GS", "伯克希尔": "BRK-B", "摩根士丹利": "MS",
    # 其他美股
    "可口可乐": "KO", "百事": "PEP", "麦当劳": "MCD", "星巴克": "SBUX",
    "耐克": "NKE", "迪士尼": "DIS", "波音": "BA", "洛克希德": "LMT",
    "沃尔玛": "WMT", "开市客": "COST", "家得宝": "HD",
    "辉瑞": "PFE", "强生": "JNJ", "联合健康": "UNH", "礼来": "LLY",
    "埃克森美孚": "XOM", "雪佛龙": "CVX",
    # 中概/港股
    "腾讯": "0700.HK", "阿里": "9988.HK", "美团": "3690.HK",
    "比亚迪": "002594.SZ", "茅台": "600519.SS", "宁德时代": "300750.SZ",
    "百度": "BIDU", "京东": "JD", "拼多多": "PDD", "蔚来": "NIO",
    "小鹏": "XPEV", "理想": "LI", "哔哩哔哩": "BILI",
    # 大宗商品（Yahoo Finance 数据源）
    "白银": "SI=F", "原油": "CL=F",
    # 国内期货（新浪财经数据源）
    "沪金": "AU0", "沪银": "AG0",
    "黄金期货": "AU0", "白银期货": "AG0",
    "au0": "AU0", "ag0": "AG0",
}

# 时间维度关键词
HORIZON_KEYWORDS = {
    "short": ["短线", "短期", "日内", "超短", "几天", "近期", "短期交易", "short"],
    "medium": ["中线", "中期", "波段", "几周", "中期投资", "medium"],
    "long": ["长线", "长期", "投资", "持有", "价值投资", "几个月", "几年", "long"],
}


def parse_request(text: str) -> dict:
    """
    自然语言解析用户意图，返回:
    { command, ticker, date, horizon, raw }
    """
    text = text.strip()
    text = re.sub(r'@\S+\s*', '', text).strip()

    result = {
        "command": "unknown",
        "ticker": None,
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "horizon": "medium",  # 默认中线
        "raw": text,
    }

    # 模式切换
    if any(w in text.lower() for w in ['快速模式', 'fast', '快速', '快一点', '加速']):
        result["command"] = "switch_mode"
        result["mode"] = "fast"
        return result
    if any(w in text.lower() for w in ['竞赛模式', 'leap模式', 'leap', '比赛模式']):
        result["command"] = "switch_mode"
        result["mode"] = "leap"
        return result
    if any(w in text.lower() for w in ['深度模式', 'deep', '深度', '慢一点', '仔细', '详细']):
        result["command"] = "switch_mode"
        result["mode"] = "deep"
        return result

    # The Leap 竞赛批量分析
    if any(w in text.lower() for w in ['竞赛分析', 'leap分析', '比赛分析', '全部分析']):
        result["command"] = "leap_analysis"
        return result

    # 帮助
    if text.lower() in ('帮助', 'help', '?', '？', '/help', 'h', '怎么用', '使用', '功能'):
        result["command"] = "help"
        return result

    # 方法论
    if any(w in text for w in ['方法', '原理', '流程', '怎么分析', '如何分析', '方法论']):
        result["command"] = "methodology"
        return result

    # 检测时间维度
    for horizon, keywords in HORIZON_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            result["horizon"] = horizon
            break

    # 提取股票代码（支持各种自然语言表述）
    # 先检查已知中文名
    for name, code in STOCK_NAMES.items():
        if name.lower() in text.lower():
            result["ticker"] = code
            result["command"] = "analyze"
            break

    # 正则提取: 纯股票代码模式（大小写不敏感）
    if result["ticker"] is None:
        # 先直接找任何像股票代码的模式
        matches = re.findall(r'\b([A-Za-z]{1,5}(?:\.[A-Za-z]{2})?)\b', text)
        skip = {'i', 'a', 'is', 'it', 'at', 'ok', 'us', 'no', 'ai', 'etf', 'ceo', 'api',
                'usd', 'gdp', 'ipo', 'the', 'to', 'in', 'on', 'of', 'or', 'be', 'by',
                'if', 'so', 'we', 'he', 'me', 'my', 'do', 'go', 'la', 'de', 'new'}
        for m in matches:
            if m.lower() not in skip and len(m) >= 2:
                result["ticker"] = m.upper()
                result["command"] = "analyze"
                break

    # 提取日期
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if date_match:
        result["date"] = date_match.group(1)

    # 如果有股票代码但没匹配到命令
    if result["ticker"] and result["command"] == "unknown":
        result["command"] = "analyze"

    return result


def run_analysis_sync(chat_id: str, ticker: str, date: str, horizon: str = "medium", mode: str = None) -> None:
    """在后台线程中运行分析，完成后发送结果"""
    try:
        horizon_labels = {"short": "短线", "medium": "中线", "long": "长线"}
        horizon_label = horizon_labels.get(horizon, "中线")

        # Leap 竞赛标的自动使用竞赛模式（质量优先）
        effective_mode = mode or current_mode
        base_symbol = ticker.upper().replace("-USD", "")
        leap_bases = {t.upper().replace("-USD", "") for t in LEAP_TICKERS}
        is_leap_ticker = base_symbol in leap_bases
        if is_leap_ticker and effective_mode != "leap":
            effective_mode = "leap"
            logger.info(f"🏆 {ticker} 是竞赛标的，自动启用竞赛深度模式")

        logger.info(f"📊 开始分析 {ticker} ({date}, {horizon_label}, 模式: {effective_mode})")

        # 分析深度配置
        analysis_config = config.copy()
        analysis_config.update(ANALYSIS_MODES.get(effective_mode, {}))
        if horizon == "short":
            analysis_config["max_debate_rounds"] = 1
            analysis_config["max_risk_discuss_rounds"] = 1
        elif horizon == "long":
            analysis_config["max_debate_rounds"] = max(analysis_config.get("max_debate_rounds", 1), 2)
            analysis_config["max_risk_discuss_rounds"] = max(analysis_config.get("max_risk_discuss_rounds", 1), 2)
        # medium: 使用模式默认值

        retry_count = 0
        while retry_count < 2:
            try:
                graph = TradingAgentsGraph(
                    config=analysis_config,
                    debug=False,
                )
                final_state, decision = graph.propagate(ticker, date)
                break
            except Exception as e:
                err_msg = str(e)
                if ("connection" in err_msg.lower() or "rate limited" in err_msg.lower() or "timeout" in err_msg.lower()) and retry_count < 1:
                    retry_count += 1
                    wait = 30
                    logger.warning(f"⚠️ 分析 {ticker} 网络错误，{wait}s 后重试 ({retry_count}/1): {e}")
                    time.sleep(wait)
                else:
                    raise

        logger.info(f"✅ 分析完成 {ticker}: {decision}")

        # 发送摘要卡片（带上时间维度标签）
        summary_card = build_report_card(ticker, date, final_state, decision, horizon_label)
        send_card(chat_id, summary_card)

        # 发送完整报告
        full_report = build_full_report_md(ticker, date, final_state, decision, horizon_label)
        clean_date = date.replace("-", "")
        send_long_text(chat_id, f"📄 {ticker} {horizon_label}完整报告", full_report)

    except Exception as e:
        logger.error(f"❌ 分析 {ticker} 失败: {e}")
        traceback.print_exc()
        error_card = build_error_card(ticker, str(e))
        send_card(chat_id, error_card)


def handle_message(event) -> None:
    """处理接收到的飞书消息"""
    try:
        msg = event.event.message
        chat_id = msg.chat_id
        content = json.loads(msg.content)
        text = content.get('text', '').strip()

        if not text:
            return

        logger.info(f"📩 收到消息: '{text[:100]}' (chat_id: {chat_id})")

        req = parse_request(text)

        if req["command"] == "switch_mode":
            global current_mode, config
            current_mode = req["mode"]
            config.update(ANALYSIS_MODES[current_mode])
            mode_names = {"fast": "⚡ 快速模式", "deep": "🧠 深度模式", "leap": "🏆 竞赛模式"}
            mode_desc = {
                "fast": "flash模型 + 1轮辩论，约1-2分钟",
                "deep": "pro模型 + 2轮辩论，约3-5分钟",
                "leap": "pro深度思考 + 多轮辩论 + 操作建议，约5-10分钟（质量优先）",
            }
            send_text(chat_id, f"{mode_names[current_mode]}\n\n{mode_desc[current_mode]}")
            return

        if req["command"] == "leap_analysis":
            # The Leap 竞赛批量分析：6 个加密标的全部走竞赛深度模式
            send_text(chat_id, (
                "🏆 **The Leap 竞赛标的批量分析**\n\n"
                "即将依次分析 6 个加密标的（竞赛深度模式）：\n"
                "1️⃣ BTC 比特币\n"
                "2️⃣ ETH 以太坊\n"
                "3️⃣ SOL\n"
                "4️⃣ LTC 莱特币\n"
                "5️⃣ XRP 瑞波\n"
                "6️⃣ DOGE 狗狗币\n\n"
                "⏳ 每个约 5-10 分钟，全部完成约 30-60 分钟，完成后逐个发送报告"
            ))
            date = datetime.date.today().strftime("%Y-%m-%d")
            for ticker, name in zip(LEAP_TICKERS, LEAP_TICKER_NAMES):
                send_card(chat_id, build_progress_card(ticker, date, "竞赛中线"))
                executor.submit(run_analysis_sync, chat_id, ticker, date, "medium", "leap")
            return

        if req["command"] == "help":
            send_card(chat_id, build_help_card())

        elif req["command"] == "methodology":
            send_text(chat_id, (
                "🔬 **TradingAgents 分析方法论**\n\n"
                "我用 **8 个 AI 角色**协作分析，模拟真实交易公司的决策流程：\n\n"
                "**第一层：4 位分析师独立研判**\n"
                "📈 市场技术分析师 — MACD、RSI、布林带等指标，判断趋势和超买超卖\n"
                "💬 社交情绪分析师 — Reddit/StockTwits 舆情，判断散户情绪\n"
                "📰 新闻宏观分析师 — 全球财经新闻、宏观事件影响\n"
                "📊 基本面分析师 — 财报、估值、盈利能力\n\n"
                "**第二层：多空辩论**\n"
                "🐂 多头研究员 vs 🐻 空头研究员 — 正反方辩论\n"
                "👨‍⚖️ Research Manager — 裁决定夺\n\n"
                "**第三层：风控辩论**\n"
                "🔥 激进型 vs 🛡️ 保守型 vs ⚖️ 中立型 — 三角辩论\n"
                "👨‍💼 Portfolio Manager — 最终决策\n\n"
                "**时间维度**\n"
                "🟢 短线 — 关注技术面、情绪、近期催化剂\n"
                "🟡 中线 — 技术面+基本面平衡\n"
                "🔵 长线 — 偏重基本面、估值、行业趋势\n\n"
                "用法举例：\n"
                "• 「帮我看看英伟达短线」→ 1-2分钟快速分析\n"
                "• 「NVDA 长期投资怎么样」→ 3-5分钟深度分析"
            ))

        elif req["command"] == "analyze" and req["ticker"]:
            ticker = req["ticker"]
            date = req["date"]
            horizon = req["horizon"]

            horizon_text = {"short": "短线", "medium": "中线", "long": "长线"}.get(horizon, "中线")

            # 发送进度提示
            send_card(chat_id, build_progress_card(ticker, date, horizon_text))

            # 后台分析
            executor.submit(run_analysis_sync, chat_id, ticker, date, horizon)

        else:
            # 帮用户尝试理解
            send_text(chat_id, (
                "🤔 没识别到股票代码，试试这些方式：\n\n"
                "📊 **股票**\n"
                "• 「分析 NVDA」或「NVDA 怎么样」\n"
                "• 「帮我看看特斯拉短线」\n"
                "• 「苹果长期投资怎么样」\n\n"
                "🪙 **加密货币**（币安数据）\n"
                "• 「BTC」、「ETH 短线」、「SOL 怎么样」\n"
                "• 「狗狗币」、「pepe」、「比特币长期」\n"
                "• 「黄金」→ PAXG（币安代币化黄金）\n\n"
                "📋 **更多**\n"
                "• 「帮助」→ 查看完整帮助\n"
                "• 「方法」→ 了解分析原理"
            ))

    except Exception as e:
        logger.error(f"处理消息异常: {e}")
        traceback.print_exc()


def main():
    """启动飞书机器人 WebSocket 连接"""
    logger.info("🔌 正在连接飞书 WebSocket...")

    # 构建事件处理器
    event_handler = (
        EventDispatcherHandlerBuilder(
            encrypt_key='',
            verification_token=VERIFICATION_TOKEN,
        )
        .register_p2_im_message_receive_v1(lambda e: handle_message(e))
        .build()
    )

    # 启动 WebSocket 连接
    ws_client = WsClient(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        event_handler=event_handler,
        auto_reconnect=True,
    )

    logger.info("✅ 飞书机器人已上线！在飞书群里 @机器人 发送股票代码即可")
    ws_client.start()

    # 保活：ws_client.start() 可能在后台线程运行，主线程必须保持活跃
    logger.info("🟢 主循环保活中...")
    while True:
        time.sleep(60)
        logger.debug("heartbeat")


if __name__ == "__main__":
    main()
