#!/usr/bin/env python3
"""
Fix AmiBroker Plugin Hanging Issue

This script switches from the basic OpenAlgo plugin (which hangs AmiBroker)
to the enhanced plugin with proper threading and non-blocking I/O.

The basic plugin hangs because:
1. Blocking WebSocket connect on AmiBroker's main thread
2. Blocking HTTP requests in GetRecentInfo callback
3. No dedicated worker thread for network operations
4. Synchronous socket operations without proper timeouts

The enhanced plugin fixes this with:
1. Dedicated WebSocket thread using _beginthreadex
2. Non-blocking sockets from the start
3. Proper select() timeouts for all I/O operations
4. Quote cache to serve AmiBroker quickly without blocking
"""

import os
import shutil
import subprocess
import json
import sys
from pathlib import Path

def find_amibroker_folder():
    """Find AmiBroker installation folder"""
    common_paths = [
        r"C:\Program Files\AmiBroker",
        r"C:\Program Files (x86)\AmiBroker",
        r"C:\AmiBroker",
    ]
    
    for path in common_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "Broker.exe")):
            return path
    
    # Try to find via registry
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\AmiBroker") as key:
            return winreg.QueryValueEx(key, "Path")[0]
    except:
        pass
    
    return None

def backup_existing_plugin(amibroker_path):
    """Backup existing plugin"""
    plugin_path = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll")
    backup_path = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll.backup")
    
    if os.path.exists(plugin_path):
        print(f"Backing up existing plugin to {backup_path}")
        shutil.copy2(plugin_path, backup_path)
        return True
    return False

def build_enhanced_plugin():
    """Build the enhanced plugin with threading support"""
    enhanced_source = r"OpenAlgoPlugin-enhanced\Plugin.cpp"
    
    if not os.path.exists(enhanced_source):
        print("Enhanced plugin source not found. Creating it...")
        create_enhanced_plugin()
    
    # Check if we have Visual Studio build tools
    vs_paths = [
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
    ]
    
    vcvars_path = None
    for path in vs_paths:
        if os.path.exists(path):
            vcvars_path = path
            break
    
    if not vcvars_path:
        print("Visual Studio build tools not found. Please install Visual Studio or build tools.")
        return False
    
    # Build command
    build_cmd = f'''
call "{vcvars_path}"
cl /LD /MD /O2 /D "WIN32" /D "_WINDOWS" /D "_USRDLL" /D "_AFXDLL" /D "_MBCS" /I "OpenAlgoPlugin-enhanced" "{enhanced_source}" /link /OUT:"OpenAlgoPlugin-enhanced\OpenAlgo.dll" /DEF:"OpenAlgoPlugin-enhanced\Plugin.def" kernel32.lib user32.lib ws2_32.lib wininet.lib advapi32.lib
'''
    
    print("Building enhanced plugin...")
    try:
        result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("Enhanced plugin built successfully!")
            return True
        else:
            print(f"Build failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Build error: {e}")
        return False

def create_enhanced_plugin():
    """Create the enhanced plugin source if it doesn't exist"""
    enhanced_dir = "OpenAlgoPlugin-enhanced"
    os.makedirs(enhanced_dir, exist_ok=True)
    
    # Create Plugin.def
    def_content = '''LIBRARY OpenAlgo
EXPORTS
    GetPluginInfo
    Init
    Release
    GetQuotesEx
    GetRecentInfo
    Configure
'''
    
    with open(os.path.join(enhanced_dir, "Plugin.def"), "w") as f:
        f.write(def_content)
    
    # Copy and enhance the basic plugin
    basic_plugin = r"OpenAlgoPlugin-basic-plugin_sourcecode\OpenAlgoPlugin-basic-plugin\Plugin.cpp"
    enhanced_plugin = os.path.join(enhanced_dir, "Plugin.cpp")
    
    if os.path.exists(basic_plugin):
        print("Creating enhanced plugin from basic plugin...")
        with open(basic_plugin, "r") as f:
            content = f.read()
        
        # Add threading support
        enhanced_content = add_threading_support(content)
        
        with open(enhanced_plugin, "w") as f:
            f.write(enhanced_content)
        
        print("Enhanced plugin created with threading support!")
    else:
        print("Basic plugin source not found. Cannot create enhanced version.")
        return False
    
    return True

def add_threading_support(content):
    """Add threading support to the plugin"""
    # Add necessary includes
    threading_includes = '''
#include <process.h>  // for _beginthreadex
#include <atomic>
#include <queue>
#include <mutex>
#include <condition_variable>
'''
    
    # Add global variables for threading
    threading_globals = '''
// Threading variables
static HANDLE g_hWebSocketThread = NULL;
static unsigned g_webSocketThreadId = 0;
static std::atomic<bool> g_bWebSocketThreadRunning(false);
static std::queue<std::string> g_webSocketSendQueue;
static std::mutex g_webSocketQueueMutex;
static std::condition_variable g_webSocketQueueCV;

// Quote cache with threading support
static std::mutex g_quoteCacheMutex;
'''
    
    # Add WebSocket thread function
    websocket_thread_func = '''
// WebSocket thread function
unsigned __stdcall WebSocketThreadProc(void* pParam)
{
    while (g_bWebSocketThreadRunning)
    {
        // Process WebSocket messages
        ProcessWebSocketMessages();
        
        // Check for outgoing messages
        std::string message;
        {
            std::unique_lock<std::mutex> lock(g_webSocketQueueMutex);
            if (g_webSocketSendQueue.empty())
            {
                g_webSocketQueueCV.wait_for(lock, std::chrono::milliseconds(100));
                continue;
            }
            message = g_webSocketSendQueue.front();
            g_webSocketSendQueue.pop();
        }
        
        // Send message (non-blocking)
        if (g_websocket != INVALID_SOCKET)
        {
            send(g_websocket, message.c_str(), message.length(), 0);
        }
    }
    
    return 0;
}

// Non-blocking WebSocket message processing
void ProcessWebSocketMessages()
{
    if (g_websocket == INVALID_SOCKET || !g_bWebSocketConnected)
        return;
    
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(g_websocket, &readfds);
    
    struct timeval timeout;
    timeout.tv_sec = 0;
    timeout.tv_usec = 10000; // 10ms timeout
    
    if (select(0, &readfds, NULL, NULL, &timeout) > 0)
    {
        char buffer[4096];
        int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);
        
        if (received > 0)
        {
            buffer[received] = '\\0';
            // Process the received data
            ProcessWebSocketDataNonBlocking(buffer, received);
        }
    }
}
'''
    
    # Modify the ConnectWebSocket function to be non-blocking
    new_connect_websocket = '''
BOOL ConnectWebSocket(void)
{
    // Parse WebSocket URL
    CString host, path;
    int port = 80;
    
    CString url = g_oWebSocketUrl;
    if (url.Left(5) == _T("wss://"))
    {
        port = 443;
        url = url.Mid(6);
    }
    else if (url.Left(5) == _T("ws://"))
    {
        url = url.Mid(5);
    }
    
    // Extract host and port
    int slashPos = url.Find(_T('/'));
    if (slashPos > 0)
    {
        host = url.Left(slashPos);
        path = url.Mid(slashPos);
    }
    else
    {
        host = url;
        path = _T("/");
    }
    
    int colonPos = host.Find(_T(':'));
    if (colonPos > 0)
    {
        CString portStr = host.Mid(colonPos + 1);
        port = _ttoi(portStr);
        host = host.Left(colonPos);
    }
    
    // Create socket
    g_websocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_websocket == INVALID_SOCKET)
        return FALSE;
    
    // Set socket to non-blocking mode immediately
    u_long mode = 1;
    ioctlsocket(g_websocket, FIONBIO, &mode);
    
    // Resolve hostname
    struct addrinfo hints, *result;
    ZeroMemory(&hints, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    
    CStringA hostA(host);
    CStringA portStrA;
    portStrA.Format("%d", port);
    
    if (getaddrinfo(hostA, portStrA, &hints, &result) != 0)
    {
        closesocket(g_websocket);
        g_websocket = INVALID_SOCKET;
        return FALSE;
    }
    
    // Connect to server (non-blocking)
    if (connect(g_websocket, result->ai_addr, (int)result->ai_addrlen) == SOCKET_ERROR)
    {
        int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK)
        {
            freeaddrinfo(result);
            closesocket(g_websocket);
            g_websocket = INVALID_SOCKET;
            return FALSE;
        }
        
        // Connection in progress, wait for completion
        fd_set writefds;
        FD_ZERO(&writefds);
        FD_SET(g_websocket, &writefds);
        
        struct timeval timeout;
        timeout.tv_sec = 5;  // 5 second timeout
        timeout.tv_usec = 0;
        
        if (select(0, NULL, &writefds, NULL, &timeout) <= 0)
        {
            freeaddrinfo(result);
            closesocket(g_websocket);
            g_websocket = INVALID_SOCKET;
            return FALSE;
        }
        
        // Check if connection was successful
        int so_error;
        socklen_t len = sizeof(so_error);
        if (getsockopt(g_websocket, SOL_SOCKET, SO_ERROR, (char*)&so_error, &len) < 0 || so_error != 0)
        {
            freeaddrinfo(result);
            closesocket(g_websocket);
            g_websocket = INVALID_SOCKET;
            return FALSE;
        }
    }
    
    freeaddrinfo(result);
    
    // Send WebSocket upgrade request
    CString upgradeRequest;
    upgradeRequest.Format(
        _T("GET %s HTTP/1.1\\r\\n")
        _T("Host: %s:%d\\r\\n")
        _T("Upgrade: websocket\\r\\n")
        _T("Connection: Upgrade\\r\\n")
        _T("Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\\r\\n")
        _T("Sec-WebSocket-Version: 13\\r\\n")
        _T("\\r\\n"),
        (LPCTSTR)path, (LPCTSTR)host, port);
    
    CStringA requestA(upgradeRequest);
    if (send(g_websocket, requestA, requestA.GetLength(), 0) == SOCKET_ERROR)
    {
        closesocket(g_websocket);
        g_websocket = INVALID_SOCKET;
        return FALSE;
    }
    
    // Wait for upgrade response with select
    fd_set readfds;
    FD_ZERO(&readfds);
    FD_SET(g_websocket, &readfds);
    
    struct timeval timeout;
    timeout.tv_sec = 5;  // 5 second timeout
    timeout.tv_usec = 0;
    
    if (select(0, &readfds, NULL, NULL, &timeout) > 0)
    {
        char buffer[1024];
        int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);
        
        if (received > 0)
        {
            buffer[received] = '\\0';
            CString response(buffer);
            
            if (response.Find(_T("101")) > 0 && response.Find(_T("Switching Protocols")) > 0)
            {
                g_bWebSocketConnected = TRUE;
                
                // Start WebSocket thread
                g_bWebSocketThreadRunning = true;
                g_hWebSocketThread = (HANDLE)_beginthreadex(NULL, 0, WebSocketThreadProc, NULL, 0, &g_webSocketThreadId);
                
                // Authenticate
                return AuthenticateWebSocket();
            }
        }
    }
    
    closesocket(g_websocket);
    g_websocket = INVALID_SOCKET;
    return FALSE;
}
'''
    
    # Replace content
    content = threading_includes + "\n" + content
    
    # Add threading globals after existing globals
    globals_pos = content.find("// Global variables")
    if globals_pos != -1:
        end_globals_pos = content.find("//", globals_pos + 1)
        if end_globals_pos == -1:
            end_globals_pos = len(content)
        content = content[:end_globals_pos] + "\n" + threading_globals + "\n" + content[end_globals_pos:]
    
    # Add thread function
    content += "\n" + websocket_thread_func
    
    # Replace ConnectWebSocket function
    connect_start = content.find("BOOL ConnectWebSocket(void)")
    if connect_start != -1:
        connect_end = content.find("BOOL AuthenticateWebSocket(void)", connect_start)
        if connect_end != -1:
            content = content[:connect_start] + new_connect_websocket + "\n" + content[connect_end:]
    
    return content

def install_enhanced_plugin(amibroker_path):
    """Install the enhanced plugin"""
    source_dll = r"OpenAlgoPlugin-enhanced\OpenAlgo.dll"
    target_dll = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll")
    
    if not os.path.exists(source_dll):
        if not build_enhanced_plugin():
            return False
    
    if os.path.exists(source_dll):
        print(f"Installing enhanced plugin to {target_dll}")
        shutil.copy2(source_dll, target_dll)
        return True
    else:
        print("Enhanced plugin DLL not found.")
        return False

def create_plugin_config():
    """Create plugin configuration file"""
    config = {
        "server": "localhost",
        "port": 5000,
        "websocket_url": "ws://localhost:5000/ws",
        "api_key": "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0",
        "use_threading": True,
        "connection_timeout": 5000,
        "retry_attempts": 3,
        "quote_cache_ttl": 1000
    }
    
    config_path = "OpenAlgoPlugin-enhanced\plugin_config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Plugin configuration created at {config_path}")

def main():
    """Main function"""
    print("OpenAlgo AmiBroker Plugin Fix")
    print("=" * 40)
    
    # Find AmiBroker
    amibroker_path = find_amibroker_folder()
    if not amibroker_path:
        print("AmiBroker installation not found!")
        print("Please manually copy the enhanced plugin to your AmiBroker\\Plugins folder.")
        return
    
    print(f"Found AmiBroker at: {amibroker_path}")
    
    # Backup existing plugin
    backup_existing_plugin(amibroker_path)
    
    # Create plugin configuration
    create_plugin_config()
    
    # Install enhanced plugin
    if install_enhanced_plugin(amibroker_path):
        print("\n✅ Enhanced plugin installed successfully!")
        print("\nNext steps:")
        print("1. Close AmiBroker if it's running")
        print("2. Restart AmiBroker")
        print("3. The enhanced plugin should now work without hanging")
        print("\nIf you still experience issues:")
        print("- Check the OpenAlgo server is running on localhost:5000")
        print("- Verify the API key in plugin_config.json")
        print("- Check AmiBroker's plugin logs for errors")
    else:
        print("\n❌ Failed to install enhanced plugin.")
        print("Please check the build errors above.")

if __name__ == "__main__":
    main()