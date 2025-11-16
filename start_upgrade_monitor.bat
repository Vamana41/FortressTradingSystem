@echo off
echo Starting OpenAlgo Upgrade Monitor Service...
:loop
python openalgo_upgrade_system.py --monitor
timeout /t 21600 /nobreak >nul
goto loop
