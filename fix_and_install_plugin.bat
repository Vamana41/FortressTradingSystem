@echo off
echo 🚀 OpenAlgo AmiBroker Plugin Fix and Installation
echo ========================================================
echo.
echo 🎯 This script will fix the hanging AmiBroker plugin issue
echo    and install the corrected version with proper timeouts.
echo.
echo 📋 What this fixes:
echo - Blocking WebSocket connections that hang AmiBroker
echo - Missing timeouts on HTTP requests
echo - No connection state management
echo - Poor error recovery
echo.
echo Press any key to start the fix...
pause > nul

echo.
echo 🔧 Step 1: Building the fixed plugin...
cd /d "C:\Users\Admin\Documents\FortressTradingSystem"

REM Check if Visual Studio is available
where cl >nul 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  Visual Studio compiler not found in PATH
    echo 📝 Attempting to use Visual Studio 2022 Community...

    REM Try to find Visual Studio 2022
    if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
        call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
        call "C:\Program Files (x86)\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    ) else (
        echo ❌ Visual Studio 2022 not found!
        echo Please install Visual Studio 2022 Community Edition
        echo or run this script from Visual Studio Command Prompt
        pause
        exit /b 1
    )
)

echo ✅ Visual Studio environment loaded

REM Build the fixed plugin
echo.
echo 🔧 Step 2: Compiling the fixed plugin...
cd build

REM Compile resources
echo 📄 Compiling resources...
rc /fo"OpenAlgoPlugin.res" OpenAlgoPlugin.rc
if %errorlevel% neq 0 (
    echo ⚠️  Resource compilation failed, continuing...
)

REM Compile source files
echo 🔨 Compiling source files...
cl /c /O2 /MD /D "NDEBUG" /D "_WINDOWS" /D "_USRDLL" /D "_WINDLL" /D "_UNICODE" /D "UNICODE" /I"." /EHsc /GR /Gd /TP Plugin.cpp OpenAlgoConfigDlg.cpp OpenAlgoGlobals.cpp stdafx.cpp
if %errorlevel% neq 0 (
    echo ❌ Source compilation failed!
    echo Please check the error messages above
    pause
    exit /b 1
)

REM Link the plugin
echo 🔗 Linking plugin...
link /OUT:"OpenAlgoPlugin.dll" /DLL /MACHINE:X64 /SUBSYSTEM:WINDOWS /DEF:"OpenAlgoPlugin.def" Plugin.obj OpenAlgoConfigDlg.obj OpenAlgoGlobals.obj stdafx.obj OpenAlgoPlugin.res kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib wininet.lib ws2_32.lib
if %errorlevel% neq 0 (
    echo ❌ Linking failed!
    pause
    exit /b 1
)

echo ✅ Plugin built successfully!

REM Installation
echo.
echo 📦 Step 3: Installing the fixed plugin...

REM Check if AmiBroker is installed
if not exist "C:\Program Files\AmiBroker" (
    echo ❌ AmiBroker not found in default location!
    echo Please install AmiBroker first or update the path in this script
    pause
    exit /b 1
)

REM Backup original plugin if it exists
echo 💾 Backing up original plugin...
cd "C:\Program Files\AmiBroker\Plugins"
if exist OpenAlgoPlugin.dll (
    copy OpenAlgoPlugin.dll OpenAlgoPlugin.dll.backup
    echo ✅ Original plugin backed up as OpenAlgoPlugin.dll.backup
)

REM Copy the fixed plugin
echo 📤 Installing fixed plugin...
copy /Y "C:\Users\Admin\Documents\FortressTradingSystem\build\OpenAlgoPlugin.dll" "C:\Program Files\AmiBroker\Plugins\"
if %errorlevel% neq 0 (
    echo ❌ Failed to copy plugin!
    echo Make sure AmiBroker is not running
    pause
    exit /b 1
)

echo ✅ Fixed plugin installed successfully!

echo.
echo 🎯 Step 4: Configuration Instructions
echo ========================================================
echo.
echo 📋 To configure the fixed plugin in AmiBroker:
echo 1. Start AmiBroker
echo 2. Go to File → Database → Configure
echo 3. Select "OpenAlgo Data Plugin (Fixed)"
echo 4. Configure settings:
echo    - Server: 127.0.0.1
echo    - Port: 5000
echo    - API Key: [Your daily OpenAlgo API key]
echo    - WebSocket URL: ws://127.0.0.1:8765
echo.
echo 🛡️  The fixed plugin includes:
echo    - Connection timeouts (no more hanging!)
echo    - Automatic retry on failures
echo    - Non-blocking data retrieval
echo    - Proper error handling
echo.
echo ✅ Installation completed!
echo.
echo 🚀 Next steps:
echo 1. Start OpenAlgo: cd openalgo && python app.py
echo 2. Start AmiBroker and configure the plugin
echo 3. Test with a symbol like RELIANCE-NSE
echo.
pause
