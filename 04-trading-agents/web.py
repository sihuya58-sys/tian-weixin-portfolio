"""
TradingAgents Web Interface
使用 Gradio 构建的 Web 界面，支持 DeepSeek 等 LLM 提供商
"""

import datetime
import time
import threading
from pathlib import Path
from typing import Generator

import gradio as gr
from dotenv import load_dotenv

# Load .env first
load_dotenv(Path(__file__).parent / ".env")

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# ---- 配置 ----
ANALYST_CHOICES = ["market", "social", "news", "fundamentals"]
ANALYST_LABELS = {
    "market": "📈 市场分析师 (Market)",
    "social": "💬 社交媒体分析师 (Sentiment)",
    "news": "📰 新闻分析师 (News)",
    "fundamentals": "📊 基本面分析师 (Fundamentals)",
}

# ---- 核心分析函数 ----
def run_analysis(
    ticker: str,
    analysis_date: str,
    selected_analysts: list,
    research_depth: int,
    deep_model: str,
    quick_model: str,
    language: str,
    progress=gr.Progress(),
) -> Generator[dict, None, dict]:
    """
    运行 TradingAgents 分析，yield 进度更新，最终返回完整报告。
    """
    # 构建配置
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "deepseek"
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    config["max_debate_rounds"] = research_depth
    config["max_risk_discuss_rounds"] = research_depth
    config["output_language"] = language

    # 将 analyst 标签转为 key
    analyst_map_reverse = {
        "📈 市场分析师 (Market)": "market",
        "💬 社交媒体分析师 (Sentiment)": "social",
        "📰 新闻分析师 (News)": "news",
        "📊 基本面分析师 (Fundamentals)": "fundamentals",
    }
    analyst_keys = [analyst_map_reverse.get(a, a) for a in selected_analysts]

    progress(0.05, desc="初始化分析引擎...")

    # 创建图
    graph = TradingAgentsGraph(
        selected_analysts=analyst_keys,
        config=config,
        debug=True,
    )

    progress(0.10, desc="连接 DeepSeek API...")

    # 获取 instrument 上下文
    instrument_context = graph.resolve_instrument_context(ticker, "stock")
    init_state = graph.propagator.create_initial_state(
        ticker, analysis_date, asset_type="stock", instrument_context=instrument_context
    )
    args = graph.propagator.get_graph_args()

    progress(0.15, desc="分析中...")

    # 流式执行
    trace = []
    agent_statuses = {}
    report_updates = []

    for chunk in graph.graph.stream(init_state, **args):
        trace.append(chunk)

        # 检测当前进度
        for key in [
            "market_report", "sentiment_report", "news_report",
            "fundamentals_report", "investment_plan", "trader_investment_plan",
            "final_trade_decision",
        ]:
            if chunk.get(key):
                label_map = {
                    "market_report": "📈 市场分析",
                    "sentiment_report": "💬 社交情绪分析",
                    "news_report": "📰 新闻分析",
                    "fundamentals_report": "📊 基本面分析",
                    "investment_plan": "🏦 研究团队决策",
                    "trader_investment_plan": "📋 交易计划",
                    "final_trade_decision": "✅ 最终决策",
                }
                status = label_map.get(key, key)
                progress_val = min(0.15 + 0.10 * len(trace), 0.95)
                progress(progress_val, desc=f"完成: {status}")
                report_updates.append(f"✅ {status}")

    # 合并最终状态
    final_state = {}
    for chunk in trace:
        final_state.update(chunk)

    decision = graph.process_signal(final_state.get("final_trade_decision", ""))

    progress(1.0, desc="分析完成!")

    # 构建报告
    report_html = build_report_html(ticker, analysis_date, final_state, decision, report_updates)
    return report_html


def build_report_html(ticker, date, state, decision, updates):
    """构建 HTML 格式的报告"""
    sections = []

    # Header
    sections.append(f"""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 30px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
        <h1 style="color: #00d4ff; margin: 0;">🔍 {ticker} 分析报告</h1>
        <p style="color: #888; margin: 10px 0 0 0;">分析日期: {date} | 提供商: DeepSeek |
           生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """)

    # 进度摘要
    if updates:
        sections.append("""
        <div style="background: #0d1b2a; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="color: #00d4ff; margin-top: 0;">📋 分析进度</h3>
            <ul style="color: #ccc; line-height: 2;">
        """)
        for u in updates:
            sections.append(f"<li>{u}</li>")
        sections.append("</ul></div>")

    # 分析师报告
    analyst_sections = [
        ("market_report", "📈 市场分析"),
        ("sentiment_report", "💬 社交情绪分析"),
        ("news_report", "📰 新闻分析"),
        ("fundamentals_report", "📊 基本面分析"),
    ]
    for key, title in analyst_sections:
        content = state.get(key)
        if content:
            sections.append(f"""
            <div style="background: #1b2838; padding: 25px; border-radius: 10px;
                        margin-bottom: 15px; border-left: 4px solid #00d4ff;">
                <h2 style="color: #00d4ff; margin-top: 0;">{title}</h2>
                <div style="color: #ddd; line-height: 1.8; white-space: pre-wrap;">{content}</div>
            </div>
            """)

    # 研究团队决策
    debate = state.get("investment_debate_state", {})
    if debate:
        parts = []
        if debate.get("bull_history"):
            parts.append(f"""
            <div style="background: #1a3a1a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #4caf50;">🐂 Bull Researcher（多头）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{debate["bull_history"]}</pre>
            </div>""")
        if debate.get("bear_history"):
            parts.append(f"""
            <div style="background: #3a1a1a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #f44336;">🐻 Bear Researcher（空头）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{debate["bear_history"]}</pre>
            </div>""")
        if debate.get("judge_decision"):
            parts.append(f"""
            <div style="background: #1a1a3a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #ff9800;">👨‍⚖️ Research Manager（裁决）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{debate["judge_decision"]}</pre>
            </div>""")
        if parts:
            sections.append(f"""
            <div style="background: #1b2838; padding: 25px; border-radius: 10px;
                        margin-bottom: 15px; border-left: 4px solid #ff9800;">
                <h2 style="color: #ff9800; margin-top: 0;">🏦 研究团队辩论</h2>
                {"".join(parts)}
            </div>""")

    # 交易计划
    if state.get("trader_investment_plan"):
        sections.append(f"""
        <div style="background: #1b2838; padding: 25px; border-radius: 10px;
                    margin-bottom: 15px; border-left: 4px solid #9c27b0;">
            <h2 style="color: #9c27b0; margin-top: 0;">📋 交易计划</h2>
            <pre style="color: #ddd; white-space: pre-wrap;">{state["trader_investment_plan"]}</pre>
        </div>""")

    # 风险讨论
    risk = state.get("risk_debate_state", {})
    if risk:
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_parts.append(f"""
            <div style="background: #3a2a1a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #ff5722;">🔥 Aggressive（激进）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{risk["aggressive_history"]}</pre>
            </div>""")
        if risk.get("conservative_history"):
            risk_parts.append(f"""
            <div style="background: #1a2a1a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #4caf50;">🛡️ Conservative（保守）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{risk["conservative_history"]}</pre>
            </div>""")
        if risk.get("neutral_history"):
            risk_parts.append(f"""
            <div style="background: #1a1a2a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #2196f3;">⚖️ Neutral（中立）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{risk["neutral_history"]}</pre>
            </div>""")
        if risk.get("judge_decision"):
            risk_parts.append(f"""
            <div style="background: #1a1a3a; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <h4 style="color: #ff9800;">👨‍💼 Portfolio Manager（最终决策）</h4>
                <pre style="color: #ddd; white-space: pre-wrap;">{risk["judge_decision"]}</pre>
            </div>""")
        if risk_parts:
            sections.append(f"""
            <div style="background: #1b2838; padding: 25px; border-radius: 10px;
                        margin-bottom: 15px; border-left: 4px solid #ff5722;">
                <h2 style="color: #ff5722; margin-top: 0;">⚡ 风险管理讨论</h2>
                {"".join(risk_parts)}
            </div>""")

    # 最终决策
    sections.append(f"""
    <div style="background: linear-gradient(135deg, #0d3b0d 0%, #1a5c1a 100%);
                padding: 30px; border-radius: 15px; margin-top: 20px; text-align: center;">
        <h1 style="color: #4caf50; margin: 0;">📊 最终交易信号</h1>
        <p style="color: #fff; font-size: 24px; margin: 15px 0;">{decision}</p>
    </div>
    """)

    return "".join(sections)


# ---- Gradio UI ----
def create_ui():
    with gr.Blocks(title="TradingAgents - AI 股票分析") as demo:
        gr.HTML("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #1a1a2e, #16213e);
                    border-radius: 15px; margin-bottom: 20px;">
            <h1 style="color: #00d4ff; font-size: 36px; margin: 0;">🤖 TradingAgents</h1>
            <p style="color: #888; font-size: 16px;">Multi-Agent LLM 金融交易分析框架 | Powered by DeepSeek</p>
        </div>
        """)

        with gr.Row():
            # 左侧：输入
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ 分析设置")

                ticker = gr.Textbox(
                    label="📌 股票代码",
                    value="NVDA",
                    placeholder="例如: NVDA, AAPL, 0700.HK, BTC-USD",
                )

                analysis_date = gr.Textbox(
                    label="📅 分析日期",
                    value=datetime.datetime.now().strftime("%Y-%m-%d"),
                    placeholder="YYYY-MM-DD",
                )

                analysts = gr.CheckboxGroup(
                    label="🔬 选择分析师",
                    choices=list(ANALYST_LABELS.values()),
                    value=list(ANALYST_LABELS.values()),  # 全选
                )

                research_depth = gr.Slider(
                    label="🔍 研究深度（辩论轮数）",
                    minimum=1,
                    maximum=3,
                    value=1,
                    step=1,
                )

                deep_model = gr.Dropdown(
                    label="🧠 深度思考模型",
                    choices=["deepseek-v4-pro", "deepseek-reasoner", "deepseek-chat"],
                    value="deepseek-v4-pro",
                )

                quick_model = gr.Dropdown(
                    label="⚡ 快速思考模型",
                    choices=["deepseek-v4-flash", "deepseek-chat"],
                    value="deepseek-v4-flash",
                )

                language = gr.Dropdown(
                    label="🌐 输出语言",
                    choices=["English", "Chinese"],
                    value="Chinese",
                )

                run_btn = gr.Button("🚀 开始分析", variant="primary", size="lg")

            # 右侧：输出
            with gr.Column(scale=2):
                gr.Markdown("### 📊 分析报告")
                output = gr.HTML(
                    value="""
                    <div style="text-align: center; padding: 80px 20px; color: #666;">
                        <h2 style="font-size: 48px;">🤖</h2>
                        <p style="font-size: 18px;">填写左侧参数，点击「开始分析」</p>
                        <p style="font-size: 14px; color: #444;">分析过程约需 2-5 分钟</p>
                    </div>
                    """
                )

        # Events
        run_btn.click(
            fn=run_analysis,
            inputs=[ticker, analysis_date, analysts, research_depth, deep_model, quick_model, language],
            outputs=output,
        )

        gr.Markdown("""
        ---
        <div style="text-align: center; color: #666; font-size: 12px;">
            Built with <a href="https://github.com/TauricResearch/TradingAgents" target="_blank">TradingAgents</a>
            | Powered by DeepSeek | Web UI by Gradio
        </div>
        """)

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
    )
