@echo off
rem Local CI launcher (R1428, roadmap G). ASCII only: no chcp, so Tcl/Tk keeps the system code page.
rem Unattended variant: never pauses. Usage: double-click, or "local_ci quick" for smoke + gate only. Add "nopause" for unattended runs.
setlocal
set "PY="
set "PROG="
for /d %%D in ("%~dp0*") do (
  if exist "%%D\Python\python.exe" set "PY=%%D\Python\python.exe"
  if exist "%%D\smoke_test.py" set "PROG=%%D"
)
if not defined PY (echo [CI] bundled python not found & exit /b 2)
if not defined PROG (echo [CI] program folder not found & exit /b 2)
set "DRAMA_SUPPRESS_MODAL=1"
"%PY%" -B "%PROG%\scripts\local_ci.py" targets
set "RC=%ERRORLEVEL%"
exit /b %RC%
