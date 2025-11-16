@echo off
echo OpenAlgo ATM Scanner Automation
echo ==============================
echo.
echo This script will run the OpenAlgo ATM Scanner in AmiBroker
echo Make sure AmiBroker is installed and the OpenAlgo plugin is configured
echo.

:: Set AmiBroker path (adjust if needed)
set AMIBROKER_PATH="C:\Program Files\AmiBroker\Broker.exe"

:: Check if AmiBroker exists
if not exist %AMIBROKER_PATH% (
    echo ERROR: AmiBroker not found at %AMIBROKER_PATH%
    echo Please update the AMIBROKER_PATH in this batch file
    pause
    exit /b 1
)

:: Set formula path
set FORMULA_PATH="C:\Program Files\AmiBroker\Formulas\OpenAlgo\ATM_Scanner.afl"

:: Check if formula exists
if not exist %FORMULA_PATH% (
    echo WARNING: Formula file not found at %FORMULA_PATH%
    echo Please create the formula file first or update the path
    echo.
    echo You can copy the formula from: C:\Users\Admin\Documents\FortressTradingSystem\OpenAlgo_ATM_Scanner.afl
    echo.
    pause
)

echo Starting AmiBroker with ATM Scanner...
echo.

:: Run AmiBroker with the scanner
%AMIBROKER_PATH% /runformula %FORMULA_PATH%

echo.
echo ATM Scanner executed successfully
echo Check AmiBroker for results
echo.
echo Note: Make sure the OpenAlgo server is running at http://localhost:5000
echo and your API key is configured in the formula parameters
echo.
pause
