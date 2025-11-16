@echo off
echo 🚀 OpenAlgo WebSocket Client for AmiBroker
echo ============================================
echo.
echo 📊 This client connects to OpenAlgo's native WebSocket server
echo 🔌 WebSocket URL: ws://127.0.0.1:8765
echo 🔑 Using API key from: %USERPROFILE%\.fortress\openalgo_api_key.txt
echo.
echo 🎯 Features:
echo    - Real-time LTP data from OpenAlgo WebSocket
echo    - Automatic reconnection on disconnect
echo    - Market data caching
echo    - No .dll dependencies required
echo.
echo 🔄 Starting WebSocket client...
echo.

REM Check if Python packages are installed
python -c "import websockets, aiohttp" 2>nul
if %errorlevel% neq 0 (
    echo 📦 Installing required packages...
    pip install websockets aiohttp
)

REM Check if API key exists
if not exist "%USERPROFILE%\.fortress\openalgo_api_key.txt" (
    echo ❌ API key not found!
    echo Please run update_api_key.bat first to set your OpenAlgo API key.
    pause
    exit /b 1
)

REM Start the WebSocket client
python openalgo_websocket_client.py

echo.
echo ❌ WebSocket client stopped.
echo.
pause
