@echo off
echo Building Fixed OpenAlgo AmiBroker Plugin...
echo.

REM Set Visual Studio environment (adjust path as needed)
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
) else if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
) else (
    echo ERROR: Visual Studio environment not found!
    echo Please install Visual Studio 2019 or 2022 Community Edition
    pause
    exit /b 1
)

echo Visual Studio environment loaded
echo.

REM Create build directory
if not exist "build" mkdir build
cd build

REM Copy source files
echo Copying source files...
copy /Y "..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\*.cpp" .
copy /Y "..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\*.h" .
copy /Y "..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\*.rc" .
copy /Y "..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\*.ico" .
copy /Y "..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\res\*.*" res\

REM Copy the fixed Plugin.cpp
echo Applying fixed Plugin.cpp...
copy /Y "..\OpenAlgoPlugin-fixed\Plugin.cpp" .

echo.
echo Building plugin with non-blocking operations and robust error handling...
echo.

REM Compile resources
echo Resource compilation...
rc /fo"OpenAlgoPlugin.res" OpenAlgo.rc
if errorlevel 1 (
    echo ERROR: Resource compilation failed!
    pause
    exit /b 1
)

REM Compile the plugin
cl /c /O2 /MD /D "NDEBUG" /D "_WINDOWS" /D "_USRDLL" /D "_WINDLL" /D "_UNICODE" /D "UNICODE" /I"." /I"res" /I"..\OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin" /EHsc /GR /Gd /TP Plugin.cpp OpenAlgoConfigDlg.cpp OpenAlgoGlobals.cpp stdafx.cpp
if errorlevel 1 (
    echo ERROR: Compilation failed!
    pause
    exit /b 1
)

REM Link the plugin
link /OUT:"OpenAlgoPlugin.dll" /DLL /MACHINE:X64 /SUBSYSTEM:WINDOWS /DEF:"OpenAlgoPlugin.def" Plugin.obj OpenAlgoConfigDlg.obj OpenAlgoGlobals.obj stdafx.obj OpenAlgoPlugin.res kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib wininet.lib ws2_32.lib
if errorlevel 1 (
    echo ERROR: Linking failed!
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo.
echo The fixed plugin is now ready: build\OpenAlgoPlugin.dll
echo.
echo Key improvements in this fixed version:
echo - Non-blocking WebSocket connections with proper timeouts
echo - Thread-safe connection management
echo - Robust error handling and recovery
echo - No more AmiBroker hanging issues
echo - Similar reliability to Rtd_Ws_AB_plugin
echo.
pause