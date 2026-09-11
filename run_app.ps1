Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Starting KPR AI-Powered College Food Court System" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Start Backend API
Write-Host "[1/2] Starting Flask Backend API on port 5000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python app.py"

# 2. Start Frontend Server
Write-Host "[2/2] Starting Frontend Server on port 5500..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m http.server 5500 --directory frontend"

Start-Sleep -Seconds 2
Write-Host "`nOpening browser at http://127.0.0.1:5500/index.html ..." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:5500/index.html"
