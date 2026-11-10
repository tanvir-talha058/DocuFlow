@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   DocuFlow - Document Approval Workflow System
echo ============================================================
echo.

set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [error] Virtual environment not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

echo [run] Starting DocuFlow server on port 8002...
echo       Local URL:          http://127.0.0.1:8002
echo       Office Network URL: http://192.168.10.86:8002
echo.
echo       Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.

"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

pause
