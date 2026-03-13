@echo off

:: ── Check for Python 3 ────────────────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python not found. Opening download page...
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to tick "Add Python to PATH" during installation.
    echo After installing, close this window and double-click run_windows.bat again.
    start https://www.python.org/downloads/
    pause
    exit /b
)

:: ── Run the client ─────────────────────────────────────────────────────────
python "%~dp0client.py"
pause
