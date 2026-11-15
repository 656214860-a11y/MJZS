@echo off
rem 夜间全量自检计划任务安装/卸载：每日 03:30 对干净树 .wt/ci 跑 run_selftests --all --safe。
rem 由 T1 任务书第 4 项要求；auto_full_safe.py --run 是唯一实现（与 post-commit 补跑同一条链路）。
rem 用法：install_nightly_task.cmd [install^|uninstall]（默认 install）
setlocal
set "TASK=ManjuNightlyFullSafe"
set "ROOT=%~dp0..\..\.."
set "PYW=%ROOT%运行环境\Python\pythonw.exe"
set "SCRIPT=%ROOT%程序\scripts\auto_full_safe.py"
set "PROG=%ROOT%程序"
if not exist "%PYW%" (echo [nightly] 缺少解释器 %PYW%& exit /b 2)
if not exist "%SCRIPT%" (echo [nightly] 缺少脚本 %SCRIPT%& exit /b 2)
if /i "%~1"=="uninstall" goto :uninstall
schtasks /create /tn "%TASK%" /sc daily /st 03:30 /f /tr "cmd /c cd /d \"%PROG%\" && \"%PYW%\" -B scripts\auto_full_safe.py --run"
if errorlevel 1 (echo [nightly] schtasks 创建失败& exit /b 1)
echo [nightly] 已注册 %TASK%：每日 03:30 跑 auto_full_safe --run（错过不补跑，下个欠账触发点覆盖）
schtasks /query /tn "%TASK%" /fo list | findstr /i "TaskName Next"
goto :eof
:uninstall
schtasks /delete /tn "%TASK%" /f
if errorlevel 1 (echo [nightly] 删除失败& exit /b 1)
echo [nightly] 已删除 %TASK%
