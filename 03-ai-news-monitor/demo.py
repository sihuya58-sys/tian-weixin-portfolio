#!/usr/bin/env python3
# ============================================================
# demo.py - 演示模式：展示系统效果（使用模拟数据）
# ============================================================
# 用途：不需要真实 API 调用，直接展示系统能做什么
# 用法：python demo.py

import json
from datetime import datetime

def print_header(title):
    print(f'\n{"=" * 60}')
    print(f'  {title}')
    print(f'{"=" * 60}\n')

def demo_rss_crawler():
    """演示 RSS 爬虫效果"""
    print_header('📰 RSS 爬虫演示 - 模拟抓取新闻')
    
    # 模拟从 RSS 源抓取的文章
    articles = [
        {
            'guid': 'coindesk-2024-01-18-1',
            'title': '美国 SEC 批准现货比特币 ETF，机构投资者看好',
            'link': 'https://coindesk.com/policy-politics/2024/01/10/bitcoin-spot-etf-sec-approval/',
            'summary': '美国证券交易委员会（SEC）今日宣布，正式批准首批现货比特币交易所交易基金（ETF）。这被行业认为是加密货币走向主流的标志性事件...',
            'published_time': '2024-01-18T10:30:00Z'
        },
        {
            'guid': 'coindesk-2024-01-18-2',
            'title': '以太坊伦敦升级推迟至 Q2，开发者讨论分片方案',
            'link': 'https://coindesk.com/tech/2024/01/17/ethereum/',
            'summary': '以太坊核心开发者在最新会议中决定推迟伦敦升级的时间表，同时加快推进分片（sharding）的开发进度...',
            'published_time': '2024-01-18T09:15:00Z'
        },
        {
            'guid': 'coindesk-2024-01-18-3',
            'title': '币安与英国金融监管部门达成协议，获准继续运营',
            'link': 'https://coindesk.com/business/2024/01/18/binance-uk/',
            'summary': '币安已与英国金融行为监管局（FCA）达成关键协议，允许其在英国继续提供服务...',
            'published_time': '2024-01-18T08:45:00Z'
        },
    ]
    
    print(f'🔗 正在抓取 RSS 源：https://feeds.coindesk.com/news')
    print(f'✅ 成功抓取 {len(articles)} 篇新文章\n')
    
    for i, article in enumerate(articles, 1):
        print(f'[{i}] 📄 {article["title"]}')
        print(f'    🔗 {article["link"][:60]}...')
        print(f'    ⏰ {article["published_time"]}\n')
    
    return articles

def demo_ai_analyzer(articles):
    """演示 AI 分析效果"""
    print_header('🤖 DeepSeek AI 分析演示 - 判断利好/利空')
    
    # 模拟 DeepSeek 的分析结果
    analysis_results = [
        {
            'article_title': articles[0]['title'],
            'article_link': articles[0]['link'],
            'token': 'BTC',
            'type': '利好',
            'reason': 'SEC 批准现货 ETF，机构资金入场，大幅利好比特币生态'
        },
        {
            'article_title': articles[1]['title'],
            'article_link': articles[1]['link'],
            'token': 'ETH',
            'type': '利好',
            'reason': '加速推进分片方案，提升以太坊扩容能力，长期利好'
        },
        # 第三篇新闻被过滤（不是重大影响）
    ]
    
    print('分析进度：\n')
    
    for i, article in enumerate(articles, 1):
        print(f'🤖 分析第 {i} 篇：{article["title"][:40]}...')
        
        # 找到该文章对应的分析结果
        matching = next((a for a in analysis_results if a['article_title'] == article['title']), None)
        
        if matching:
            print(f'   ✅ 分析完成 - 标的：{matching["token"]}，属性：{matching["type"]}')
            print(f'   💡 理由：{matching["reason"]}\n')
        else:
            print(f'   ⏭️ 判定为无关紧要（噪音），已过滤\n')
    
    print(f'🎯 本轮共发现 {len(analysis_results)} 条重大新闻\n')
    return analysis_results

def demo_push_sender(analysis_results):
    """演示推送效果"""
    print_header('📲 Telegram 推送演示 - 推送到手机')
    
    print('推送消息：\n')
    
    for i, result in enumerate(analysis_results, 1):
        # 选择 emoji
        emoji = '🚀' if result['type'] == '利好' else '📉'
        
        message = f'{emoji} {result["token"]} - {result["type"]}\n'
        message += f'📰 {result["article_title"]}\n'
        message += f'💡 {result["reason"]}\n'
        message += f'[🔗 查看原文]({result["article_link"]})'
        
        print(f'[推送 {i}/{len(analysis_results)}]')
        print('─' * 50)
        print(message)
        print('─' * 50)
        print(f'✅ 已推送到 Telegram\n')

def demo_database_stats():
    """演示数据库统计"""
    print_header('📊 数据库统计信息')
    
    stats = {
        '总新闻数': 125,
        '已推送数': 18,
        '已过滤数': 107,
        '今日新闻': 3,
        '今日推送': 2,
        '数据库大小': '2.3 MB',
        '运行时长': '3 天 5 小时'
    }
    
    print('| 指标 | 数值 |')
    print('|------|------|')
    for key, value in stats.items():
        print(f'| {key} | {value} |')
    print()

def demo_timeline():
    """展示完整工作流时间线"""
    print_header('⏱️ 工作流程时间线')
    
    timeline = [
        ('10:00:00', 'RSS 轮询开始', '抓取 CoinDesk 等源'),
        ('10:00:05', 'RSS 解析完成', '发现 3 篇新文章'),
        ('10:00:08', 'SQLite 去重', '2 篇已推送，1 篇重复'),
        ('10:00:10', 'DeepSeek 分析开始', '发送到 AI 进行判断'),
        ('10:00:15', 'AI 分析完成', '识别 2 条重大新闻'),
        ('10:00:16', 'Telegram 推送', '已推送到用户手机'),
        ('10:00:17', '轮询完成', '存储到数据库'),
        ('10:01:00', '等待下一轮', '60 秒后再次轮询'),
    ]
    
    for time, action, details in timeline:
        print(f'⏰ {time}  |  {action:<15} →  {details}')
    
    print()

def main():
    print('\n')
    print('🎬 加密货币新闻智能过滤与推送系统 - 完整演示')
    print('=' * 60)
    print('本演示使用模拟数据，展示系统的完整工作流程\n')
    
    # 第一步：RSS 爬虫
    articles = demo_rss_crawler()
    
    # 第二步：AI 分析
    analysis_results = demo_ai_analyzer(articles)
    
    # 第三步：推送
    demo_push_sender(analysis_results)
    
    # 数据库统计
    demo_database_stats()
    
    # 时间线
    demo_timeline()
    
    # 总结
    print_header('✨ 演示总结')
    print('✅ RSS 爬虫：成功抓取新闻')
    print('✅ AI 甄别：准确识别重要信息')
    print('✅ 推送系统：实时通知用户')
    print('✅ 数据库：持久化存储数据')
    print()
    print('🚀 准备好开始真实运行了吗？')
    print('   运行命令：python main.py')
    print()

if __name__ == '__main__':
    main()
