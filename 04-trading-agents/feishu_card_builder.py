"""
TradingAgents 飞书卡片消息构建器
将分析结果格式化为飞书卡片消息
"""

import datetime
import re
import textwrap
from typing import Dict, Any


def _truncate(text: str, max_chars: int = 5000) -> str:
    """截断过长的文本，保留关键信息"""
    if not text or len(text) <= max_chars:
        return text or "(无数据)"
    return text[:max_chars] + "\n\n..."


def _signal_color(decision: str) -> str:
    """根据交易信号返回卡片颜色"""
    decision_lower = (decision or "").lower()
    if decision_lower in ("buy", "overweight"):
        return "green"
    elif decision_lower in ("sell", "underweight"):
        return "red"
    else:
        return "orange"


def _signal_emoji(decision: str) -> str:
    """根据交易信号返回 emoji"""
    decision_lower = (decision or "").lower()
    emoji_map = {
        "buy": "🟢 强烈买入",
        "overweight": "🟢 增持",
        "hold": "🟡 持有",
        "underweight": "🔴 减持",
        "sell": "🔴 强烈卖出",
    }
    return emoji_map.get(decision_lower, f"⚪ {decision}")


def build_progress_card(ticker: str, date: str, horizon_label: str = "") -> Dict[str, Any]:
    """分析进行中的进度提示卡片"""
    horizon_line = f"\n**时间维度**: {horizon_label}" if horizon_label else ""
    return {
        "header": {
            "title": {"content": f"🔍 正在分析 {ticker.upper()}", "tag": "plain_text"},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": f"**分析日期**: {date}{horizon_line}\n**预计耗时**: 2-5 分钟\n\n正在调用多智能体分析引擎..."},
            {"tag": "hr"},
            {"tag": "markdown", "content": (
                "⏳ 8 个 AI 角色正在协作：\n"
                "📈 市场技术分析　💬 社交情绪分析\n"
                "📰 新闻宏观分析　📊 基本面分析\n"
                "🐂🐻 多空辩论　🛡️ 风控评估"
            )},
        ],
    }


def build_error_card(ticker: str, error_msg: str) -> Dict[str, Any]:
    """分析出错的提示卡片"""
    return {
        "header": {
            "title": {"content": f"❌ 分析失败 - {ticker.upper()}", "tag": "plain_text"},
            "template": "red",
        },
        "elements": [
            {"tag": "markdown", "content": f"**错误信息**:\n```\n{_truncate(str(error_msg), 600)}\n```"},
            {"tag": "hr"},
            {"tag": "markdown", "content": "💡 请检查：\n• 股票代码是否正确（如 NVDA, AAPL）\n• API Key 是否有效\n• 网络连接是否正常"},
        ],
    }


def build_report_card(
    ticker: str,
    date: str,
    final_state: Dict[str, Any],
    decision: str,
    horizon_label: str = "",
) -> Dict[str, Any]:
    """构建分析报告摘要卡片（简洁版，详情见富文本消息）"""
    elements = []

    meta = f"**股票**: {ticker.upper()}　|　**日期**: {date}"
    if horizon_label:
        meta += f"　|　**{horizon_label}**"
    meta += f"\n**分析时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    elements.append({"tag": "markdown", "content": meta})
    elements.append({"tag": "hr"})

    # 各分析师报告第一段摘要
    analyst_sections = [
        ("market_report", "📈 市场技术分析"),
        ("sentiment_report", "💬 社交情绪分析"),
        ("news_report", "📰 新闻宏观分析"),
        ("fundamentals_report", "📊 基本面分析"),
    ]

    for key, title in analyst_sections:
        content = final_state.get(key)
        if content:
            # 只取第一段作为摘要
            summary = str(content).split("\n\n")[0][:200]
            elements.append({"tag": "markdown", "content": f"**{title}**: {summary}"})

    elements.append({"tag": "hr"})

    # 最终决策
    decision_emoji = _signal_emoji(decision)
    elements.append({
        "tag": "markdown",
        "content": f"## 📊 最终交易信号: {decision_emoji}",
    })

    # 操作建议（入场/止损/止盈/仓位）
    plan = final_state.get("trader_investment_plan")
    if plan:
        plan_str = str(plan)
        op_lines = []
        for label in ("Action", "Entry Price", "Stop Loss", "Take Profit", "Position Sizing"):
            m = re.search(rf"\*\*{label}\*\*:?\s*([^\n]+)", plan_str)
            if m:
                value = m.group(1).strip()
                op_lines.append(f"**{label}**: {value}")
        if op_lines:
            elements.append({"tag": "markdown", "content": "## 🎯 操作建议\n" + "\n".join(op_lines)})

    # 底部
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": "📄 完整报告见下一条消息"}
    ]})

    return {
        "header": {
            "title": {"content": f"📊 {ticker.upper()} 分析报告", "tag": "plain_text"},
            "template": _signal_color(decision),
        },
        "elements": elements,
    }


def build_full_report_md(
    ticker: str,
    date: str,
    final_state: Dict[str, Any],
    decision: str,
    horizon_label: str = "",
) -> str:
    """构建完整分析报告 Markdown 文本"""
    lines = []
    lines.append(f"# 📊 {ticker.upper()} 完整分析报告")
    meta = f"**分析日期**: {date}"
    if horizon_label:
        meta += f"　|　**时间维度**: {horizon_label}"
    lines.append(meta)
    lines.append("")

    analyst_sections = [
        ("market_report", "## 📈 市场技术分析"),
        ("sentiment_report", "## 💬 社交情绪分析"),
        ("news_report", "## 📰 新闻宏观分析"),
        ("fundamentals_report", "## 📊 基本面分析"),
    ]

    for key, title in analyst_sections:
        content = final_state.get(key)
        if content:
            lines.append(title)
            lines.append("")
            lines.append(str(content))
            lines.append("")
            lines.append("---")
            lines.append("")

    # 研究团队辩论
    debate = final_state.get("investment_debate_state", {})
    if debate:
        lines.append("## 🏦 研究团队辩论")
        lines.append("")
        if debate.get("bull_history"):
            lines.append("### 🐂 多头研究员")
            lines.append(str(debate["bull_history"]))
            lines.append("")
        if debate.get("bear_history"):
            lines.append("### 🐻 空头研究员")
            lines.append(str(debate["bear_history"]))
            lines.append("")
        if debate.get("judge_decision"):
            lines.append("### 👨‍⚖️ Research Manager 裁决")
            lines.append(str(debate["judge_decision"]))
            lines.append("")
        lines.append("---")
        lines.append("")

    # 交易计划
    plan = final_state.get("trader_investment_plan")
    if plan:
        lines.append("## 📋 交易计划")
        lines.append("")
        lines.append(str(plan))
        lines.append("")
        lines.append("---")
        lines.append("")

    # 最终决策
    lines.append(f"## 📊 最终交易信号: {decision}")
    lines.append("")
    lines.append("> ⚠️ 以上分析由 AI 生成，不构成投资建议。请独立判断并承担风险。")

    return "\n".join(lines)


def build_help_card() -> Dict[str, Any]:
    """帮助信息卡片"""
    return {
        "header": {
            "title": {"content": "🤖 TradingAgents 机器人", "tag": "plain_text"},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": "**我是 AI 多智能体交易分析机器人**\n\n由 8+ 个专业 AI 角色协作分析股票：\n📈 市场分析师　💬 情绪分析师　📰 新闻分析师　📊 基本面分析师\n🐂 多头研究员　🐻 空头研究员　🛡️ 风控团队　👨‍💼 投资组合经理"},
            {"tag": "hr"},
            {"tag": "markdown", "content": (
                "**使用方法**\n\n"
                "• `分析 NVDA` — 分析今日股票\n"
                "• `分析 NVDA 2024-05-10` — 分析指定日期\n"
                "• `帮助` — 显示此消息\n\n"
                "**🏆 The Leap 竞赛功能**\n"
                "• `竞赛分析` — 批量深度分析 6 个竞赛标的（BTC/ETH/SOL/LTC/XRP/DOGE）\n"
                "• `竞赛模式` — 切换为深度思考+操作建议模式\n"
                "• 竞赛标的全自动使用深度模式，输出入场/止损/止盈/仓位\n\n"
                "**支持的市场**\n"
                "• 美股: NVDA, AAPL, TSLA...\n"
                "• 港股: 0700.HK, 9988.HK...\n"
                "• A股: 600519.SS, 000858.SZ...\n"
                "• 加密货币: BTC-USD, ETH-USD...\n"
                "• 国内期货: 沪金, 沪银"
            )},
        ],
    }
