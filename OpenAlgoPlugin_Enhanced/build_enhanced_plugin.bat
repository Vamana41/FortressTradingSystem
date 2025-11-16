@echo off
REM Build script for OpenAlgo Enhanced AmiBroker Plugin
REM This script builds the enhanced plugin with robust error handling

echo OpenAlgo Enhanced Plugin Build Script
echo =====================================

REM Check for Visual Studio 2019 or later
set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist %VSWHERE% (
    echo ERROR: Visual Studio 2019 or later not found!
    echo Please install Visual Studio 2019 or later with C++ development tools
    exit /b 1
)

REM Find Visual Studio installation
for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -property installationPath`) do (
    set VSINSTALLPATH=%%i
)

if not defined VSINSTALLPATH (
    echo ERROR: Visual Studio installation path not found!
    exit /b 1
)

echo Found Visual Studio at: %VSINSTALLPATH%

REM Set up Visual Studio environment
call "%VSINSTALLPATH%\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 (
    echo ERROR: Failed to set up Visual Studio environment!
    exit /b 1
)

REM Check for AmiBroker ADK
if not defined AMIBROKER_ADK (
    echo ERROR: AMIBROKER_ADK environment variable not set!
    echo Please set AMIBROKER_ADK to point to your AmiBroker Development Kit
    echo Example: set AMIBROKER_ADK=C:\AmiBroker\ADK
    exit /b 1
)

if not exist "%AMIBROKER_ADK%" (
    echo ERROR: AmiBroker ADK not found at: %AMIBROKER_ADK%
    echo Please download the AmiBroker ADK from https://www.amibroker.com/
    exit /b 1
)

echo Found AmiBroker ADK at: %AMIBROKER_ADK%

REM Create build directory
if not exist "build" mkdir build
cd build

REM Generate Visual Studio project files
echo Generating Visual Studio project...

REM Create CMakeLists.txt for the project
echo cmake_minimum_required(VERSION 3.16) > CMakeLists.txt
echo project(OpenAlgoPlugin_Enhanced) >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Set C++ standard >> CMakeLists.txt
echo set(CMAKE_CXX_STANDARD 17) >> CMakeLists.txt
echo set(CMAKE_CXX_STANDARD_REQUIRED ON) >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Find Windows SDK >> CMakeLists.txt
echo find_package(WindowsSDK REQUIRED) >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Include directories >> CMakeLists.txt
echo include_directories(^) >> CMakeLists.txt
echo     "%AMIBROKER_ADK%\Include" ^) >> CMakeLists.txt
echo     $^{CMAKE_CURRENT_SOURCE_DIR^}/../ >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Source files >> CMakeLists.txt
echo set(SOURCES ^) >> CMakeLists.txt
echo     ../Plugin_Enhanced.cpp ^) >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Create DLL >> CMakeLists.txt
echo add_library(OpenAlgoPlugin_Enhanced SHARED $^{SOURCES^}) >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Link libraries >> CMakeLists.txt
echo target_link_libraries(OpenAlgoPlugin_Enhanced ^) >> CMakeLists.txt
echo     "%AMIBROKER_ADK%\Lib\broker.lib" ^) >> CMakeLists.txt
echo     wininet.lib ^) >> CMakeLists.txt
echo     ws2_32.lib ^) >> CMakeLists.txt
echo     ole32.lib ^) >> CMakeLists.txt
echo     oaidl.lib >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Set output name >> CMakeLists.txt
echo set_target_properties(OpenAlgoPlugin_Enhanced PROPERTIES OUTPUT_NAME "OpenAlgoPlugin") >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # Set DLL properties >> CMakeLists.txt
echo set_target_properties(OpenAlgoPlugin_Enhanced PROPERTIES SUFFIX ".dll") >> CMakeLists.txt
echo. >> CMakeLists.txt
echo # MSVC specific settings >> CMakeLists.txt
echo if(MSVC) >> CMakeLists.txt
echo     target_compile_options(OpenAlgoPlugin_Enhanced PRIVATE /W4 /WX-) >> CMakeLists.txt
echo     set_target_properties(OpenAlgoPlugin_Enhanced PROPERTIES VS_DEBUGGER_WORKING_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}") >> CMakeLists.txt
echo endif() >> CMakeLists.txt

REM Configure and build
echo Configuring project...
cmake -G "Visual Studio 16 2019" -A x64 ..
if errorlevel 1 (
    echo ERROR: CMake configuration failed!
    exit /b 1
)

echo Building Release version...
cmake --build . --config Release
if errorlevel 1 (
    echo ERROR: Build failed!
    exit /b 1
)

echo.
echo Build completed successfully!
echo.
echo Output files:
dir /B Release\*.dll

REM Create installation script
echo @echo off > install_enhanced.bat
echo REM Install OpenAlgo Enhanced Plugin >> install_enhanced.bat
echo. >> install_enhanced.bat
echo echo Installing OpenAlgo Enhanced Plugin... >> install_enhanced.bat
echo. >> install_enhanced.bat
echo REM Backup original plugin >> install_enhanced.bat
echo if exist "C:\Program Files ^(x86^)\AmiBroker\Plugins\OpenAlgoPlugin.dll" ^( >> install_enhanced.bat
echo     copy "C:\Program Files ^(x86^)\AmiBroker\Plugins\OpenAlgoPlugin.dll" "C:\Program Files ^(x86^)\AmiBroker\Plugins\OpenAlgoPlugin_backup.dll" >> install_enhanced.bat
echo     echo Backed up original plugin to OpenAlgoPlugin_backup.dll >> install_enhanced.bat
echo ^) >> install_enhanced.bat
echo. >> install_enhanced.bat
echo REM Install enhanced plugin >> install_enhanced.bat
echo copy "%~dp0Release\OpenAlgoPlugin.dll" "C:\Program Files ^(x86^)\AmiBroker\Plugins\OpenAlgoPlugin.dll" >> install_enhanced.bat
echo. >> install_enhanced.bat
echo if errorlevel 1 ^( >> install_enhanced.bat
echo     echo ERROR: Failed to install plugin! >> install_enhanced.bat
echo     echo Please run this script as Administrator >> install_enhanced.bat
echo     pause >> install_enhanced.bat
echo     exit /b 1 >> install_enhanced.bat
echo ^) >> install_enhanced.bat
echo. >> install_enhanced.bat
echo echo Plugin installed successfully! >> install_enhanced.bat
echo echo. >> install_enhanced.bat
echo echo Please restart AmiBroker to use the enhanced plugin. >> install_enhanced.bat
echo pause >> install_enhanced.bat

echo.
echo Installation script created: install_enhanced.bat
echo.
echo To install the enhanced plugin:
echo 1. Run install_enhanced.bat as Administrator
echo 2. Restart AmiBroker
echo 3. Configure the plugin with your OpenAlgo settings

REM Create test script
echo @echo off > test_plugin.bat
echo REM Test OpenAlgo Enhanced Plugin >> test_plugin.bat
echo. >> test_plugin.bat
echo echo Testing OpenAlgo Enhanced Plugin... >> test_plugin.bat
echo echo. >> test_plugin.bat
echo REM Check if plugin file exists >> test_plugin.bat
echo if not exist "C:\Program Files ^(x86^)\AmiBroker\Plugins\OpenAlgoPlugin.dll" ^( >> test_plugin.bat
echo     echo ERROR: Plugin not found in AmiBroker plugins folder! >> test_plugin.bat
echo     echo Please run install_enhanced.bat first >> test_plugin.bat
echo     pause >> test_plugin.bat
echo     exit /b 1 >> test_plugin.bat
echo ^) >> test_plugin.bat
echo. >> test_plugin.bat
echo echo Plugin file found. >> test_plugin.bat
echo echo. >> test_plugin.bat
echo REM Check if OpenAlgo server is running >> test_plugin.bat
echo echo Checking OpenAlgo server... >> test_plugin.bat
echo powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/v1/ping' -Method POST -Body '{\"apikey\":\"test\"}' -TimeoutSec 5; if ^($response.StatusCode -eq 200^) { Write-Host 'OpenAlgo server is responding' -ForegroundColor Green } else { Write-Host 'OpenAlgo server returned status:' $response.StatusCode -ForegroundColor Yellow } } catch { Write-Host 'OpenAlgo server is not responding' -ForegroundColor Red }" >> test_plugin.bat
echo. >> test_plugin.bat
echo echo. >> test_plugin.bat
echo echo To fully test the plugin: >> test_plugin.bat
echo 1. Start AmiBroker >> test_plugin.bat
echo 2. Add a test symbol like 'RELIANCE-NSE' >> test_plugin.bat
echo 3. Check the plugin status indicator >> test_plugin.bat
echo 4. Verify data is streaming >> test_plugin.bat
echo pause >> test_plugin.bat

cd ..

echo.
echo Build and setup scripts created successfully!
echo.
echo Next steps:
echo 1. Run build_enhanced_plugin.bat to build the plugin
echo 2. Run install_enhanced.bat as Administrator to install
echo 3. Run test_plugin.bat to verify installation
echo.
echo For detailed instructions, see README_ENHANCED.md
