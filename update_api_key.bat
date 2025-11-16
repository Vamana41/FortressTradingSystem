@echo off
echo 🔄 Fortress Trading System - Daily API Key Update
echo ========================================================
echo.
echo 📋 Daily Process:
echo 1. Login to OpenAlgo manually
echo 2. Login to Fyers through OpenAlgo
echo 3. Copy API key from OpenAlgo dashboard
echo 4. Run this script and paste the key
echo.
echo Press any key to start API key update...
pause > nul

python daily_api_key_updater.py

echo.
echo 🎯 To start Fortress Trading System:
echo cd fortress
echo set PYTHONPATH=%cd%\fortress\src
echo python fortress\src\fortress\main.py
echo.
pause
