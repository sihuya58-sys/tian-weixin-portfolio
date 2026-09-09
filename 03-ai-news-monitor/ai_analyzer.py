# ============================================================
# ai_analyzer.py - DeepSeek AI 分析模块
# ============================================================

import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DeepSeekAnalyzer:
    """DeepSeek AI 分析器：判断新闻是否对加密货币有重大影响"""

    def __init__(self, api_key, base_url, model, system_prompt, max_retries, db):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.db = db

    def analyze_news(self, title: str, content: str) -> Optional[Dict]:
        """使用 DeepSeek 分析新闻，判断是否是重大利好/利空"""

        user_prompt = f"标题：{title}\n\n内容：{content[:500]}"

        for attempt in range(self.max_retries):
            try:
                logger.info(f'[AI] DeepSeek 分析中（第 {attempt + 1}/{self.max_retries} 次）：{title[:50]}...')

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 150,
                    },
                    timeout=30,
                )

                if response.status_code != 200:
                    logger.warning(f'[!] 第 {attempt + 1} 次请求失败 HTTP {response.status_code}：{response.text[:200]}')

                    if response.status_code == 429:
                        logger.error('[X] DeepSeek API 速率限制，等待后重试...')

                    if attempt < self.max_retries - 1:
                        import time
                        wait_time = (attempt + 1) * 2
                        logger.info(f'[时钟] {wait_time} 秒后重试...')
                        time.sleep(wait_time)
                    continue

                data = response.json()
                analysis_text = data["choices"][0]["message"]["content"].strip()

                if not analysis_text:
                    logger.info(f'[跳过] DeepSeek 判定为无关紧要，忽略：{title[:50]}')
                    return None

                result = self._parse_analysis(analysis_text)

                if result:
                    logger.info(f'[OK] 分析完成 - 标的：{result["token"]}，属性：{result["type"]}')
                    return result
                else:
                    logger.info(f'[跳过] DeepSeek 返回无效格式，认定为无关紧要')
                    return None

            except requests.Timeout:
                logger.warning(f'[!] 第 {attempt + 1} 次请求超时')
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep((attempt + 1) * 2)
            except Exception as e:
                logger.warning(f'[!] 第 {attempt + 1} 次尝试失败：{e}')

                if attempt < self.max_retries - 1:
                    import time
                    wait_time = (attempt + 1) * 2
                    logger.info(f'[时钟] {wait_time} 秒后重试...')
                    time.sleep(wait_time)

        logger.error(f'[X] DeepSeek 分析失败（已重试 {self.max_retries} 次）')
        return None

    def _parse_analysis(self, analysis_text: str) -> Optional[Dict]:
        """解析 DeepSeek 的结构化输出"""
        try:
            lines = analysis_text.strip().split('\n')
            result = {}

            for line in lines:
                if '标的：' in line:
                    result['token'] = line.split('：')[-1].strip().upper()
                elif '属性：' in line:
                    attr = line.split('：')[-1].strip()
                    if '利好' in attr:
                        result['type'] = '利好'
                    elif '利空' in attr:
                        result['type'] = '利空'
                elif '理由：' in line:
                    result['reason'] = line.split('：')[-1].strip()

            if result.get('token') and result.get('type'):
                return result
            else:
                return None

        except Exception as e:
            logger.debug(f'[!] 解析 DeepSeek 输出失败：{e}')
            return None

    def analyze_multiple_articles(self, articles: list) -> list:
        """批量分析多篇文章，返回有重大影响的结果"""
        results = []

        for article in articles:
            analysis = self.analyze_news(
                title=article.get('title', ''),
                content=article.get('summary', '')
            )

            if analysis:
                analysis['article_guid'] = article['guid']
                analysis['article_title'] = article['title']
                analysis['article_link'] = article['link']
                results.append(analysis)

                self.db.update_push_status(
                    article['guid'],
                    'success',
                    f"{analysis['token']} - {analysis['type']}"
                )
            else:
                self.db.update_push_status(article['guid'], 'filtered')

        return results
