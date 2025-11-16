@echo off
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
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" 2>nul
if %errorlevel% neq 0 (
    call "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" 2>nul
)

REM Build the plugin
echo Compiling OpenAlgoPluginFixed.cpp...
cl /O2 /MD /D "WIN32" /D "_WINDOWS" /D "NDEBUG" /D "_USRDLL" /D "_WINDLL" ^
   /I"C:\AmiBroker\ADK\Include" ^
   OpenAlgoPluginFixed.cpp ^
   /link /DLL /OUT:OpenAlgoRelayFixed.dll ^
   /LIBPATH:"C:\AmiBroker\ADK\Lib" ^
   ws2_32.lib

if %errorlevel% equ 0 (
    echo Build successful!
    echo Plugin created: OpenAlgoRelayFixed.dll
) else (
    echo Build failed!
)

pause
