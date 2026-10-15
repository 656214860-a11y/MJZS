@echo off
chcp 65001 >nul
rem 测试模式：提示弹窗自动确认（只写状态栏，不阻塞等待手动点「确定」）
set DRAMA_AUTO_CONFIRM=1
start "" "%~dp0运行环境\Python\pythonw.exe" -I "%~dp0启动漫剧制作助手.pyw"
