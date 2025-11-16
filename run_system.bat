@echo off
TITLE Sentinel Fortress System - MASTER LAUNCHER (v10.0 - The Final Key)

ECHO ==================================================================
ECHO  Fortress Environment Detected. Launching Components...
ECHO ==================================================================
ECHO.

REM This is the Master Key: The absolute path to the virtual environment's
REM activation script. This is the command that "poetry shell" runs.
SET "VENV_ACTIVATE=C:\Users\Admin\AppData\Local\pypoetry\Cache\virtualenvs\sentinel-fortress-system-lGWcwW-K-py3.11\Scripts\activate.bat"

ECHO [1/3] Launching OpenAlgo Conductor (Web UI, ZMQ Broker, API Worker)...
REM This is the solution to the paradox:
REM 1. We CALL the activation script to load all 75 packages.
REM 2. We change the directory TO 'openalgo'.
REM 3. We can now just run 'python app.py' because the correct, activated Python is in control.
REM 4. We use /k to KEEP THE WINDOW OPEN for diagnostics.
start "Conductor" cmd /k "CALL %VENV_ACTIVATE% & cd openalgo & (python app.py || py -3.14 app.py || py -3.12 app.py)"
timeout /t 5 >nul

ECHO [2/3] Launching AmiBroker Watcher Sentinel...
REM We use the same technique for all other scripts.
start "Sentinel-Ami" cmd /k "CALL %VENV_ACTIVATE% & (python sentinels/amibroker_watcher.py || py -3.14 sentinels/amibroker_watcher.py || py -3.12 sentinels/amibroker_watcher.py)"
timeout /t 2 >nul

ECHO [3/3] Launching The Strategist Engine...
start "Strategist" cmd /k "CALL %VENV_ACTIVATE% & (python sentinels/strategist.py || py -3.14 sentinels/strategist.py || py -3.12 sentinels/strategist.py)"
timeout /t 2 >nul

ECHO.
ECHO ==================================================================
ECHO  All Fortress components are now online and decoupled.
ECHO  System is operational.
ECHO  (The windows will remain open for diagnostics)
ECHO ==================================================================