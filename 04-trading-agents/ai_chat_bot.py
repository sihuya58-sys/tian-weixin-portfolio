"""
AI 飞书助手 — 通用 AI 聊天 + TradingAgents 8-agent 深度股票分析
电脑开机自动后台运行，手机飞书随时用
"""

import concurrent.futures
import datetime
import json
import logging
import os
import re
import sys
import tempfile
import traceback
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

import lark_oapi as lark
from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

# ---- 日志 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("ai_bot")

# ---- 配置 ----
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 代理
PROXY_URL = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or "http://127.0.0.1:9567"
os.environ["HTTP_PROXY"] = PROXY_URL
os.environ["HTTPS_PROXY"] = PROXY_URL

if not APP_ID or not APP_SECRET:
    logger.error("❌ 请在 .env 中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    sys.exit(1)

if not DEEPSEEK_KEY:
    logger.error("❌ 请在 .env 中配置 DEEPSEEK_API_KEY")
    sys.exit(1)

# ---- AI 客户端（通用聊天）----
ai_client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
CHAT_MODEL = "deepseek-v4-pro"

# ---- TradingAgents（深度股票分析）----
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

TA_CONFIG = DEFAULT_CONFIG.copy()
TA_CONFIG["llm_provider"] = "deepseek"
TA_CONFIG["deep_think_llm"] = "deepseek-v4-pro"
TA_CONFIG["quick_think_llm"] = "deepseek-v4-flash"
TA_CONFIG["output_language"] = "Chinese"
TA_CONFIG["max_debate_rounds"] = 2
TA_CONFIG["max_risk_discuss_rounds"] = 2

# ---- 飞书客户端 ----
feishu_client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.WARNING) \
    .build()

# ---- 对话记忆 ----
conversations: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 20

# ---- 股票名称映射 ----
STOCK_NAMES = {
    "苹果": "AAPL", "特斯拉": "TSLA", "英伟达": "NVDA", "微软": "MSFT",
    "谷歌": "GOOGL", "亚马逊": "AMZN", "meta": "META", "茅台": "600519.SS",
    "腾讯": "0700.HK", "阿里": "9988.HK", "比亚迪": "002594.SZ",
    "黄金": "GLD", "比特币": "BTC-USD", "以太坊": "ETH-USD",
    "amd": "AMD", "英特尔": "INTC", "奈飞": "NFLX", "台积电": "TSM",
}

# ---- 线程池 ----
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ---- 系统提示词（通用聊天）----
SYSTEM_PROMPT = """你是飞书群里的 AI 助手「小T」。你很聪明，简洁直接。

注意：如果用户提到股票名称或代码，另一个股票分析引擎会自动启动进行深度分析。你只负责非股票的通用问题。

风格：默认中文，简洁，代码可运行。"""


def send_text(chat_id: str, text: str) -> None:
    """发送文本消息"""
    try:
        content = json.dumps({"text": text}, ensure_ascii=False)
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
            ).build()
        feishu_client.im.v1.message.create(request)
    except Exception as e:
        logger.error(f"发送失败: {e}")


def detect_ticker(text: str) -> str | None:
    """从自然语言中提取股票代码"""
    # 先检查中文名
    for name, code in STOCK_NAMES.items():
        if name.lower() in text.lower():
            return code
    # 正则匹配大写代码
    matches = re.findall(r'\b([A-Z]{1,5}(?:\.[A-Za-z]{2})?)\b', text)
    skip = {'I', 'A', 'IS', 'IT', 'AT', 'OK', 'US', 'NO', 'AI', 'ETF', 'CEO', 'API', 'USD', 'GDP', 'IPO'}
    for m in matches:
        if m.upper() not in skip and len(m) >= 2:
            return m.upper()
    return None


def is_stock_question(text: str) -> bool:
    """判断是否是股票分析相关的问题"""
    keywords = ['分析', '股票', '走势', '行情', '涨', '跌', '买入', '卖出',
                '持仓', '仓位', '短线', '长线', '中线', '投资', '交易', 'K线',
                '技术面', '基本面', '财报', '估值', '龙头', '板块']
    ticker = detect_ticker(text)
    return ticker is not None or any(kw in text for kw in keywords)


def run_stock_analysis(chat_id: str, ticker: str, user_text: str) -> None:
    """后台运行 TradingAgents 8-agent 深度分析"""
    try:
        today = datetime.date.today().strftime("%Y-%m-%d")
        # 尝试提取日期
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', user_text)
        analysis_date = date_match.group(1) if date_match else today

        logger.info(f"📊 TradingAgents 分析: {ticker} ({analysis_date})")

        # 告知用户
        send_text(chat_id, (
            f"🔬 启动深度分析引擎 — {ticker}\n\n"
            f"8 个 AI 角色正在协作：\n"
            f"📈 市场技术分析　💬 社交情绪分析\n"
            f"📰 新闻宏观分析　📊 基本面分析\n"
            f"🐂🐻 多空辩论　🛡️ 风控辩论\n"
            f"👨‍💼 投资组合经理最终决策\n\n"
            f"⏳ 预计 3-5 分钟，请稍候..."
        ))

        graph = TradingAgentsGraph(config=TA_CONFIG, debug=False)
        final_state, decision = graph.propagate(ticker, analysis_date)

        # 构建报告
        report_lines = [f"# 📊 {ticker} 深度分析报告"]
        report_lines.append(f"**日期**: {analysis_date}")
        report_lines.append(f"**最终决策**: {decision}")
        report_lines.append("")

        sections = [
            ("market_report", "📈 市场技术分析"),
            ("sentiment_report", "💬 社交情绪分析"),
            ("news_report", "📰 新闻宏观分析"),
            ("fundamentals_report", "📊 基本面分析"),
        ]
        for key, title in sections:
            content = final_state.get(key, "")
            if content:
                report_lines.append(f"## {title}")
                report_lines.append(str(content))
                report_lines.append("")

        # 辩论结果
        debate = final_state.get("investment_debate_state", {})
        if debate.get("judge_decision"):
            report_lines.append("## 🏦 研究团队裁决")
            report_lines.append(str(debate["judge_decision"]))
            report_lines.append("")

        # 交易计划
        plan = final_state.get("trader_investment_plan", "")
        if plan:
            report_lines.append("## 📋 交易计划")
            report_lines.append(str(plan))
            report_lines.append("")

        report_lines.append(f"---")
        report_lines.append(f"## 最终信号: **{decision}**")
        report_lines.append("> ⚠️ AI 生成，不构成投资建议")

        report = "\n".join(report_lines)

        # 分段发送
        MAX_LEN = 20000
        parts = [report[i:i+MAX_LEN] for i in range(0, len(report), MAX_LEN)]
        for i, part in enumerate(parts):
            label = f"📄 {ticker} 深度报告" + (f" ({i+1}/{len(parts)})" if len(parts) > 1 else "")
            text_json = json.dumps({"text": f"{label}\n\n{part}"}, ensure_ascii=False)
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("text").content(text_json).build()).build()
            feishu_client.im.v1.message.create(request)

        logger.info(f"✅ 深度分析完成: {ticker} → {decision}")

    except Exception as e:
        logger.error(f"分析失败: {e}")
        traceback.print_exc()
        send_text(chat_id, f"❌ 分析 {ticker} 失败: {str(e)[:100]}")


def chat_with_ai(chat_id: str, user_msg: str) -> str:
    """调用 DeepSeek 通用对话"""
    try:
        history = conversations[chat_id]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-MAX_HISTORY:])
        messages.append({"role": "user", "content": user_msg})

        response = ai_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )

        reply = response.choices[0].message.content.strip()

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY * 2:
            conversations[chat_id] = history[-MAX_HISTORY * 2:]

        return reply

    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        return f"😵 出错了: {str(e)[:50]}"


def handle_message(event) -> None:
    """处理飞书消息 — 自动区分通用聊天 vs 深度股票分析"""
    try:
        msg = event.event.message
        chat_id = msg.chat_id
        content = json.loads(msg.content)
        text = content.get('text', '').strip()

        text = re.sub(r'@\S+\s*', '', text).strip()
        if not text:
            return

        logger.info(f"📩 [{chat_id[-8:]}] {text[:80]}")

        # ---- 在线检测 ----
        if text.lower() in ('在吗', '在不在', '在线吗', 'ping', '活着吗', '还在吗', 'hi', 'hello', '你好', '嗨'):
            send_text(chat_id, f"👋 在呢！{datetime.datetime.now().strftime('%H:%M:%S')} 起在线。\n\n💬 随便聊天\n📊 提到股票 → 自动 8-agent 深度分析")
            return

        # ---- 清空记忆 ----
        if text in ('清空记忆', '清除记忆', '忘记', '重置'):
            conversations[chat_id] = []
            send_text(chat_id, "🧹 记忆已清空")
            return

        # ---- 股票分析 → TradingAgents 深度分析 ----
        ticker = detect_ticker(text)
        if ticker:
            executor.submit(run_stock_analysis, chat_id, ticker, text)
            return

        # ---- 通用聊天 ----
        reply = chat_with_ai(chat_id, text)
        send_text(chat_id, reply)

    except Exception as e:
        logger.error(f"消息处理异常: {e}")
        traceback.print_exc()


def main():
    logger.info(f"🤖 小T AI 助手启动中...")
    logger.info(f"   模型: DeepSeek {CHAT_MODEL}")
    logger.info(f"   App ID: {APP_ID[:8]}***")

    event_handler = (
        EventDispatcherHandlerBuilder(
            encrypt_key='',
            verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
        )
        .register_p2_im_message_receive_v1(lambda e: handle_message(e))
        .build()
    )

    ws_client = WsClient(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        event_handler=event_handler,
        auto_reconnect=True,
    )

    logger.info("✅ 小T 已上线！在飞书群里 @我 试试「在吗」")
    ws_client.start()


if __name__ == "__main__":
    main()
