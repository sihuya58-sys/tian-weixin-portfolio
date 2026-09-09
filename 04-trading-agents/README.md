# 交易分析 Agents(基于 TradingAgents 二次开发)

> **一句话简介**：基于开源多智能体交易分析框架 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 二次开发,接入国产大模型与中国市场数据源,封装成飞书机器人 / 网页界面,手机上随时发起多智能体深度分析。

## 背景

原版 TradingAgents 框架用 LangGraph 编排多个 AI 角色(分析师、研究员、交易员、风控)协作产出投资决策,但面向海外市场:默认 OpenAI/Gemini 模型、美股数据源,国内使用门槛高。本项目在保留原框架多智能体协作架构的基础上做本地化改造,并封装成日常可用的工具形态。

## 做了什么

- **接入国产大模型**:支持 DeepSeek 等 OpenAI 兼容协议的 LLM,通过环境变量切换提供商
- **新增中国商品期货数据源**:基于 akshare / 新浪财经,支持上期所、大商所、郑商所期货日 K 数据
- **扩展加密货币资产模式**:支持 Binance / CoinGecko 等加密资产数据
- **三个使用入口**:
  - `ai_chat_bot.py` — 飞书 AI 助手:自然语言识别股票代码与意图,后台自动跑 8 角色深度分析并组装报告
  - `feishu_bot.py` — 飞书机器人:WebSocket 长连接,无需公网 IP,本地即可运行
  - `web.py` — Gradio Web 界面,可自由选择分析师组合
- **报告自动化**:分析结果自动组装为 Markdown 报告,飞书卡片分步推送进度与结论

## 成果数据

- 8 个 AI 角色协作:4 分析师(市场/情绪/新闻/基本面)+ 多空辩论 + 风控辩论 + 投资组合经理最终决策
- 一轮完整深度分析约 3-5 分钟,全程自动运行,结果推送到手机
- 保留原框架的辩论机制:多空研究员辩论 + 三风格风控分析师辩论,组合经理综合裁决

## 技术栈

- LangGraph(多智能体状态图编排)
- Python / LangChain
- DeepSeek API(OpenAI 兼容协议)
- 飞书开放平台(lark-oapi,WebSocket 长连接)
- Gradio(Web 界面)
- akshare / yfinance(中国期货 + 美股数据)

## 如何运行

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 .env(参考 .env.example)
#    必填:FEISHU_APP_ID / FEISHU_APP_SECRET / DEEPSEEK_API_KEY

# 3. 启动(任选其一)
python ai_chat_bot.py   # 飞书 AI 助手(推荐,自然语言发起分析)
python web.py           # Gradio Web 界面
```

飞书机器人使用前需在[飞书开放平台](https://open.feishu.cn/)创建自建应用并开启机器人能力。

## 声明

本项目基于开源项目 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)(Apache-2.0 协议)二次开发,新增功能包括:国产大模型接入、中国商品期货数据源、加密货币资产模式、飞书机器人/网页入口、报告组装与卡片推送。原项目 LICENSE 见 `LICENSE` 文件。

## 作者

田伟鑫 | 榆林大学储能科学与工程 2027 届 | 邮箱：17392130590@163.com
