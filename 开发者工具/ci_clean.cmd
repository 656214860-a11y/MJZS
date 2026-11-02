@echo off
rem Full safe selftest on a clean detached worktree (.wt\ci) of HEAD, using the bundled python.
setlocal
set "PY="
set "PROG="
for /d %%D in ("%~dp0..\*") do if exist "%%D\Python\python.exe" set "PY=%%D\Python\python.exe"
for /d %%D in ("%~dp0..\.wt\ci\*") do if exist "%%D\smoke_test.py" set "PROG=%%D"
if not defined PY exit /b 2
if not defined PROG exit /b 2
set "DRAMA_SUPPRESS_MODAL=1"
rem worktree created from another account: trust it for this run only (command-line scope config)
set "GIT_CONFIG_COUNT=1"
set "GIT_CONFIG_KEY_0=safe.directory"
set "GIT_CONFIG_VALUE_0=*"
"%PY%" -B "%PROG%\scripts\local_ci.py" full
exit /b %ERRORLEVEL%
