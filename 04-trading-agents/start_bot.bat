@echo off
chcp 65001 >nul
title TradingAgents 飞书
cd /d "C:\Users\弹猫的吉他\Desktop\TradingAgents-main"
echo 启动中...
"%~dp0.venv\Scripts\python.exe" -u feishu_bot.py
pause
