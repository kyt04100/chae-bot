@echo off
REM One-click launcher for chae-bot. Double-click this file to start the local server.
REM Press Ctrl+C in this window (or close it) to stop the server.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run setup first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -e .[ingest,web]
    pause
    exit /b 1
)

echo starting chae-bot at http://127.0.0.1:8000 ...
echo.
.venv\Scripts\python.exe -m research_bot.cli serve
pause
