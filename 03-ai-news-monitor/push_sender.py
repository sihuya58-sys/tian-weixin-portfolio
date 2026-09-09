# ============================================================
# push_sender.py - 推送模块
# ============================================================

import requests
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PushSender:
    """推送服务：发送到 Telegram 或 PushDeer"""
    
    def __init__(self, channel, telegram_token, telegram_chat_id, pushdeer_key):
        self.channel = channel
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.pushdeer_key = pushdeer_key
        self.success_count = 0
        self.fail_count = 0
    
    def send_alert(self, analysis_result: Dict) -> bool:
        """发送单条警报到用户手机"""
        message = self._format_message(analysis_result)
        link = analysis_result.get('article_link', '')
        
        if self.channel == 'telegram':
            return self._send_telegram(message, link)
        elif self.channel == 'pushdeer':
            return self._send_pushdeer(message)
        else:
            logger.error(f'❌ 未知推送渠道：{self.channel}')
            return False
    
    def send_batch_alerts(self, results: List[Dict]) -> bool:
        """批量发送多条警报"""
        if not results:
            logger.info('📭 没有需要推送的结果')
            return True
        
        all_success = True
        for result in results:
            success = self.send_alert(result)
            if success:
                self.success_count += 1
            else:
                self.fail_count += 1
                all_success = False
        
        logger.info(f'📊 推送统计 - 成功：{self.success_count}，失败：{self.fail_count}')
        return all_success
    
    def _format_message(self, analysis_result: Dict) -> str:
        """格式化推送消息"""
        token = analysis_result.get('token', '').upper()
        alert_type = analysis_result.get('type', '')
        reason = analysis_result.get('reason', '')
        title = analysis_result.get('article_title', '')
        
        emoji = '🚀' if alert_type == '利好' else '📉'
        
        message = f'{emoji} {token} - {alert_type}\n'
        message += f'📰 {title}\n'
        message += f'💡 {reason}'
        
        return message
    
    def _send_telegram(self, message: str, link: str = '') -> bool:
        """通过 Telegram Bot 发送消息"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error('❌ 未配置 Telegram 密钥')
            return False
        
        try:
            url = f'https://api.telegram.org/bot{self.telegram_token}/sendMessage'
            
            text = message
            if link:
                text += f'\n\n[🔗 查看原文]({link})'
            
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': False,
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f'✅ Telegram 推送成功')
                return True
            else:
                logger.error(f'❌ Telegram 推送失败：{response.text}')
                return False
        
        except Exception as e:
            logger.error(f'❌ Telegram 推送异常：{e}')
            return False
    
    def _send_pushdeer(self, message: str) -> bool:
        """通过 PushDeer 发送消息"""
        if not self.pushdeer_key:
            logger.error('❌ 未配置 PushDeer 密钥')
            return False
        
        try:
            url = 'https://api2.pushdeer.com/message/push'
            
            payload = {
                'pushkey': self.pushdeer_key,
                'text': '加密新闻警报',
                'content': message,
                'type': 'markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    logger.info(f'✅ PushDeer 推送成功')
                    return True
            
            logger.error(f'❌ PushDeer 推送失败：{response.text}')
            return False
        
        except Exception as e:
            logger.error(f'❌ PushDeer 推送异常：{e}')
            return False
    
    def get_stats(self) -> Dict:
        """获取推送统计"""
        return {
            'success': self.success_count,
            'failed': self.fail_count,
            'total': self.success_count + self.fail_count
        }
