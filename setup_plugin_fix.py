#!/usr/bin/env python3
"""
OpenAlgo AmiBroker Plugin Fix Setup Script
This script sets up the fixed plugin to prevent AmiBroker hanging issues.
"""

import os
import sys
import shutil
import subprocess
import json
import time
import requests
from pathlib import Path

def log(message):
    """Log with timestamp"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def check_dependencies():
    """Check if required dependencies are available"""
    log("Checking dependencies...")
    
    # Check Python packages
    required_packages = ['websockets', 'python-dotenv']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        log(f"Installing missing packages: {missing_packages}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
    
    log("Dependencies check complete")

def setup_relay_server():
    """Setup and start the relay server"""
    log("Setting up relay server...")
    
    # Create relay server directory
    relay_dir = Path("relay_server")
    relay_dir.mkdir(exist_ok=True)
    
    # Copy relay server files
    shutil.copy("openalgo_relay_server.py", relay_dir)
    shutil.copy("relay_server.env", relay_dir / ".env")
    
    # Create relay server startup script
    startup_script = relay_dir / "start_relay.bat"
    with open(startup_script, 'w') as f:
        f.write(f"""@echo off
cd /d "{relay_dir.absolute()}"
echo Starting OpenAlgo Relay Server...
python openalgo_relay_server.py
pause
""")
    
    log("Relay server setup complete")
    return relay_dir

def create_plugin_config():
    """Create plugin configuration registry file"""
    log("Creating plugin configuration...")
    
    config_content = f"""Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Software\\OpenAlgoRelay]
"Server"="127.0.0.1"
"Port"=dword:0000223a
"ApiKey"="{os.getenv('OPENALGO_API_KEY', '')}"
"""
    
    with open("openalgo_relay_config.reg", 'w') as f:
        f.write(config_content)
    
    log("Plugin configuration created")

def create_build_script():
    """Create build script for the fixed plugin"""
    log("Creating build script...")
    
    build_script = """@echo off
echo Building OpenAlgo Fixed Plugin...

REM Check for Visual Studio
where cl >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Visual Studio compiler not found!
    echo Please install Visual Studio or Build Tools for Visual Studio
    pause
    exit /b 1
)

REM Set up Visual Studio environment
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" 2>nul
if %errorlevel% neq 0 (
    call "C:\\Program Files\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat" 2>nul
)

REM Build the plugin
echo Compiling OpenAlgoPluginFixed.cpp...
cl /O2 /MD /D "WIN32" /D "_WINDOWS" /D "NDEBUG" /D "_USRDLL" /D "_WINDLL" ^
   /I"C:\\AmiBroker\\ADK\\Include" ^
   OpenAlgoPluginFixed.cpp ^
   /link /DLL /OUT:OpenAlgoRelayFixed.dll ^
   /LIBPATH:"C:\\AmiBroker\\ADK\\Lib" ^
   ws2_32.lib

if %errorlevel% equ 0 (
    echo Build successful!
    echo Plugin created: OpenAlgoRelayFixed.dll
) else (
    echo Build failed!
)

pause
"""
    
    with open("build_plugin.bat", 'w', encoding='utf-8') as f:
        f.write(build_script)
    
    log("Build script created")

def create_installation_guide():
    """Create installation guide for the fixed plugin"""
    log("Creating installation guide...")
    
    guide = f"""# OpenAlgo AmiBroker Plugin Fix - Installation Guide

## Problem Solved
This fix resolves the AmiBroker hanging issue with the original OpenAlgo plugin by:
1. Using a relay server architecture (similar to Rtd_Ws_AB_plugin)
2. Implementing non-blocking WebSocket connections
3. Adding proper error handling and reconnection logic
4. Using background threads for network operations

## Installation Steps

### 1. Install Dependencies
```bash
pip install websockets python-dotenv
```

### 2. Configure Relay Server
1. Copy `relay_server.env` to `relay_server/.env`
2. Update the API key in the .env file:
   ```
   OPENALGO_API_KEY=89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0
   ```

### 3. Start Relay Server
```bash
cd relay_server
python openalgo_relay_server.py
```

### 4. Install Plugin Configuration
Double-click `openalgo_relay_config.reg` to add registry settings.

### 5. Build the Fixed Plugin
1. Install Visual Studio or Build Tools for Visual Studio
2. Install AmiBroker ADK (AmiBroker Development Kit)
3. Run `build_plugin.bat`

### 6. Install the Plugin
1. Copy `OpenAlgoRelayFixed.dll` to your AmiBroker plugins folder:
   - Usually: `C:\\Program Files\\AmiBroker\\Plugins`

### 7. Configure AmiBroker
1. Open AmiBroker
2. Go to File -> Database Settings
3. Select "OpenAlgo Data Plugin (Relay Fixed)" as the data source
4. Configure the plugin settings

## Usage

### Relay Server Features
- **Non-blocking connections**: Prevents AmiBroker hanging
- **Automatic reconnection**: Handles connection failures gracefully
- **Quote caching**: Provides fast data access
- **Health monitoring**: Continuous connection health checks
- **Multi-client support**: Handles multiple AmiBroker instances

### Plugin Features
- **Async WebSocket**: Non-blocking data retrieval
- **Quote caching**: 5-second cache for performance
- **Error handling**: Graceful degradation on connection issues
- **Background processing**: Network operations in separate thread

## Troubleshooting

### Plugin Still Hanging
1. Check if relay server is running: `python openalgo_relay_server.py`
2. Verify firewall settings allow port 8766
3. Check OpenAlgo server is running on port 5000

### No Data Received
1. Verify API key in relay_server/.env
2. Check OpenAlgo server logs for authentication errors
3. Ensure symbols are properly formatted (e.g., "RELIANCE-NSE")

### Connection Issues
1. Test relay server: `telnet localhost 8766`
2. Check OpenAlgo WebSocket: `ws://localhost:8765`
3. Verify network connectivity between components

## Architecture

```
AmiBroker -> Fixed Plugin -> Relay Server -> OpenAlgo Server
     |           |              |              |
  Non-blocking  Async WS     Multi-client    Broker APIs
  UI Thread    Connection   Management      (Fyers, etc.)
```

## Performance Notes
- Cache timeout: 5 seconds
- Connection timeout: 2 seconds
- Reconnection delay: 5 seconds exponential backoff
- Maximum clients: 50
- Maximum symbols per client: 100

## Support
For issues with this fix, check:
1. Relay server logs
2. AmiBroker plugin status
3. OpenAlgo server connectivity
4. Network firewall settings
"""
    
    with open("OPENALGO_PLUGIN_FIX_GUIDE.md", 'w', encoding='utf-8') as f:
        f.write(guide)
    
    log("Installation guide created")

def create_test_script():
    """Create test script to verify the fix"""
    log("Creating test script...")
    
    test_script = """#!/usr/bin/env python3
\"\"\"
Test script to verify OpenAlgo Relay Server and Plugin Fix
\"\"\"

import asyncio
import websockets
import json
import time
import sys

def test_relay_connection():
    \"\"\"Test connection to relay server\"\"\"
    print("Testing relay server connection...")
    
    async def test_connection():
        try:
            async with websockets.connect("ws://localhost:8766") as websocket:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "pong":
                    print("✓ Relay server connection successful")
                    return True
                else:
                    print(f"✗ Unexpected response: {data}")
                    return False
                    
        except Exception as e:
            print(f"✗ Relay server connection failed: {e}")
            return False
    
    return asyncio.run(test_connection())

def test_quote_subscription():
    \"\"\"Test quote subscription\"\"\"
    print("Testing quote subscription...")
    
    async def test_subscription():
        try:
            async with websockets.connect("ws://localhost:8766") as websocket:
                # Subscribe to a symbol
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "symbol": "RELIANCE-NSE"
                }))
                
                # Wait for response
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "quote":
                    print(f"✓ Quote received: {data}")
                    return True
                else:
                    print(f"✗ Quote subscription failed: {data}")
                    return False
                    
        except Exception as e:
            print(f"✗ Quote subscription failed: {e}")
            return False
    
    return asyncio.run(test_subscription())

def main():
    print("OpenAlgo Plugin Fix Test Suite")
    print("=" * 40)
    
    tests = [
        ("Relay Connection", test_relay_connection),
        ("Quote Subscription", test_quote_subscription),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\\nRunning: {test_name}")
        if test_func():
            passed += 1
        time.sleep(1)
    
    print(f"\\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! The fix should work correctly.")
    else:
        print("✗ Some tests failed. Check the relay server and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    with open("test_plugin_fix.py", 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    log("Test script created")

def main():
    """Main setup function"""
    log("Starting OpenAlgo Plugin Fix Setup...")
    
    try:
        # Check dependencies
        check_dependencies()
        
        # Setup relay server
        relay_dir = setup_relay_server()
        
        # Create configuration
        create_plugin_config()
        
        # Create build script
        create_build_script()
        
        # Create installation guide
        create_installation_guide()
        
        # Create test script
        create_test_script()
        
        log("Setup complete!")
        log("\nNext steps:")
        log("1. Start the relay server: cd relay_server && python openalgo_relay_server.py")
        log("2. Install plugin configuration: double-click openalgo_relay_config.reg")
        log("3. Build the plugin: run build_plugin.bat (requires Visual Studio)")
        log("4. Test the fix: python test_plugin_fix.py")
        log("5. Read the installation guide: OPENALGO_PLUGIN_FIX_GUIDE.md")
        
    except Exception as e:
        log(f"Setup failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())