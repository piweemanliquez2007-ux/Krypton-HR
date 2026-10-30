@echo off
title HR & Payroll System - HTTPS Launcher
color 0b

echo ========================================================
echo        STARTING ENTERPRISE HR & PAYROLL SYSTEM (HTTPS)
echo ========================================================
echo.

:: Detect folder structure - the script is in hr-payroll-system/ and backend/frontend
:: are in hr-payroll-system/hr-payroll-system/
set "BASE_DIR=%~dp0"
if exist "%BASE_DIR%hr-payroll-system\backend" (
    set "BACKEND_DIR=%BASE_DIR%hr-payroll-system\backend"
    set "FRONTEND_DIR=%BASE_DIR%hr-payroll-system\frontend"
) else if exist "%BASE_DIR%backend" (
    set "BACKEND_DIR=%BASE_DIR%backend"
    set "FRONTEND_DIR=%BASE_DIR%frontend"
) else (
    echo [ERROR] Could not locate backend or frontend folders!
    echo         Expected at: %BASE_DIR%hr-payroll-system\backend
    echo         Or: %BASE_DIR%backend
    pause
    exit /b 1
)

echo [INFO] Backend: %BACKEND_DIR%
echo [INFO] Frontend: %FRONTEND_DIR%
echo.

:: Check for certificate files in backend folder
set "CERT_FILE=%BACKEND_DIR%\cert.pem"
set "KEY_FILE=%BACKEND_DIR%\key.pem"
if not exist "%CERT_FILE%" (
    echo [ERROR] cert.pem not found in backend folder!
    echo         Run: openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
    echo         in the backend folder first.
    pause
    exit /b 1
)
if not exist "%KEY_FILE%" (
    echo [ERROR] key.pem not found in backend folder!
    pause
    exit /b 1
)

:: Check for virtual environment
if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at %BACKEND_DIR%\venv\Scripts\python.exe
    echo         Run: cd "%BACKEND_DIR%" && python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: 1. Launch FastAPI backend over HTTPS on port 8000
echo [1/3] Starting FastAPI Backend on https://localhost:8000 ...
start "HR Backend API (HTTPS 8000)" cmd /k "cd /d "%BACKEND_DIR%" && "%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --ssl-keyfile "%KEY_FILE%" --ssl-certfile "%CERT_FILE%""

:: 2. Launch frontend over HTTPS on port 5173
echo [2/3] Starting Frontend Server on https://localhost:5173 ...
start "HR Frontend (HTTPS 5173)" cmd /k "cd /d "%FRONTEND_DIR%" && python serve_https.py 5173 "%CERT_FILE%" "%KEY_FILE%""

:: 3. Wait and open browser
echo [3/3] Opening system in your default browser...
timeout /t 3 /nobreak >nul
start https://localhost:5173

echo.
echo ========================================================
echo   SUCCESS! System is now running (HTTPS):
echo   - Frontend: https://localhost:5173
echo   - API Docs: https://localhost:8000/docs
echo   - Health:   https://localhost:8000/health
echo ========================================================
echo.
echo (Keep the two opened command windows running to use the app)
pause