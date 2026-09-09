# ============================================================
# config.py - 配置文件
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# ============ API 密钥配置 ============
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
PUSHDEER_PUSHKEY = os.getenv('PUSHDEER_PUSHKEY', '')

# ============ DeepSeek API 配置 ============
DEEPSEEK_BASE_URL = 'https://api.deepseek.com/v1'
DEEPSEEK_MODEL = 'deepseek-chat'

# ============ RSS 源配置 ============
RSS_SOURCES = [
    'https://feeds.coindesk.com/news',
    'https://feeds.coindesk.com/prices',
    'https://cryptoslate.com/feed/',
    'https://blockworks.co/feed/',
]


# ============ 代理配置 ============
# 从 .env 读取代理设置（HTTP_PROXY / HTTPS_PROXY）
def get_proxies():
    """构建 requests 可用的代理字典"""
    proxies = {}
    http_proxy = os.getenv('HTTP_PROXY', '')
    https_proxy = os.getenv('HTTPS_PROXY', '')
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    return proxies if proxies else None

# ============ 轮询配置 ============
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '60'))  # 轮询间隔（秒）
MAX_RETRIES = 3  # API 请求失败重试次数
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))  # HTTP 请求超时（秒）



# ============ 本地存储配置 ============
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / 'crypto_news.db'  # SQLite 数据库路径
LOG_PATH = DATA_DIR / 'news_filter.log'  # 日志文件路径

# ============ DeepSeek AI 系统提示词 ============
DEEPSEEK_SYSTEM_PROMPT = """你是一位顶级加密货币交易员。请冷酷、客观地分析这段新闻。

如果该新闻对特定代币（如 BTC, ETH, SOL, ADA, XRP 等）有直接且重大的【利好】或【利空】影响，请输出以下格式：
---
标的：[代币名称或代币简称，如 BTC、ETH、SOL]
属性：[利好 或 利空]
理由：[一句话精简说明，不超过30字]
---

如果属于无用噪音、行业八卦、或影响轻微的新闻，请直接忽略，不要输出任何内容。

**重要**：只有当你有明确、高置信度的判断时才输出。保持冷静和客观。"""

# ============ 推送渠道配置 ============
PUSH_CHANNEL = os.getenv('PUSH_CHANNEL', 'telegram')  # 'telegram' 或 'pushdeer'

# ============ 验证配置 ============
def validate_config():
    """检查必要的配置是否已设置"""
    errors = []

    if not DEEPSEEK_API_KEY:
        errors.append('X DEEPSEEK_API_KEY 未设置')

    if PUSH_CHANNEL == 'telegram':
        if not TELEGRAM_BOT_TOKEN:
            errors.append('X TELEGRAM_BOT_TOKEN 未设置')
        if not TELEGRAM_CHAT_ID:
            errors.append('X TELEGRAM_CHAT_ID 未设置')
    elif PUSH_CHANNEL == 'pushdeer':
        if not PUSHDEER_PUSHKEY:
            errors.append('X PUSHDEER_PUSHKEY 未设置')

    if errors:
        print('\n'.join(errors))
        return False

    return True


if __name__ == '__main__':
    # 测试配置
    print('配置检查结果：')
    if validate_config():
        print('[OK] 所有必需配置已正确设置')
        print(f'   RSS 源数量：{len(RSS_SOURCES)}')
        print(f'   轮询间隔：{POLL_INTERVAL} 秒')
        print(f'   推送渠道：{PUSH_CHANNEL}')
    else:
        print('[!] 请先配置必要的 API 密钥')
