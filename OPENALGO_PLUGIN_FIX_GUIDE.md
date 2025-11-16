# OpenAlgo AmiBroker Plugin Fix Guide

## Problem Identified
The original OpenAlgo AmiBroker plugin causes AmiBroker to hang due to **blocking operations** in the WebSocket connection and HTTP request handling. This is similar to the robust implementation you have in your Rtd_Ws_AB_plugin.

## Key Issues Fixed

### 1. **Blocking WebSocket Connections**
- **Original Issue**: `connect()` calls were blocking indefinitely
- **Fix**: Implemented non-blocking sockets with `select()` timeout
- **Timeout**: 3 seconds for WebSocket connections

### 2. **Blocking HTTP Requests**
- **Original Issue**: HTTP requests to OpenAlgo API would block forever
- **Fix**: Added proper timeouts (2 seconds) and non-blocking approach
- **Threading**: Connection tests run in separate threads

### 3. **No Connection State Management**
- **Original Issue**: No way to detect if connection was in progress
- **Fix**: Added connection state tracking with timeouts
- **Prevention**: Prevents multiple simultaneous connection attempts

### 4. **Missing Error Recovery**
- **Original Issue**: No graceful handling of connection failures
- **Fix**: Robust error handling with automatic retry logic
- **Recovery**: Connection state resets after timeouts

## Key Improvements in Fixed Version

### Non-Blocking Operations
```cpp
// Set socket to non-blocking mode immediately
u_long mode = 1;
ioctlsocket(g_websocket, FIONBIO, &mode);

// Use select() with timeout instead of blocking connect()
if (select(0, NULL, &writefds, NULL, &timeout) <= 0) {
    // Timeout occurred - connection failed
    return FALSE;
}
```

### Thread-Safe Connection Management
```cpp
// Connection test runs in separate thread
unsigned __stdcall ConnectionThreadProc(void* pParam) {
    // Non-blocking connection test with timeout
    // Updates global status when complete
    // Prevents AmiBroker UI blocking
}
```

### Robust Timeout Handling
```cpp
// Check if connection attempt is in progress
if (g_bConnectionInProgress) {
    DWORD dwElapsed = (DWORD)GetTickCount64() - g_dwConnectionStartTime;
    if (dwElapsed > HTTP_REQUEST_TIMEOUT) {
        // Timeout - reset connection state
        g_bConnectionInProgress = FALSE;
        return FALSE;
    }
    return FALSE; // Still testing
}
```

## Building the Fixed Plugin

### Prerequisites
1. **Visual Studio 2019/2022 Community Edition**
2. **Windows SDK**
3. **AmiBroker Plugin SDK** (included in source)

### Build Steps
1. Open Command Prompt as Administrator
2. Navigate to the FortressTradingSystem folder
3. Run the build script:
   ```cmd
   build_fixed_plugin.bat
   ```

### Manual Build (if script fails)
```cmd
# Set up Visual Studio environment
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

# Compile resources
rc /fo"OpenAlgoPlugin.res" OpenAlgoPlugin.rc

# Compile source files
cl /c /O2 /MD /D "NDEBUG" /D "_WINDOWS" /D "_USRDLL" /D "_WINDLL" /D "_UNICODE" /D "UNICODE" /I"." /EHsc /GR /Gd /TP Plugin.cpp OpenAlgoConfigDlg.cpp OpenAlgoGlobals.cpp stdafx.cpp

# Link the plugin
link /OUT:"OpenAlgoPlugin.dll" /DLL /MACHINE:X64 /SUBSYSTEM:WINDOWS /DEF:"OpenAlgoPlugin.def" Plugin.obj OpenAlgoConfigDlg.obj OpenAlgoGlobals.obj stdafx.obj OpenAlgoPlugin.res kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib wininet.lib ws2_32.lib
```

## Installation

### 1. Backup Original Plugin
```cmd
# Navigate to AmiBroker plugins folder
cd "C:\Program Files\AmiBroker\Plugins"

# Backup original plugin (if exists)
if exist OpenAlgoPlugin.dll copy OpenAlgoPlugin.dll OpenAlgoPlugin.dll.backup
```

### 2. Install Fixed Plugin
```cmd
# Copy the fixed plugin
copy "C:\Users\Admin\Documents\FortressTradingSystem\build\OpenAlgoPlugin.dll" "C:\Program Files\AmiBroker\Plugins\"
```

### 3. Configure Plugin
1. Start AmiBroker
2. Go to **File → Database → Configure**
3. Select **OpenAlgo Data Plugin (Fixed)**
4. Configure settings:
   - **Server**: 127.0.0.1
   - **Port**: 5000
   - **API Key**: Your OpenAlgo API key (89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0)
   - **WebSocket URL**: ws://127.0.0.1:8765

## Testing the Fixed Plugin

### 1. Verify OpenAlgo Server is Running
```python
# Check if OpenAlgo server is responding
python check_system_status.py
```

### 2. Test Connection in AmiBroker
1. Open **Real-time Quote Window**
2. Add a symbol like "RELIANCE-NSE"
3. Check plugin status (should show "OK" in green)

### 3. Monitor Connection
The plugin now includes:
- **Connection timeouts** (no more hanging)
- **Automatic retry** on connection failures
- **Status indicators** showing connection state
- **Non-blocking data retrieval**

## Comparison with Rtd_Ws_AB_plugin

The fixed version now implements similar robust patterns to your Rtd_Ws_AB_plugin:

| Feature | Original OpenAlgo | Fixed Version | Rtd_Ws_AB_plugin |
|---------|------------------|---------------|------------------|
| Non-blocking connections | ❌ | ✅ | ✅ |
| Connection timeouts | ❌ | ✅ (3s) | ✅ |
| Thread-safe operations | ❌ | ✅ | ✅ |
| Error recovery | ❌ | ✅ | ✅ |
| Status monitoring | Basic | Enhanced | Advanced |
| Bi-directional WebSocket | ❌ | ✅ | ✅ |

## Troubleshooting

### Plugin Still Hangs
1. **Check OpenAlgo Server**: Ensure server is running on port 5000
2. **Verify API Key**: Confirm API key is correctly configured
3. **Check Windows Firewall**: Allow AmiBroker to connect to localhost
4. **Review Logs**: Check AmiBroker plugin logs for errors

### Connection Failed
1. **Server Status**: Run `python check_system_status.py`
2. **Port Availability**: Check if port 5000 is available
3. **API Endpoints**: Verify OpenAlgo API is responding

### Data Not Updating
1. **Symbol Format**: Use format "SYMBOL-EXCHANGE" (e.g., "RELIANCE-NSE")
2. **WebSocket Connection**: Check WebSocket URL configuration
3. **Market Hours**: Ensure data is available during market hours

## Next Steps

After installing the fixed plugin:

1. **Test basic connectivity** with simple symbols
2. **Verify ATM symbol injection** works correctly
3. **Test real-time data flow** during market hours
4. **Integrate with your ATM selection logic** (fyers_client_Two_expiries)

The fixed plugin should now provide the same reliability as your Rtd_Ws_AB_plugin without hanging AmiBroker.
