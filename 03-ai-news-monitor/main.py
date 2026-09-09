# ============================================================
# main.py - 主程序
# ============================================================
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import time
import logging
import signal
import sys
from datetime import datetime

# ======== Windows GBK 控制台兼容性修复 ========
# Windows 终端默认 GBK 编码不支持 Emoji（🚀✅🔗等），
# 打印日志时抛出 UnicodeEncodeError→程序静默崩溃→完全无输出
# 方案：用一个自定义 Handler 在输出前替换 Emoji 为普通文字
import re

_EMOJI_MAP = {
    '🚀': '[火箭]', '✅': '[OK]', '❌': '[X]', '🔗': '[链接]',
    '📰': '[新闻]', '📲': '[推送]', '📊': '[图表]', '📋': '[列表]',
    '📭': '[空]', '📝': '[记录]', '🔍': '[搜索]', '🔕': '[静音]',
    '⏰': '[时钟]', '⏳': '[等待]', '⚙️': '[设置]', '💰': '[币]',
    '🎯': '[目标]', '🎬': '[开始]', '🤖': '[AI]', '💡': '[提示]',
    '⏹️': '[停止]', '🔄': '[循环]', '⏭️': '[跳过]', '💬': '[评论]',
    '─': '-', '🔬': '[测试]', '🌐': '[网络]', '📉': '[跌]',
    '👇': '[指下]', '👆': '[指上]', 'ℹ️': '[信息]', '🚨': '[警报]',
}
_EMOJI_RE = re.compile('[\U0001F300-\U0001FFFF\U0000FE0F\u2600-\u27BF]+')

def _safe_log_msg(msg):
    for emoji, text in _EMOJI_MAP.items():
        msg = msg.replace(emoji, text)
    return _EMOJI_RE.sub('', msg)






import config
from storage import NewsDatabase
from rss_crawler import RSScrawler
from ai_analyzer import DeepSeekAnalyzer
from push_sender import PushSender

# 配置日志（先清空避免重复）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# 用 Emoji-safe 的自定义 Handler 替换默认的 StreamHandler
for handler in logging.root.handlers[:]:
    if isinstance(handler, logging.StreamHandler):
        logging.root.removeHandler(handler)

class SafeConsoleHandler(logging.StreamHandler):
    """将日志中的 Emoji 替换为安全文字，避免 GBK 编码崩溃"""
    def emit(self, record):
        record.msg = _safe_log_msg(record.msg)
        super().emit(record)
        self.flush()

safe_handler = SafeConsoleHandler()
safe_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.root.addHandler(safe_handler)

logger = logging.getLogger(__name__)



class CryptoNewsFilterSystem:
    """加密货币新闻智能过滤与推送系统主程序"""
    
    def __init__(self):
        self.running = True
        self.poll_count = 0
        self.total_articles = 0
        self.total_alerts = 0
        
        # 初始化各模块
        self.db = NewsDatabase(config.DB_PATH)
        self.crawler = RSScrawler(config.RSS_SOURCES, config.REQUEST_TIMEOUT, self.db)
        self.analyzer = DeepSeekAnalyzer(
            config.DEEPSEEK_API_KEY,
            config.DEEPSEEK_BASE_URL,
            config.DEEPSEEK_MODEL,
            config.DEEPSEEK_SYSTEM_PROMPT,
            config.MAX_RETRIES,
            self.db
        )
        self.sender = PushSender(
            config.PUSH_CHANNEL,
            config.TELEGRAM_BOT_TOKEN,
            config.TELEGRAM_CHAT_ID,
            config.PUSHDEER_PUSHKEY
        )
        
        # 注册信号处理（Ctrl+C 优雅退出）
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info('\n⏹️ 收到关闭信号，正在清理...')
        self.running = False
        self.print_stats()
        sys.exit(0)
    
    def run(self):
        """启动主循环"""
        logger.info('=' * 60)
        logger.info('🚀 加密货币新闻智能过滤与推送系统启动')
        logger.info('=' * 60)
        
        # 检查配置
        if not config.validate_config():
            logger.error('❌ 配置检查失败，请先设置必要的 API 密钥')
            sys.exit(1)
        
        logger.info(f'⚙️ 轮询间隔：{config.POLL_INTERVAL} 秒')
        logger.info(f'📋 RSS 源数量：{len(config.RSS_SOURCES)} 个')
        logger.info(f'📲 推送渠道：{config.PUSH_CHANNEL}')
        
        # 启动主循环
        while self.running:
            try:
                self.poll_once()
                
                # 等待下一轮
                logger.info(f'⏳ 等待 {config.POLL_INTERVAL} 秒后进行下一轮轮询...\n')
                time.sleep(config.POLL_INTERVAL)
            
            except KeyboardInterrupt:
                self._handle_shutdown(None, None)
            except Exception as e:
                logger.error(f'❌ 主循环异常：{e}')
                logger.info(f'⏳ {config.POLL_INTERVAL} 秒后重试...\n')
                time.sleep(config.POLL_INTERVAL)
    
    def poll_once(self):
        """执行一次完整的轮询 → 分析 → 推送流程"""
        
        self.poll_count += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f'─' * 60)
        logger.info(f'🔄 第 {self.poll_count} 轮轮询开始 [{timestamp}]')
        logger.info(f'─' * 60)
        
        # 第一步：抓取新闻
        articles = self.crawler.get_latest_news(max_articles=10)
        
        if not articles:
            logger.info('📭 本轮没有新文章\n')
            return
        
        self.total_articles += len(articles)
        logger.info(f'📰 获取 {len(articles)} 篇新文章，开始分析...\n')
        
        # 第二步：AI 分析
        analysis_results = self.analyzer.analyze_multiple_articles(articles)
        
        if not analysis_results:
            logger.info('🔕 本轮没有发现重大利好/利空信息\n')
            return
        
        logger.info(f'🎯 发现 {len(analysis_results)} 条重大新闻\n')
        
        # 第三步：推送警报
        logger.info('📲 开始推送警报...')
        self.sender.send_batch_alerts(analysis_results)
        
        self.total_alerts += len(analysis_results)
        logger.info(f'✅ 本轮轮询完成\n')
    
    def print_stats(self):
        """打印运行统计"""
        db_stats = self.db.get_stats()
        push_stats = self.sender.get_stats()
        
        logger.info('\n' + '=' * 60)
        logger.info('📊 运行统计')
        logger.info('=' * 60)
        logger.info(f'轮询次数：{self.poll_count}')
        logger.info(f'处理文章总数：{self.total_articles}')
        logger.info(f'成功推送警报：{self.total_alerts}')
        logger.info(f'推送成功率：{push_stats["success"]} / {push_stats["total"]}')
        logger.info(f'数据库记录总数：{db_stats["total"]}')
        logger.info('=' * 60 + '\n')


def main():
    """程序入口"""
    system = CryptoNewsFilterSystem()
    system.run()


if __name__ == '__main__':
    main()
