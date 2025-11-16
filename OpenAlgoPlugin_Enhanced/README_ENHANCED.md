# OpenAlgo Enhanced AmiBroker Plugin

This enhanced version of the OpenAlgo AmiBroker plugin provides robust error handling and non-blocking operations to prevent AmiBroker hanging issues.

## Key Improvements

### 1. **Non-Blocking Operations**
- All network operations use non-blocking sockets with proper timeouts
- Connection attempts are limited to 3 seconds maximum
- No more hanging during connection failures

### 2. **Background Connection Thread**
- Dedicated worker thread handles all network operations
- Main AmiBroker thread remains responsive
- Graceful degradation when connections fail

### 3. **Robust Error Handling**
- Exponential backoff retry mechanism
- Comprehensive error logging
- Connection health monitoring
- Automatic reconnection on failures

### 4. **Thread Safety**
- Proper mutex protection for shared resources
- Atomic operations for connection state
- No race conditions or deadlocks

### 5. **Enhanced Status Reporting**
- Detailed connection status messages
- Visual indicators for connection health
- Retry countdown timer

## Building the Enhanced Plugin

### Prerequisites
- Visual Studio 2019 or later
- Windows SDK
- AmiBroker Development Kit (ADK)

### Build Instructions

1. **Create Visual Studio Project**
```
File -> New -> Project -> Visual C++ -> Win32 -> Win32 Project
Name: OpenAlgoPlugin_Enhanced
Application type: DLL
```

2. **Add Source Files**
- Copy Plugin_Enhanced.cpp to your project
- Add necessary AmiBroker ADK headers

3. **Configure Project Settings**
```
Configuration Properties:
- General -> Configuration Type: Dynamic Library (.dll)
- C/C++ -> General -> Additional Include Directories: $(AMIBROKER_ADK)\Include
- Linker -> General -> Additional Library Directories: $(AMIBROKER_ADK)\Lib
- Linker -> Input -> Additional Dependencies: oaidl.lib;ole32.lib;ws2_32.lib;wininet.lib
```

4. **Build the Plugin**
- Build -> Build Solution (Release configuration)
- Output: OpenAlgoPlugin_Enhanced.dll

## Installation

1. **Backup Original Plugin**
```powershell
# Backup the original plugin if it exists
Copy-Item "C:\Program Files (x86)\AmiBroker\Plugins\OpenAlgoPlugin.dll" "C:\Program Files (x86)\AmiBroker\Plugins\OpenAlgoPlugin_backup.dll"
```

2. **Install Enhanced Plugin**
```powershell
# Copy the enhanced plugin to AmiBroker plugins folder
Copy-Item "OpenAlgoPlugin_Enhanced.dll" "C:\Program Files (x86)\AmiBroker\Plugins\OpenAlgoPlugin.dll"
```

3. **Configure Plugin**
- Start AmiBroker
- Go to File -> Database Settings -> Data Source
- Select "OpenAlgo Enhanced Data Plugin"
- Configure with your settings:
  - Server: 127.0.0.1
  - Port: 5000
  - API Key: [your OpenAlgo API key]
  - WebSocket URL: ws://127.0.0.1:8765

## Configuration

### Registry Settings
The plugin stores its configuration in the Windows registry:
```
HKEY_CURRENT_USER\Software\TJP\Broker\OpenAlgo
```

### Settings:
- `Server`: OpenAlgo server address (default: 127.0.0.1)
- `Port`: OpenAlgo server port (default: 5000)
- `ApiKey`: Your OpenAlgo API key
- `WebSocketUrl`: WebSocket URL for real-time data (default: ws://127.0.0.1:8765)
- `RefreshInterval`: Data refresh interval in seconds (default: 5)
- `TimeShift`: Time zone offset in hours (default: 0)

## Troubleshooting

### Plugin Still Hanging?
1. **Check OpenAlgo Server Status**
   ```bash
   python check_system_status.py
   ```

2. **Enable Debug Logging**
   - Use DebugView from Microsoft Sysinternals
   - Plugin logs detailed connection information

3. **Test Connection Manually**
   - Right-click on plugin status in AmiBroker
   - Select "Test Connection"

### Common Issues

**Issue: "Connection timeout" error**
- Solution: Check if OpenAlgo server is running on port 5000
- Verify firewall settings allow local connections

**Issue: "Authentication failed" error**
- Solution: Verify API key is correct
- Check OpenAlgo server logs for authentication errors

**Issue: "No recent data" warning**
- Solution: Check WebSocket connection on port 8765
- Verify symbol subscriptions are working

## Performance Monitoring

The enhanced plugin provides several performance indicators:

1. **Connection Status Colors:**
   - 🟢 Green: Connected and receiving data
   - 🟡 Yellow: Waiting to connect
   - 🟠 Orange: Connected but no recent data
   - 🔴 Red: Disconnected, retrying
   - 🟣 Purple: Offline, manual reconnection required

2. **Status Messages:**
   - "OK": Everything working normally
   - "WAIT": Initializing connection
   - "RETRY": Connection failed, retrying in X seconds
   - "STALE": Connected but data is old
   - "OFF": Plugin is offline

## Comparison with Original Plugin

| Feature | Original Plugin | Enhanced Plugin |
|---------|----------------|-----------------|
| Blocking Operations | ❌ Yes | ✅ No |
| Background Thread | ❌ No | ✅ Yes |
| Retry Mechanism | ❌ Basic | ✅ Exponential Backoff |
| Error Logging | ❌ Minimal | ✅ Comprehensive |
| Connection Health | ❌ No | ✅ Monitored |
| Thread Safety | ❌ Limited | ✅ Full |
| Timeout Protection | ❌ No | ✅ 3-second max |
| Graceful Degradation | ❌ No | ✅ Yes |

## Next Steps

After installing the enhanced plugin:

1. **Test the Connection**
   - Start AmiBroker
   - Add some test symbols (e.g., RELIANCE-NSE, SBIN-NSE)
   - Verify data is streaming correctly

2. **Monitor Performance**
   - Watch the connection status indicator
   - Check for any error messages
   - Verify data freshness

3. **Configure ATM Scanner**
   - Use the ATM scanner AFL formula provided
   - Set up automatic symbol injection
   - Test with your trading strategy

## Support

If you continue to experience issues:

1. **Check System Status**
   ```bash
   python check_system_status.py
   ```

2. **Review Logs**
   - Use DebugView to capture plugin logs
   - Check OpenAlgo server logs
   - Review AmiBroker plugin status messages

3. **Contact Support**
   - Provide the debug logs
   - Include system configuration details
   - Describe the exact steps to reproduce the issue

The enhanced plugin should resolve the hanging issues while maintaining full compatibility with your existing OpenAlgo setup.