@echo off
echo 🚀 OpenAlgo RTD Server for AmiBroker
echo ========================================
echo.
echo 📊 This server provides real-time data to AmiBroker via:
echo    - HTTP API for quotes and historical data
echo    - CSV export for AmiBroker import
echo    - WebSocket for real-time streaming
echo.
echo 🎯 AmiBroker Integration:
echo    1. Use AmiBroker's ASCII import feature
echo    2. Point to: http://127.0.0.1:8080/rtd/export/SYMBOL-EXCHANGE
echo    3. Example: http://127.0.0.1:8080/rtd/export/RELIANCE-NSE
echo.
echo 🔄 Starting RTD server...
echo.

REM Check if Python packages are installed
python -c "import aiohttp, websockets" 2>nul
if %errorlevel% neq 0 (
    echo 📦 Installing required packages...
    pip install aiohttp websockets
)

REM Start the RTD server
python openalgo_rtd_server.py

echo.
echo ❌ RTD server stopped.
echo.
pause
