@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start_ignis.py %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python start_ignis.py %*
  exit /b %errorlevel%
)

where python3 >nul 2>nul
if %errorlevel%==0 (
  python3 start_ignis.py %*
  exit /b %errorlevel%
)

echo.
echo [IGNIS] ERROR: Python 3.10+ was not found.
echo Install Python from https://www.python.org/downloads/ or use Docker.
pause
exit /b 1
