// OpenAlgoPluginFixed.cpp - Fixed plugin that uses relay server
#include "stdafx.h"
#include "resource.h"
#include "Plugin.h"
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <queue>
#include <chrono>

#pragma comment(lib, "ws2_32.lib")

// Plugin identification
#define PLUGIN_NAME "OpenAlgo Data Plugin (Relay Fixed)"
#define VENDOR_NAME "OpenAlgo Community"
#define PLUGIN_VERSION 10005
#define PLUGIN_ID PIDCODE('O', 'A', 'R', 'F')  // OpenAlgo Relay Fixed
#define THIS_PLUGIN_TYPE PLUGIN_TYPE_DATA

// Global configuration
static std::string g_server = "127.0.0.1";
static int g_port = 8766;  // Relay server port
static std::string g_api_key = "";
static bool g_initialized = false;
static bool g_connected = false;

// Connection management
static SOCKET g_socket = INVALID_SOCKET;
static std::mutex g_socket_mutex;
static std::thread g_connection_thread;
static bool g_connection_thread_running = false;
static std::queue<std::string> g_send_queue;
static std::mutex g_send_queue_mutex;

// Quote cache for non-blocking data retrieval
struct QuoteData {
    double ltp;
    double open;
    double high;
    double low;
    double close;
    double volume;
    double oi;
    std::chrono::steady_clock::time_point timestamp;
    
    QuoteData() : ltp(0), open(0), high(0), low(0), close(0), volume(0), oi(0) {}
};

static std::map<std::string, QuoteData> g_quote_cache;
static std::mutex g_cache_mutex;

// Function declarations
static bool InitializeWinsock();
static bool ConnectToRelay();
static void DisconnectFromRelay();
static void ConnectionThreadProc();
static bool SendToRelay(const std::string& message);
static bool ReceiveFromRelay(std::string& message);
static void ProcessRelayMessage(const std::string& message);
static bool IsCacheValid(const std::string& symbol);
static void UpdateCache(const std::string& symbol, const QuoteData& data);

// Plugin API functions
PLUGINAPI int Init(void)
{
    if (g_initialized) return 1;
    
    // Load configuration from registry
    HKEY hKey;
    if (RegOpenKeyEx(HKEY_CURRENT_USER, TEXT("Software\\OpenAlgoRelay"), 0, KEY_READ, &hKey) == ERROR_SUCCESS)
    {
        char buffer[256];
        DWORD bufferSize = sizeof(buffer);
        DWORD dwType;
        
        // Read server
        if (RegQueryValueExA(hKey, "Server", NULL, &dwType, (LPBYTE)buffer, &bufferSize) == ERROR_SUCCESS)
            g_server = buffer;
            
        // Read port
        DWORD portValue;
        bufferSize = sizeof(DWORD);
        if (RegQueryValueExA(hKey, "Port", NULL, &dwType, (LPBYTE)&portValue, &bufferSize) == ERROR_SUCCESS)
            g_port = portValue;
            
        // Read API key
        bufferSize = sizeof(buffer);
        if (RegQueryValueExA(hKey, "ApiKey", NULL, &dwType, (LPBYTE)buffer, &bufferSize) == ERROR_SUCCESS)
            g_api_key = buffer;
            
        RegCloseKey(hKey);
    }
    
    // Initialize Winsock
    if (!InitializeWinsock())
        return 0;
    
    // Start connection thread
    g_connection_thread_running = true;
    g_connection_thread = std::thread(ConnectionThreadProc);
    
    g_initialized = true;
    return 1;
}

PLUGINAPI int Release(void)
{
    // Stop connection thread
    g_connection_thread_running = false;
    if (g_connection_thread.joinable())
        g_connection_thread.join();
    
    // Disconnect from relay
    DisconnectFromRelay();
    
    // Cleanup Winsock
    WSACleanup();
    
    g_initialized = false;
    return 1;
}

PLUGINAPI int GetQuotesEx(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes, GQEContext* pContext)
{
    std::string symbol = CT2A(pszTicker);
    
    // Return existing data if not connected (non-blocking behavior)
    if (!g_connected)
        return nLastValid + 1;
    
    // Check cache first
    {
        std::lock_guard<std::mutex> lock(g_cache_mutex);
        if (IsCacheValid(symbol))
        {
            const QuoteData& cached = g_quote_cache[symbol];
            if (nLastValid + 1 < nSize)
            {
                struct Quotation& quote = pQuotes[nLastValid + 1];
                quote.Price = cached.ltp;
                quote.Open = cached.open;
                quote.High = cached.high;
                quote.Low = cached.low;
                quote.Volume = cached.volume;
                quote.OpenInterest = cached.oi;
                quote.DateTime.Date = GetCurrentDateTime();
                return nLastValid + 2;
            }
        }
    }
    
    // Request fresh data from relay (non-blocking)
    std::string request = "{\"type\":\"get_quote\",\"symbol\":\"" + symbol + "\"}";
    SendToRelay(request);
    
    // Return existing data to prevent blocking
    return nLastValid + 1;
}

PLUGINAPI AmiVar GetExtraData(LPCTSTR pszTicker, LPCTSTR pszFieldName, int nFieldType)
{
    AmiVar result;
    result.type = VAR_FLOAT;
    result.val = 0;
    
    std::string symbol = CT2A(pszTicker);
    std::string field = CT2A(pszFieldName);
    std::transform(field.begin(), field.end(), field.begin(), ::toupper);
    
    {
        std::lock_guard<std::mutex> lock(g_cache_mutex);
        if (g_quote_cache.find(symbol) != g_quote_cache.end() && IsCacheValid(symbol))
        {
            const QuoteData& quote = g_quote_cache[symbol];
            
            if (field == "LTP") result.val = quote.ltp;
            else if (field == "OPEN") result.val = quote.open;
            else if (field == "HIGH") result.val = quote.high;
            else if (field == "LOW") result.val = quote.low;
            else if (field == "CLOSE") result.val = quote.close;
            else if (field == "VOLUME") result.val = quote.volume;
            else if (field == "OI") result.val = quote.oi;
        }
    }
    
    return result;
}

PLUGINAPI int GetStatus(LPCTSTR pszTicker, int nPeriodicity)
{
    return g_connected ? STATUS_CONNECTED : STATUS_DISCONNECTED;
}

PLUGINAPI int Configure(HWND hParent)
{
    // Simple configuration dialog would go here
    MessageBox(hParent, TEXT("Configure OpenAlgo Relay settings in registry:\\n")
               TEXT("HKEY_CURRENT_USER\\Software\\OpenAlgoRelay\\\n")
               TEXT("Server, Port, ApiKey"), TEXT("OpenAlgo Relay Configuration"), MB_OK);
    return 1;
}

// Helper functions
static bool InitializeWinsock()
{
    WSADATA wsaData;
    return WSAStartup(MAKEWORD(2, 2), &wsaData) == 0;
}

static bool ConnectToRelay()
{
    std::lock_guard<std::mutex> lock(g_socket_mutex);
    
    if (g_socket != INVALID_SOCKET)
        return true;
    
    // Create socket
    g_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_socket == INVALID_SOCKET)
        return false;
    
    // Set non-blocking mode
    u_long mode = 1;
    ioctlsocket(g_socket, FIONBIO, &mode);
    
    // Resolve address
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(g_port);
    inet_pton(AF_INET, g_server.c_str(), &addr.sin_addr);
    
    // Connect with timeout
    int result = connect(g_socket, (struct sockaddr*)&addr, sizeof(addr));
    if (result == SOCKET_ERROR)
    {
        int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK)
        {
            closesocket(g_socket);
            g_socket = INVALID_SOCKET;
            return false;
        }
        
        // Wait for connection with select
        fd_set writefds;
        FD_ZERO(&writefds);
        FD_SET(g_socket, &writefds);
        
        struct timeval tv;
        tv.tv_sec = 2;  // 2 second timeout
        tv.tv_usec = 0;
        
        if (select(0, NULL, &writefds, NULL, &tv) <= 0)
        {
            closesocket(g_socket);
            g_socket = INVALID_SOCKET;
            return false;
        }
    }
    
    // Send authentication
    std::string auth_msg = "{\"type\":\"auth\",\"api_key\":\"" + g_api_key + "\"}";
    if (!SendToRelay(auth_msg))
    {
        closesocket(g_socket);
        g_socket = INVALID_SOCKET;
        return false;
    }
    
    g_connected = true;
    return true;
}

static void DisconnectFromRelay()
{
    std::lock_guard<std::mutex> lock(g_socket_mutex);
    
    g_connected = false;
    
    if (g_socket != INVALID_SOCKET)
    {
        closesocket(g_socket);
        g_socket = INVALID_SOCKET;
    }
}

static void ConnectionThreadProc()
{
    while (g_connection_thread_running)
    {
        if (!g_connected)
        {
            // Try to connect
            if (ConnectToRelay())
            {
                // Connection successful, start receiving
                std::string message;
                while (g_connected && g_connection_thread_running)
                {
                    if (ReceiveFromRelay(message))
                    {
                        ProcessRelayMessage(message);
                    }
                    
                    // Process send queue
                    {
                        std::lock_guard<std::mutex> lock(g_send_queue_mutex);
                        while (!g_send_queue.empty())
                        {
                            std::string msg = g_send_queue.front();
                            g_send_queue.pop();
                            SendToRelay(msg);
                        }
                    }
                    
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                }
            }
            else
            {
                // Connection failed, wait before retry
                std::this_thread::sleep_for(std::chrono::seconds(5));
            }
        }
        else
        {
            // Already connected, just maintain connection
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
}

static bool SendToRelay(const std::string& message)
{
    std::lock_guard<std::mutex> lock(g_socket_mutex);
    
    if (g_socket == INVALID_SOCKET)
        return false;
    
    // Add newline delimiter
    std::string msg = message + "\n";
    
    int result = send(g_socket, msg.c_str(), msg.length(), 0);
    return result != SOCKET_ERROR;
}

static bool ReceiveFromRelay(std::string& message)
{
    std::lock_guard<std::mutex> lock(g_socket_mutex);
    
    if (g_socket == INVALID_SOCKET)
        return false;
    
    char buffer[4096];
    int result = recv(g_socket, buffer, sizeof(buffer) - 1, 0);
    
    if (result > 0)
    {
        buffer[result] = '\0';
        message = buffer;
        return true;
    }
    else if (result == 0)
    {
        // Connection closed
        g_connected = false;
        return false;
    }
    
    return false;
}

static void ProcessRelayMessage(const std::string& message)
{
    // Simple JSON parsing for quote data
    if (message.find("\"type\":\"quote\"") != std::string::npos)
    {
        // Extract symbol
        size_t symbol_pos = message.find("\"symbol\":\"");
        if (symbol_pos != std::string::npos)
        {
            symbol_pos += 10;
            size_t symbol_end = message.find("\"", symbol_pos);
            if (symbol_end != std::string::npos)
            {
                std::string symbol = message.substr(symbol_pos, symbol_end - symbol_pos);
                
                // Extract price data
                QuoteData quote;
                
                size_t ltp_pos = message.find("\"ltp\":");
                if (ltp_pos != std::string::npos)
                {
                    quote.ltp = std::stod(message.substr(ltp_pos + 6));
                    quote.close = quote.ltp;
                }
                
                size_t open_pos = message.find("\"open\":");
                if (open_pos != std::string::npos)
                {
                    quote.open = std::stod(message.substr(open_pos + 7));
                }
                
                size_t high_pos = message.find("\"high\":");
                if (high_pos != std::string::npos)
                {
                    quote.high = std::stod(message.substr(high_pos + 7));
                }
                
                size_t low_pos = message.find("\"low\":");
                if (low_pos != std::string::npos)
                {
                    quote.low = std::stod(message.substr(low_pos + 6));
                }
                
                size_t vol_pos = message.find("\"volume\":");
                if (vol_pos != std::string::npos)
                {
                    quote.volume = std::stod(message.substr(vol_pos + 9));
                }
                
                quote.timestamp = std::chrono::steady_clock::now();
                
                // Update cache
                UpdateCache(symbol, quote);
            }
        }
    }
}

static bool IsCacheValid(const std::string& symbol)
{
    auto it = g_quote_cache.find(symbol);
    if (it == g_quote_cache.end())
        return false;
    
    auto now = std::chrono::steady_clock::now();
    auto age = std::chrono::duration_cast<std::chrono::seconds>(now - it->second.timestamp).count();
    
    return age < 5;  // Valid for 5 seconds
}

static void UpdateCache(const std::string& symbol, const QuoteData& data)
{
    std::lock_guard<std::mutex> lock(g_cache_mutex);
    g_quote_cache[symbol] = data;
}

static double GetCurrentDateTime()
{
    // Return current time in AmiBroker format
    time_t now = time(NULL);
    struct tm* tm = localtime(&now);
    
    // Pack datetime in AmiBroker format
    union AmiDate date;
    date.PackDate.Year = tm->tm_year + 1900;
    date.PackDate.Month = tm->tm_mon + 1;
    date.PackDate.Day = tm->tm_mday;
    date.PackDate.Hour = tm->tm_hour;
    date.PackDate.Minute = tm->tm_min;
    date.PackDate.Second = tm->tm_sec;
    
    return date.Date;
}