"""
极简飞书 AI 助手 — 只用 DeepSeek，不需要任何外部数据源
双击 simple_bot.bat 启动
"""
import datetime, json, logging, os, re, sys, traceback
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from openai import OpenAI
import lark_oapi as lark
from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bot")

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

if not all([APP_ID, APP_SECRET, DEEPSEEK_KEY]):
    logger.error("请配置 .env: FEISHU_APP_ID, FEISHU_APP_SECRET, DEEPSEEK_API_KEY")
    sys.exit(1)

ai = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
feishu = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).log_level(lark.LogLevel.WARNING).build()
memory: dict[str, list] = defaultdict(list)

STOCK_SYSTEM = """你是专业股票分析师。用户问到任何股票，请从以下维度分析：

1. **基本面** — 公司业务、财报、估值
2. **技术面** — 近期趋势、关键价位
3. **情绪面** — 市场情绪、新闻影响
4. **风险** — 主要风险因素
5. **结论** — 给出明确的多空判断和理由

简洁专业，控制在 800 字内。结尾加 ⚠️ 不构成投资建议。"""

CHAT_SYSTEM = "你是飞书群 AI 助手「小T」。聪明、简洁、直接。中文回复。"


def send(chat_id: str, text: str):
    try:
        c = json.dumps({"text": text}, ensure_ascii=False)
        req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(
            CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("text").content(c).build()).build()
        feishu.im.v1.message.create(req)
    except Exception as e:
        logger.error(f"发送失败: {e}")


def ask_ai(chat_id: str, msg: str, system: str) -> str:
    try:
        hist = memory[chat_id]
        msgs = [{"role": "system", "content": system}]
        msgs.extend(hist[-20:])
        msgs.append({"role": "user", "content": msg})

        resp = ai.chat.completions.create(model="deepseek-v4-pro", messages=msgs, temperature=0.7, max_tokens=3000)
        reply = resp.choices[0].message.content.strip()

        hist.append({"role": "user", "content": msg})
        hist.append({"role": "assistant", "content": reply})
        if len(hist) > 40:
            memory[chat_id] = hist[-40:]
        return reply
    except Exception as e:
        return f"出错了: {e}"


def on_message(event):
    try:
        msg = event.event.message
        chat_id = msg.chat_id
        text = json.loads(msg.content).get("text", "").strip()
        text = re.sub(r'@\S+\s*', '', text).strip()
        if not text:
            return

        logger.info(f"[{chat_id[-6:]}] {text[:60]}")

        # 在线检测
        if text in ('在吗','ping','hi','hello','你好','嗨'):
            send(chat_id, f"👋 在呢！{datetime.datetime.now():%H:%M:%S} 起在线")
            return

        # 清空记忆
        if text in ('清空记忆','忘记','重置'):
            memory[chat_id] = []
            send(chat_id, "🧹 已清空")
            return

        # 判断是否股票问题
        is_stock = bool(re.search(r'[A-Z]{2,5}|股票|走势|行情|涨跌|买入|卖出|投资|分析|短线|长线', text))
        system = STOCK_SYSTEM if is_stock else CHAT_SYSTEM

        reply = ask_ai(chat_id, text, system)
        send(chat_id, reply)

    except Exception as e:
        logger.error(f"异常: {e}")


def main():
    logger.info("🚀 小T 启动中...")
    handler = EventDispatcherHandlerBuilder(encrypt_key='', verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN","")) \
        .register_p2_im_message_receive_v1(on_message).build()
    ws = WsClient(app_id=APP_ID, app_secret=APP_SECRET, event_handler=handler, auto_reconnect=True)
    logger.info("✅ 已上线！飞书群发「在吗」测试")
    ws.start()


if __name__ == "__main__":
    main()
