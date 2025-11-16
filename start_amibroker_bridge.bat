@echo off
echo 🚀 OpenAlgo AmiBroker Bridge
echo ============================================
echo.
echo 📊 Multiple integration methods available:
echo    1. DDE (Dynamic Data Exchange) - Real-time
echo    2. HTTP API - REST endpoints
echo    3. CSV Export - File-based import
echo.
echo 🔌 WebSocket URL: ws://127.0.0.1:8765
echo 🔑 Using API key from: %USERPROFILE%\.fortress\openalgo_api_key.txt
echo.
echo 🎯 AmiBroker Integration Methods:
echo.
echo 📡 DDE (Recommended for real-time):
echo    Topic: OpenAlgo
echo    Item format: SYMBOL.FIELD
echo    Example: =OpenAlgo|RELIANCE!LTP
echo    Available fields: LTP, OPEN, HIGH, LOW, CLOSE, VOLUME, OI, TIMESTAMP
echo.
echo 🌐 HTTP API:
echo    Quote: http://127.0.0.1:8082/quote/RELIANCE-NSE
echo    All quotes: http://127.0.0.1:8082/quotes
echo    Status: http://127.0.0.1:8082/status
echo    CSV Export: http://127.0.0.1:8082/export/RELIANCE-NSE
echo.
echo 🔄 Starting bridge...
echo.

REM Check if Python packages are installed
python -c "import pywin32, aiohttp" 2>nul
if %errorlevel% neq 0 (
    echo 📦 Installing required packages...
    pip install pywin32 aiohttp
)

REM Check if API key exists
if not exist "%USERPROFILE%\.fortress\openalgo_api_key.txt" (
    echo ❌ API key not found!
    echo Please run update_api_key.bat first to set your OpenAlgo API key.
    pause
    exit /b 1
)

REM Start the AmiBroker bridge
python openalgo_amibroker_bridge.py

echo.
echo ❌ AmiBroker bridge stopped.
echo.
pause