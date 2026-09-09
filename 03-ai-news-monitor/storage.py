# ============================================================
# storage.py - 本地存储模块
# ============================================================

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class NewsDatabase:
    """SQLite 数据库管理：记录已处理的新闻 GUID + 历史分析库"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 新闻记录表：存储已处理的新闻
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    link TEXT,
                    published_time TEXT,
                    processed_time TEXT,
                    push_status TEXT DEFAULT 'pending',
                    gemini_analysis TEXT
                )
            ''')
            
            # 新表：历史分析库（用于查询历史同类新闻的价格反应）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin TEXT NOT NULL,
                    event_title TEXT NOT NULL,
                    event_category TEXT,
                    analyzed_at TEXT NOT NULL,
                    ai_result TEXT NOT NULL,
                    technical_notes TEXT,
                    sentiment TEXT,
                    impact_level TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f'✅ 数据库初始化成功：{self.db_path}')
        except Exception as e:
            logger.error(f'❌ 数据库初始化失败：{e}')
            raise
    
    def is_processed(self, guid):
        """检查新闻是否已处理过"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM news_items WHERE guid = ?', (guid,))
            result = cursor.fetchone()[0]
            conn.close()
            
            return result > 0
        except Exception as e:
            logger.error(f'❌ 数据库查询失败：{e}')
            return False
    
    def add_news_item(self, guid, title, link, published_time):
        """记录新闻项目"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO news_items (guid, title, link, published_time, processed_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (guid, title, link, published_time, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            logger.debug(f'📝 新闻已记录：{title[:50]}...')
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f'❌ 插入数据库失败：{e}')
            return False
    
    def update_push_status(self, guid, status, analysis_result=None):
        """更新新闻的推送状态和分析结果"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            if analysis_result:
                cursor.execute('''
                    UPDATE news_items 
                    SET push_status = ?, gemini_analysis = ?
                    WHERE guid = ?
                ''', (status, analysis_result, guid))
            else:
                cursor.execute('''
                    UPDATE news_items 
                    SET push_status = ?
                    WHERE guid = ?
                ''', (status, guid))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f'❌ 更新推送状态失败：{e}')
    
    def get_stats(self):
        """获取统计信息"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM news_items')
            total_items = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM news_items WHERE push_status = ?', ('success',))
            pushed_items = cursor.fetchone()[0]
            
            conn.close()
            
            return {'total': total_items, 'pushed': pushed_items}
        except Exception as e:
            logger.error(f'❌ 获取统计信息失败：{e}')
            return {'total': 0, 'pushed': 0}
