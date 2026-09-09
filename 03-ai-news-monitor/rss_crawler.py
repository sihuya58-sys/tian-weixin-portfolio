# ============================================================
# rss_crawler.py - RSS 爬虫模块（Python 3.14 兼容版本）
# ============================================================
# 使用 xml.etree.ElementTree 原生解析 RSS，完全放弃 feedparser
# 这样避免了 cgi 模块依赖，完全兼容 Python 3.14+

import os
import requests
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from typing import List, Dict
from html import unescape

logger = logging.getLogger(__name__)


class RSScrawler:
    """RSS 爬虫：使用 XML 原生解析 RSS 源，兼容 Python 3.14"""
    
    def __init__(self, rss_sources, request_timeout, db):
        self.rss_sources = rss_sources
        self.timeout = request_timeout
        self.db = db

        # 代理配置
        self.proxies = {}
        http_proxy = os.getenv('HTTP_PROXY', '')
        https_proxy = os.getenv('HTTPS_PROXY', '')
        if http_proxy:
            self.proxies['http'] = http_proxy
        if https_proxy:
            self.proxies['https'] = https_proxy

        # 定义 XML 命名空间
        self.namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        }
    
    def fetch_feed(self, rss_url: str) -> List[Dict]:
        """
        抓取单个 RSS 源，返回新文章列表
        使用 requests 获取 XML 内容，用 ElementTree 解析
        """
        try:
            logger.info(f'🔗 正在抓取：{rss_url}')
            
            # 使用 requests 获取 RSS 源内容
            response = requests.get(rss_url, timeout=self.timeout, proxies=self.proxies if self.proxies else None)
            response.encoding = 'utf-8'  # 强制 UTF-8 编码
            
            if response.status_code != 200:
                logger.error(f'❌ HTTP 错误：{response.status_code}')
                return []
            
            # 解析 XML
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f'❌ XML 解析错误：{e}')
                return []
            
            articles = []
            
            # RSS 2.0 格式
            items = root.findall('.//item')
            if not items:
                # Atom 格式
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items:
                article = self._parse_entry(item)
                if article:
                    articles.append(article)
            
            logger.info(f'✅ 成功抓取 {len(articles)} 篇新文章')
            return articles
        
        except requests.ConnectionError as e:
            err_str = str(e)
            if '远程主机强迫关闭' in err_str or 'Connection reset' in err_str:
                logger.error(f'❌ 连接被远程主机重置（可能被网络封锁）：{rss_url}')
            elif '连接尝试失败' in err_str or 'Connection refused' in err_str:
                logger.error(f'❌ 连接被拒绝（DNS 或网络问题）：{rss_url}')
            else:
                logger.error(f'❌ 网络连接失败：{rss_url} - {type(e).__name__}')
            return []
        except requests.Timeout:
            logger.error(f'⏰ 请求超时（{self.timeout}秒）：{rss_url}')
            return []
        except requests.RequestException as e:
            logger.error(f'❌ 网络请求失败：{rss_url} - {e}')
            return []
        except Exception as e:
            logger.error(f'❌ RSS 抓取异常：{rss_url} - {type(e).__name__}: {e}')
            return []
    
    def _parse_entry(self, item) -> Dict:
        """
        解析 RSS 条目，提取关键信息
        同时支持 RSS 2.0 和 Atom 格式
        """
        try:
            # 支持 RSS 2.0 和 Atom 格式
            title = self._get_text(item, './title', './/{http://www.w3.org/2005/Atom}title')
            link = self._get_text(item, './link', './/{http://www.w3.org/2005/Atom}link/@href')
            
            # 对于 Atom，link 可能是属性
            if not link:
                link_elem = item.find('.//{http://www.w3.org/2005/Atom}link')
                if link_elem is not None:
                    link = link_elem.get('href', '')
            
            guid = self._get_text(item, './guid', './/{http://www.w3.org/2005/Atom}id')
            if not guid:
                guid = link  # 如果没有 GUID，用 link 作为唯一标识
            
            if not guid:
                return None
            
            # 检查是否已处理过
            if self.db.is_processed(guid):
                return None
            
            # 提取摘要/内容
            summary = self._get_text(item, './description', './/{http://www.w3.org/2005/Atom}summary')
            
            # 如果没有摘要，尝试用 content:encoded
            if not summary:
                summary = self._get_text(
                    item,
                    './/{http://purl.org/rss/1.0/modules/content/}encoded',
                    './/{http://www.w3.org/2005/Atom}content'
                )
            
            # HTML 转义字符解码
            if summary:
                summary = unescape(summary)
                # 移除 HTML 标签
                summary = self._strip_html_tags(summary)
            
            # 发布时间
            pub_time = self._get_text(item, './pubDate', './/{http://www.w3.org/2005/Atom}published')
            if not pub_time:
                pub_time = datetime.now().isoformat()
            
            # 内容有效性检查
            if len(title) < 5:
                logger.debug(f'⏭️ 标题过短，跳过：{title[:30]}')
                return None
            
            if len(summary) < 20:
                logger.debug(f'⏭️ 摘要过短，跳过：{title[:30]}')
                return None
            
            # 构建文章信息
            article = {
                'guid': guid,
                'title': title,
                'link': link,
                'summary': summary[:500],  # 限制摘要长度
                'published_time': pub_time,
            }
            
            # 记录到数据库
            self.db.add_news_item(
                article['guid'],
                article['title'],
                article['link'],
                article['published_time']
            )
            
            return article
        
        except Exception as e:
            logger.error(f'❌ 解析条目失败：{e}')
            return None
    
    def _get_text(self, element, *paths: str) -> str:
        """
        获取 XML 元素文本，支持多个路径尝试
        路径以 @ 结尾表示属性，如 './link/@href'
        """
        for path in paths:
            if not path:
                continue
            
            try:
                # 处理属性路径 (如 ./link/@href)
                if '@' in path:
                    path_base, attr = path.rsplit('@', 1)
                    elem = element.find(path_base.rstrip('/'))
                    if elem is not None:
                        text = elem.get(attr, '').strip()
                        if text:
                            return text
                else:
                    # 处理元素文本
                    elem = element.find(path)
                    if elem is not None:
                        text = (elem.text or '').strip()
                        if text:
                            return text
            except Exception:
                continue
        
        return ''
    
    def _strip_html_tags(self, text: str) -> str:
        """
        简单的 HTML 标签剥离
        移除常见的 HTML 标签，保留纯文本
        """
        import re
        
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def fetch_all_feeds(self) -> List[Dict]:
        """抓取所有 RSS 源的最新文章"""
        all_articles = []
        
        for rss_url in self.rss_sources:
            articles = self.fetch_feed(rss_url)
            all_articles.extend(articles)
        
        logger.info(f'📰 本轮共抓取 {len(all_articles)} 篇新文章需要分析')
        return all_articles
    
    def get_latest_news(self, max_articles=10) -> List[Dict]:
        """获取最新的新闻文章"""
        all_articles = self.fetch_all_feeds()
        return all_articles[:max_articles]
