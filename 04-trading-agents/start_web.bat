@echo off
title TradingAgents Web 分析
cd /d "%~dp0"
echo ================================
echo   TradingAgents 8-Agent 分析
echo ================================
echo.
echo 浏览器打开 http://127.0.0.1:7860
echo 这个窗口不要关！
echo.
python -u web.py
pause
