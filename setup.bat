@echo off
title DeepSeek Monitor - Setup

echo ============================================
echo   DeepSeek Monitor - Setup
echo ============================================
echo.

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ first:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)
python --version
echo.
echo Starting installation...
echo.
python "%~dp0install.py"
pause
