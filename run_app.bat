@echo off
title KPR Food Court Launcher
echo =================================================================
echo   Starting KPR AI-Powered College Food Court System
echo =================================================================
echo.

:: 1. Launch Backend in a new dedicated terminal
echo [1/2] Launching Flask Backend API on http://127.0.0.1:5000 ...
start "KPR Food Court - Backend API (:5000)" cmd /k "cd /d %~dp0backend && python app.py"

:: 2. Launch Frontend in a new dedicated terminal
echo [2/2] Launching Frontend Server on http://127.0.0.1:5500 ...
start "KPR Food Court - Frontend Portal (:5500)" cmd /k "cd /d %~dp0 && python -m http.server 5500 --directory frontend"

timeout /t 3 >nul

echo.
echo =================================================================
echo   Both services are now running!
echo.
echo   - Customer Portal:  http://127.0.0.1:5500/index.html
echo   - Vendor Portal:    http://127.0.0.1:5500/pages/vendor/login.html
echo   - Admin Portal:     http://127.0.0.1:5500/pages/admin/login.html
echo   - Backend API:      http://127.0.0.1:5000/api/health
echo =================================================================
echo.

:: Automatically open browser
start http://127.0.0.1:5500/index.html
