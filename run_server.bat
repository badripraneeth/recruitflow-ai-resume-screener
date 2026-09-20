@echo off
title RecruitFlow Server
echo ====================================================
echo  Starting RecruitFlow - AI Resume Screener
echo ====================================================
echo.

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    echo [OK] Using virtual environment .venv
    set "PY_EXE=.venv\Scripts\python.exe"
) ELSE (
    echo [OK] Using system Python
    set "PY_EXE=python"
)

echo [OK] Verifying Django configuration...
%PY_EXE% manage.py check
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] System check failed. Please check the error above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ====================================================
echo  Server is starting!
echo  Open your browser at: http://127.0.0.1:8000/
echo  Press Ctrl+C to stop.
echo ====================================================
echo.

%PY_EXE% manage.py runserver 127.0.0.1:8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server stopped with error.
    pause
)
