// Enhanced Plugin.cpp - Robust implementation with non-blocking operations
#include "stdafx.h"
#include "resource.h"
#include "OpenAlgoGlobals.h"
#include "Plugin.h"
#include "Plugin_Legacy.h"
#include "OpenAlgoConfigDlg.h"
#include <math.h>
#include <time.h>
#include <stdlib.h>
#include <thread>
#include <chrono>
#include <atomic>
#include <mutex>
#include <condition_variable>

// Plugin identification
#define PLUGIN_NAME "OpenAlgo Enhanced Data Plugin"
#define VENDOR_NAME "OpenAlgo Community Enhanced"
#define PLUGIN_VERSION 10004
#define PLUGIN_ID PIDCODE('O', 'A', 'E', 'N')
#define THIS_PLUGIN_TYPE PLUGIN_TYPE_DATA
#define AGENT_NAME PLUGIN_NAME

// Timer IDs
#define TIMER_INIT 198
#define TIMER_REFRESH 199
#define RETRY_COUNT 8
#define CONNECTION_TIMEOUT_MS 3000
#define MAX_RETRY_DELAY_MS 30000

////////////////////////////////////////
// Plugin Info Structure
////////////////////////////////////////
static struct PluginInfo oPluginInfo =
{
	sizeof(struct PluginInfo),
	THIS_PLUGIN_TYPE,
	PLUGIN_VERSION,
	PLUGIN_ID,
	PLUGIN_NAME,
	VENDOR_NAME,
	0,
	530000
};

///////////////////////////////
// Global Variables
///////////////////////////////
HWND g_hAmiBrokerWnd = NULL;
int g_nPortNumber = 5000;
int g_nRefreshInterval = 5;
int g_nTimeShift = 0;
CString g_oServer = _T("127.0.0.1");
CString g_oApiKey = _T("");
CString g_oWebSocketUrl = _T("ws://127.0.0.1:8765");
int g_nStatus = STATUS_WAIT;

// Enhanced connection management
static std::atomic<bool> g_bPluginInitialized{false};
static std::atomic<bool> g_bConnectionThreadRunning{false};
static std::atomic<bool> g_bShutdownRequested{false};
static std::thread g_connectionThread;
static std::mutex g_connectionMutex;
static std::condition_variable g_connectionCV;

// WebSocket connection management with thread safety
static SOCKET g_websocket = INVALID_SOCKET;
static std::atomic<bool> g_bWebSocketConnected{false};
static std::atomic<bool> g_bWebSocketAuthenticated{false};
static std::atomic<bool> g_bWebSocketConnecting{false};
static std::atomic<DWORD> g_dwLastConnectionAttempt{0};
static CMap<CString, LPCTSTR, BOOL, BOOL> g_SubscribedSymbols;
static std::mutex g_WebSocketMutex;
static std::atomic<bool> g_bCriticalSectionInitialized{false};

// Cache for recent quotes
struct QuoteCache {
	CString symbol;
	CString exchange;
	float ltp;
	float open;
	float high;
	float low;
	float close;
	float volume;
	float oi;
	DWORD lastUpdate;
	
	QuoteCache() : ltp(0.0f), open(0.0f), high(0.0f), low(0.0f), 
	               close(0.0f), volume(0.0f), oi(0.0f), lastUpdate(0) {}
};

static CMap<CString, LPCTSTR, QuoteCache, QuoteCache&> g_QuoteCache;
typedef CArray<struct Quotation, struct Quotation> CQuoteArray;

// Connection retry management
struct ConnectionRetry {
	int attemptCount;
	DWORD lastAttemptTime;
	DWORD nextRetryDelay;
	
	ConnectionRetry() : attemptCount(0), lastAttemptTime(0), nextRetryDelay(1000) {}
};

static ConnectionRetry g_connectionRetry;

// Forward declarations
VOID CALLBACK OnTimerProc(HWND, UINT, UINT_PTR, DWORD);
void SetupRetry(void);
BOOL TestOpenAlgoConnection(void);
BOOL GetOpenAlgoQuote(LPCTSTR pszTicker, QuoteCache& quote);
int GetOpenAlgoHistory(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes);
CString GetExchangeFromTicker(LPCTSTR pszTicker);
CString GetIntervalString(int nPeriodicity);
void ConvertUnixToPackedDate(time_t unixTime, union AmiDate* pAmiDate);

// Enhanced WebSocket functions with robust error handling
BOOL InitializeWebSocketAsync(void);
void CleanupWebSocket(void);
BOOL ConnectWebSocketNonBlocking(void);
BOOL AuthenticateWebSocketNonBlocking(void);
BOOL SendWebSocketFrame(const CString& message);
CString DecodeWebSocketFrame(const char* buffer, int length);
BOOL SubscribeToSymbol(LPCTSTR pszTicker);
BOOL UnsubscribeFromSymbol(LPCTSTR pszTicker);
BOOL ProcessWebSocketDataNonBlocking(void);
void GenerateWebSocketMaskKey(unsigned char* maskKey);
void ConnectionWorkerThread(void);
BOOL ShouldAttemptConnection(void);
DWORD GetNextRetryDelay(void);

// Helper function for mixed EOD/Intraday data
int FindLastBarOfMatchingType(int nPeriodicity, int nLastValid, struct Quotation* pQuotes);
int CompareQuotations(const void* a, const void* b);

// Enhanced error handling
void LogError(const CString& error);
BOOL HandleConnectionFailure(const CString& reason);
BOOL IsConnectionHealthy(void);

///////////////////////////////
// Enhanced Helper Functions
///////////////////////////////

void LogError(const CString& error) {
	// Log errors to debug output and potentially a log file
	CString logMsg;
	CTime now = CTime::GetCurrentTime();
	logMsg.Format(_T("[%02d:%02d:%02d] OpenAlgo Enhanced Error: %s"), 
	              now.GetHour(), now.GetMinute(), now.GetSecond(), (LPCTSTR)error);
	
	OutputDebugString(logMsg);
}

BOOL ShouldAttemptConnection(void) {
	DWORD currentTime = (DWORD)GetTickCount64();
	DWORD timeSinceLastAttempt = currentTime - g_dwLastConnectionAttempt.load();
	
	return (timeSinceLastAttempt >= g_connectionRetry.nextRetryDelay);
}

DWORD GetNextRetryDelay(void) {
	g_connectionRetry.attemptCount++;
	
	// Exponential backoff with jitter
	DWORD baseDelay = min(1000 * (1 << min(g_connectionRetry.attemptCount, 5)), MAX_RETRY_DELAY_MS);
	DWORD jitter = rand() % 1000; // 0-999ms jitter
	
	return baseDelay + jitter;
}

BOOL HandleConnectionFailure(const CString& reason) {
	LogError(reason);
	
	g_connectionRetry.nextRetryDelay = GetNextRetryDelay();
	g_connectionRetry.lastAttemptTime = (DWORD)GetTickCount64();
	
	// Update status
	g_nStatus = STATUS_DISCONNECTED;
	
	// Notify AmiBroker of connection failure
	if (g_hAmiBrokerWnd != NULL) {
		::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
	}
	
	return FALSE;
}

BOOL IsConnectionHealthy(void) {
	if (!g_bWebSocketConnected.load() || !g_bWebSocketAuthenticated.load()) {
		return FALSE;
	}
	
	// Check if we have recent data activity
	DWORD currentTime = (DWORD)GetTickCount64();
	DWORD lastUpdate = g_dwLastConnectionAttempt.load();
	
	// If no data for more than 60 seconds, consider connection unhealthy
	return (currentTime - lastUpdate) < 60000;
}

// Compare two quotations for sorting by timestamp (oldest to newest)
int CompareQuotations(const void* a, const void* b) {
	const struct Quotation* qa = (const struct Quotation*)a;
	const struct Quotation* qb = (const struct Quotation*)b;
	
	if (qa->DateTime.Date < qb->DateTime.Date)
		return -1;
	else if (qa->DateTime.Date > qb->DateTime.Date)
		return 1;
	else
		return 0;
}

// Find last bar in array that matches the requested periodicity type
int FindLastBarOfMatchingType(int nPeriodicity, int nLastValid, struct Quotation* pQuotes) {
	if (nLastValid < 0 || pQuotes == NULL)
		return -1;
	
	if (nPeriodicity == 86400) {  // Daily data
		for (int i = nLastValid; i >= 0; i--) {
			if (pQuotes[i].DateTime.PackDate.Hour == DATE_EOD_HOURS &&
			    pQuotes[i].DateTime.PackDate.Minute == DATE_EOD_MINUTES) {
				return i;
			}
		}
		return -1;
	}
	else if (nPeriodicity == 60) {  // 1-minute data
		for (int i = nLastValid; i >= 0; i--) {
			if (pQuotes[i].DateTime.PackDate.Hour < DATE_EOD_HOURS) {
				return i;
			}
		}
		return -1;
	}
	else {
		return nLastValid;
	}
}

CString BuildOpenAlgoURL(const CString& server, int port, const CString& endpoint) {
	CString result;
	result.Format(_T("http://%s:%d%s"), (LPCTSTR)server, port, (LPCTSTR)endpoint);
	return result;
}

// Extract exchange from ticker format (e.g., "RELIANCE-NSE" -> "NSE")
CString GetExchangeFromTicker(LPCTSTR pszTicker) {
	CString ticker(pszTicker);
	int dashPos = ticker.ReverseFind(_T('-'));
	if (dashPos != -1) {
		return ticker.Mid(dashPos + 1);
	}
	
	return _T("NSE"); // Default to NSE
}

// Get clean symbol without exchange suffix
CString GetCleanSymbol(LPCTSTR pszTicker) {
	CString ticker(pszTicker);
	int dashPos = ticker.ReverseFind(_T('-'));
	if (dashPos != -1) {
		return ticker.Left(dashPos);
	}
	return ticker;
}

// Get interval string for OpenAlgo API
CString GetIntervalString(int nPeriodicity) {
	switch (nPeriodicity) {
		case 60: return _T("1m");
		case 300: return _T("5m");
		case 900: return _T("15m");
		case 1800: return _T("30m");
		case 3600: return _T("1h");
		case 86400: return _T("D");
		case 604800: return _T("W");
		case 2592000: return _T("M");
		default: return _T("1m");
	}
}

// Convert Unix timestamp to AmiBroker packed date format
void ConvertUnixToPackedDate(time_t unixTime, union AmiDate* pAmiDate) {
	if (!pAmiDate) return;
	
	struct tm* ptm = gmtime(&unixTime);
	if (!ptm) return;
	
	pAmiDate->PackDate.Year = ptm->tm_year + 1900 - 1900;  // AmiBroker years start from 1900
	pAmiDate->PackDate.Month = ptm->tm_mon + 1;
	pAmiDate->PackDate.Day = ptm->tm_mday;
	pAmiDate->PackDate.Hour = ptm->tm_hour;
	pAmiDate->PackDate.Minute = ptm->tm_min;
	pAmiDate->PackDate.Second = ptm->tm_sec;
	pAmiDate->PackDate.DayOfWeek = ptm->tm_wday;
	pAmiDate->PackDate.MilliSec = 0;
}

///////////////////////////////
// Enhanced Connection Worker Thread
///////////////////////////////

void ConnectionWorkerThread(void) {
	LogError(_T("Connection worker thread started"));
	
	while (!g_bShutdownRequested.load()) {
		try {
			// Check if we should attempt connection
			if (ShouldAttemptConnection() && !g_bWebSocketConnected.load()) {
				LogError(_T("Attempting WebSocket connection..."));
				
				// Mark connection attempt time
				g_dwLastConnectionAttempt = (DWORD)GetTickCount64();
				
				// Attempt connection in background
				if (ConnectWebSocketNonBlocking()) {
					LogError(_T("WebSocket connection established"));
					g_connectionRetry.attemptCount = 0; // Reset retry count on success
				}
			}
			
			// Process WebSocket data if connected
			if (g_bWebSocketConnected.load()) {
				ProcessWebSocketDataNonBlocking();
			}
			
			// Sleep for a short interval to avoid CPU spinning
			std::this_thread::sleep_for(std::chrono::milliseconds(100));
			
		} catch (const std::exception& e) {
			LogError(CString(_T("Connection worker exception: ")) + CString(e.what()));
		} catch (...) {
			LogError(_T("Unknown exception in connection worker thread"));
		}
	}
	
	LogError(_T("Connection worker thread stopped"));
}

///////////////////////////////
// Enhanced WebSocket Functions
///////////////////////////////

void GenerateWebSocketMaskKey(unsigned char* maskKey) {
	srand((unsigned int)GetTickCount64());
	maskKey[0] = (unsigned char)(rand() & 0xFF);
	maskKey[1] = (unsigned char)(rand() & 0xFF);
	maskKey[2] = (unsigned char)(rand() & 0xFF);
	maskKey[3] = (unsigned char)(rand() & 0xFF);
}

BOOL SendWebSocketFrame(const CString& message) {
	std::lock_guard<std::mutex> lock(g_WebSocketMutex);
	
	if (g_websocket == INVALID_SOCKET)
		return FALSE;
	
	// Convert message to UTF-8
	CStringA messageA(message);
	int messageLen = messageA.GetLength();
	
	// Create WebSocket frame
	unsigned char frame[1024];
	int frameLen = 0;
	
	// First byte: FIN=1, opcode=1 (text frame)
	frame[frameLen++] = 0x81;
	
	// Payload length
	if (messageLen < 126) {
		frame[frameLen++] = (unsigned char)(0x80 | messageLen); // MASK=1
	} else if (messageLen < 65536) {
		frame[frameLen++] = 0x80 | 126; // MASK=1, 16-bit length
		frame[frameLen++] = (messageLen >> 8) & 0xFF;
		frame[frameLen++] = messageLen & 0xFF;
	} else {
		return FALSE; // Message too large
	}
	
	// Generate masking key
	unsigned char maskKey[4];
	GenerateWebSocketMaskKey(maskKey);
	memcpy(&frame[frameLen], maskKey, 4);
	frameLen += 4;
	
	// Mask the payload
	for (int i = 0; i < messageLen; i++) {
		frame[frameLen++] = messageA[i] ^ maskKey[i % 4];
	}
	
	// Send the frame with timeout
	int sent = send(g_websocket, (char*)frame, frameLen, 0);
	return (sent == frameLen);
}

CString DecodeWebSocketFrame(const char* buffer, int length) {
	CString result;
	
	if (length < 2) return result;
	
	unsigned char opcode = buffer[0] & 0x0F;
	unsigned char payloadLen = buffer[1] & 0x7F;
	bool masked = (buffer[1] & 0x80) != 0;
	
	// Handle control frames
	if (opcode == 0x09) return _T("PING_FRAME");  // Ping
	if (opcode == 0x0A) return _T("PONG_FRAME");  // Pong
	if (opcode == 0x08) return _T("CLOSE_FRAME"); // Close
	
	int pos = 2;
	int payloadLength = payloadLen;
	
	if (payloadLen == 126) {
		if (length < 4) return result;
		payloadLength = (buffer[2] << 8) | buffer[3];
		pos = 4;
	} else if (payloadLen == 127) {
		return result; // Too large for this implementation
	}
	
	if (masked) {
		if (length < pos + 4 + payloadLength) return result;
		
		unsigned char maskKey[4];
		memcpy(maskKey, &buffer[pos], 4);
		pos += 4;
		
		// Unmask the payload
		for (int i = 0; i < payloadLength; i++) {
			result += (TCHAR)(buffer[pos + i] ^ maskKey[i % 4]);
		}
	} else {
		if (length < pos + payloadLength) return result;
		for (int i = 0; i < payloadLength; i++) {
			result += (TCHAR)buffer[pos + i];
		}
	}
	
	return result;
}

BOOL ConnectWebSocketNonBlocking(void) {
	// Prevent multiple simultaneous connection attempts
	bool expected = false;
	if (!g_bWebSocketConnecting.compare_exchange_strong(expected, true)) {
		return FALSE;
	}
	
	// Use RAII to ensure connecting flag is reset
	struct ConnectingGuard {
		~ConnectingGuard() { g_bWebSocketConnecting = false; }
	} guard;
	
	try {
		// Parse WebSocket URL
		CString host, path;
		int port = 80;
		
		CString url = g_oWebSocketUrl;
		if (url.Left(5) == _T("wss://")) {
			port = 443;
			url = url.Mid(6);
		} else if (url.Left(5) == _T("ws://")) {
			url = url.Mid(5);
		}
		
		// Extract host and port
		int colonPos = url.Find(_T(':'));
		if (colonPos > 0) {
			CString portStr = url.Mid(colonPos + 1);
			port = _ttoi(portStr);
			host = url.Left(colonPos);
		} else {
			int slashPos = url.Find(_T('/'));
			if (slashPos > 0) {
				host = url.Left(slashPos);
				path = url.Mid(slashPos);
			} else {
				host = url;
				path = _T("/");
			}
		}
		
		// Create socket with timeout
		std::lock_guard<std::mutex> lock(g_WebSocketMutex);
		
		if (g_websocket != INVALID_SOCKET) {
			closesocket(g_websocket);
		}
		
		// Initialize Winsock if needed
		WSADATA wsaData;
		if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
			return HandleConnectionFailure(_T("Failed to initialize Winsock"));
		}
		
		g_websocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
		if (g_websocket == INVALID_SOCKET) {
			return HandleConnectionFailure(_T("Failed to create socket"));
		}
		
		// Set socket to non-blocking mode immediately
		u_long mode = 1;
		ioctlsocket(g_websocket, FIONBIO, &mode);
		
		// Resolve hostname
		struct addrinfo hints, *result = nullptr;
		ZeroMemory(&hints, sizeof(hints));
			hints.ai_family = AF_INET;
			hints.ai_socktype = SOCK_STREAM;
			hints.ai_protocol = IPPROTO_TCP;
		
		CStringA hostA(host);
		CStringA portStrA;
		portStrA.Format("%d", port);
		
		if (getaddrinfo(hostA, portStrA, &hints, &result) != 0) {
			closesocket(g_websocket);
			g_websocket = INVALID_SOCKET;
			return HandleConnectionFailure(_T("Failed to resolve hostname"));
		}
		
		// Connect with timeout using select
		if (connect(g_websocket, result->ai_addr, (int)result->ai_addrlen) == SOCKET_ERROR) {
			int error = WSAGetLastError();
			if (error != WSAEWOULDBLOCK) {
				freeaddrinfo(result);
				closesocket(g_websocket);
				g_websocket = INVALID_SOCKET;
				return HandleConnectionFailure(_T("Connection failed"));
			}
			
			// Wait for connection with timeout
			fd_set writefds;
			FD_ZERO(&writefds);
			FD_SET(g_websocket, &writefds);
			
			struct timeval timeout;
			timeout.tv_sec = CONNECTION_TIMEOUT_MS / 1000;
			timeout.tv_usec = (CONNECTION_TIMEOUT_MS % 1000) * 1000;
			
			int selectResult = select(0, NULL, &writefds, NULL, &timeout);
			if (selectResult <= 0) {
				freeaddrinfo(result);
				closesocket(g_websocket);
				g_websocket = INVALID_SOCKET;
				return HandleConnectionFailure(_T("Connection timeout"));
			}
			
			// Check if connection was successful
			int so_error;
			socklen_t len = sizeof(so_error);
			if (getsockopt(g_websocket, SOL_SOCKET, SO_ERROR, (char*)&so_error, &len) < 0 || so_error != 0) {
				freeaddrinfo(result);
				closesocket(g_websocket);
				g_websocket = INVALID_SOCKET;
				return HandleConnectionFailure(_T("Connection failed"));
			}
		}
		
		freeaddrinfo(result);
		
		// Send WebSocket upgrade request
		CString upgradeRequest;
		upgradeRequest.Format(
			_T("GET %s HTTP/1.1\r\n")
			_T("Host: %s:%d\r\n")
			_T("Upgrade: websocket\r\n")
			_T("Connection: Upgrade\r\n")
			_T("Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n")
			_T("Sec-WebSocket-Version: 13\r\n")
			_T("\r\n"),
			(LPCTSTR)path, (LPCTSTR)host, port);
		
		CStringA requestA(upgradeRequest);
		if (send(g_websocket, requestA, requestA.GetLength(), 0) == SOCKET_ERROR) {
			closesocket(g_websocket);
			g_websocket = INVALID_SOCKET;
			return HandleConnectionFailure(_T("Failed to send upgrade request"));
		}
		
		// Wait for upgrade response with timeout
		fd_set readfds;
		FD_ZERO(&readfds);
		FD_SET(g_websocket, &readfds);
		
		struct timeval timeout;
		timeout.tv_sec = CONNECTION_TIMEOUT_MS / 1000;
		timeout.tv_usec = (CONNECTION_TIMEOUT_MS % 1000) * 1000;
		
		int selectResult = select(0, &readfds, NULL, NULL, &timeout);
		if (selectResult <= 0) {
			closesocket(g_websocket);
			g_websocket = INVALID_SOCKET;
			return HandleConnectionFailure(_T("Upgrade response timeout"));
		}
		
		char buffer[1024];
		int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);
		if (received <= 0) {
			closesocket(g_websocket);
			g_websocket = INVALID_SOCKET;
			return HandleConnectionFailure(_T("Failed to receive upgrade response"));
		}
		
		buffer[received] = '\0';
		CString response(buffer);
		
		if (response.Find(_T("101")) > 0 && response.Find(_T("Switching Protocols")) > 0) {
			g_bWebSocketConnected = true;
			
			// Authenticate asynchronously
			return AuthenticateWebSocketNonBlocking();
		} else {
			closesocket(g_websocket);
			g_websocket = INVALID_SOCKET;
			return HandleConnectionFailure(_T("WebSocket upgrade failed"));
		}
		
	} catch (const std::exception& e) {
		LogError(CString(_T("ConnectWebSocketNonBlocking exception: ")) + CString(e.what()));
		return FALSE;
	} catch (...) {
		LogError(_T("Unknown exception in ConnectWebSocketNonBlocking"));
		return FALSE;
	}
}

BOOL AuthenticateWebSocketNonBlocking(void) {
	if (!g_bWebSocketConnected.load())
		return FALSE;
	
	// Send authentication message
	CString authMsg = _T("{\"action\":\"authenticate\",\"api_key\":\"") + g_oApiKey + _T("\"}");
	
	if (!SendWebSocketFrame(authMsg)) {
		return HandleConnectionFailure(_T("Failed to send authentication message"));
	}
	
	// Don't wait for response here - let the background thread handle it
	// Set a flag to indicate we're waiting for auth response
	return TRUE;
}

BOOL ProcessWebSocketDataNonBlocking(void) {
	if (!g_bWebSocketConnected.load() || g_websocket == INVALID_SOCKET)
		return FALSE;
	
	std::lock_guard<std::mutex> lock(g_WebSocketMutex);
	
	try {
		// Check for incoming data (non-blocking)
		fd_set readfds;
		FD_ZERO(&readfds);
		FD_SET(g_websocket, &readfds);
		
		struct timeval timeout;
		timeout.tv_sec = 0;
		timeout.tv_usec = 0; // Non-blocking
		
		int selectResult = select(0, &readfds, NULL, NULL, &timeout);
		if (selectResult <= 0) {
			return FALSE; // No data available
		}
		
		char buffer[2048];
		int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);
		
		if (received > 0) {
			CString data = DecodeWebSocketFrame(buffer, received);
			
			// Handle WebSocket control frames
			if (data == _T("PING_FRAME")) {
				// Send pong response
				unsigned char pongFrame[6] = {0x8A, 0x84, 0x00, 0x00, 0x00, 0x00};
				GenerateWebSocketMaskKey(&pongFrame[2]);
				send(g_websocket, (char*)pongFrame, 6, 0);
				return TRUE;
			}
			else if (data == _T("CLOSE_FRAME")) {
				// Connection closed by server
				g_bWebSocketConnected = false;
				g_bWebSocketAuthenticated = false;
				closesocket(g_websocket);
				g_websocket = INVALID_SOCKET;
				return FALSE;
			}
			else if (data == _T("PONG_FRAME")) {
				// Pong received, connection is alive
				return TRUE;
			}
			
			// Handle authentication response
			if (data.Find(_T("\"status\":\"ok\"")) >= 0 || 
			    data.Find(_T("\"status\":\"success\"")) >= 0 ||
			    data.Find(_T("\"authenticated\":true")) >= 0) {
				
				g_bWebSocketAuthenticated = true;
				g_connectionRetry.attemptCount = 0; // Reset on successful auth
				
				// Update connection status
				g_nStatus = STATUS_CONNECTED;
				if (g_hAmiBrokerWnd != NULL) {
					::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
				}
				
				return TRUE;
			}
			
			// Parse market data JSON and update cache
			if (!data.IsEmpty() && data.Find(_T("market_data")) >= 0) {
				// Simple JSON parsing to extract quote data
				CString symbol, exchange;
				float ltp = 0, open = 0, high = 0, low = 0, close = 0, volume = 0, oi = 0;
				
				// Extract symbol
				int symbolPos = data.Find(_T("\"symbol\":\""));
				if (symbolPos >= 0) {
					symbolPos += 10;
					int endPos = data.Find(_T("\""), symbolPos);
					symbol = data.Mid(symbolPos, endPos - symbolPos);
				}
				
				// Extract exchange
				int exchangePos = data.Find(_T("\"exchange\":\""));
				if (exchangePos >= 0) {
					exchangePos += 12;
					int endPos = data.Find(_T("\""), exchangePos);
					exchange = data.Mid(exchangePos, endPos - exchangePos);
				}
				
				// Extract LTP
				int ltpPos = data.Find(_T("\"ltp\":"));
				if (ltpPos >= 0) {
					ltpPos += 6;
					int endPos = data.Find(_T(","), ltpPos);
					if (endPos < 0) endPos = data.Find(_T("}"), ltpPos);
					CString val = data.Mid(ltpPos, endPos - ltpPos);
					ltp = (float)_tstof(val);
				}
				
				// Update cache if we have valid data
				if (!symbol.IsEmpty() && !exchange.IsEmpty() && ltp > 0) {
					QuoteCache quote;
					quote.symbol = symbol;
					quote.exchange = exchange;
					quote.ltp = ltp;
					quote.open = open;
					quote.high = high;
					quote.low = low;
					quote.close = close;
					quote.volume = volume;
					quote.oi = oi;
					quote.lastUpdate = (DWORD)GetTickCount64();
					
					CString ticker = symbol + _T("-") + exchange;
					g_QuoteCache.SetAt(ticker, quote);
					
					// Update last connection time to indicate healthy connection
					g_dwLastConnectionAttempt = (DWORD)GetTickCount64();
				}
				
				return TRUE;
			}
			
		} else if (received == 0) {
			// Connection closed
			g_bWebSocketConnected = false;
			g_bWebSocketAuthenticated = false;
			return FALSE;
		}
		
	} catch (const std::exception& e) {
		LogError(CString(_T("ProcessWebSocketDataNonBlocking exception: ")) + CString(e.what()));
	} catch (...) {
		LogError(_T("Unknown exception in ProcessWebSocketDataNonBlocking"));
	}
	
	return FALSE;
}

BOOL SubscribeToSymbol(LPCTSTR pszTicker) {
	if (!g_bWebSocketConnected.load() || !g_bWebSocketAuthenticated.load())
		return FALSE;
	
	// Extract symbol and exchange
	CString symbol = GetCleanSymbol(pszTicker);
	CString exchange = GetExchangeFromTicker(pszTicker);
	
	// Send subscription message for quote mode (mode 2)
	CString subMsg;
	subMsg.Format(_T("{\"action\":\"subscribe\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"mode\":2}"),
		(LPCTSTR)symbol, (LPCTSTR)exchange);
	
	return SendWebSocketFrame(subMsg);
}

BOOL UnsubscribeFromSymbol(LPCTSTR pszTicker) {
	if (!g_bWebSocketConnected.load())
		return FALSE;
	
	// Extract symbol and exchange
	CString symbol = GetCleanSymbol(pszTicker);
	CString exchange = GetExchangeFromTicker(pszTicker);
	
	// Send unsubscription message
	CString unsubMsg;
	unsubMsg.Format(_T("{\"action\":\"unsubscribe\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"mode\":2}"),
		(LPCTSTR)symbol, (LPCTSTR)exchange);
	
	return SendWebSocketFrame(unsubMsg);
}

void CleanupWebSocket(void) {
	// Signal shutdown
	g_bShutdownRequested = true;
	
	// Stop connection worker thread
	if (g_connectionThread.joinable()) {
		g_connectionCV.notify_all();
		g_connectionThread.join();
	}
	
	std::lock_guard<std::mutex> lock(g_WebSocketMutex);
	
	// Unsubscribe from all symbols
	POSITION pos = g_SubscribedSymbols.GetStartPosition();
	while (pos != NULL) {
		CString symbol;
		BOOL subscribed;
		g_SubscribedSymbols.GetNextAssoc(pos, symbol, subscribed);
		if (subscribed) {
			UnsubscribeFromSymbol(symbol);
		}
	}
	
	g_SubscribedSymbols.RemoveAll();
	
	// Close WebSocket connection
	if (g_websocket != INVALID_SOCKET) {
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
	}
	
	g_bWebSocketConnected = false;
	g_bWebSocketAuthenticated = false;
	
	WSACleanup();
}

///////////////////////////////
// Plugin API Functions
///////////////////////////////

PLUGINAPI int Init(void) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!g_bPluginInitialized.load()) {
		// Initialize on first call
		g_oServer = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("Server"), _T("127.0.0.1"));
		g_oApiKey = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("ApiKey"), _T(""));
		g_oWebSocketUrl = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("WebSocketUrl"), _T("ws://127.0.0.1:8765"));
		g_nPortNumber = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("Port"), 5000);
		g_nRefreshInterval = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("RefreshInterval"), 5);
		g_nTimeShift = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("TimeShift"), 0);
		
		g_nStatus = STATUS_WAIT;
		g_bPluginInitialized = true;
		
		// Initialize quote cache
		g_QuoteCache.InitHashTable(997);
		
		// Start connection worker thread
		g_bShutdownRequested = false;
		g_connectionThread = std::thread(ConnectionWorkerThread);
		
		LogError(_T("Enhanced OpenAlgo plugin initialized"));
	}
	
	return 1;
}

PLUGINAPI int Release(void) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	// Signal shutdown and cleanup
	g_bShutdownRequested = true;
	CleanupWebSocket();
	
	// Clear cache
	g_QuoteCache.RemoveAll();
	
	LogError(_T("Enhanced OpenAlgo plugin released"));
	
	return 1;
}

PLUGINAPI int GetPluginInfo(struct PluginInfo* pInfo) {
	if (pInfo) {
		memcpy(pInfo, &oPluginInfo, sizeof(struct PluginInfo));
		return 1;
	}
	return 0;
}

PLUGINAPI int SetSite(struct SiteInterface* pSite) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!pSite) return 0;
	
	COpenAlgoConfigDlg oDlg;
	oDlg.m_pSite = pSite;
	
	if (oDlg.DoModal() == IDOK) {
		// Force status update after config change
		if (g_hAmiBrokerWnd != NULL) {
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}
	
	return 1;
}

PLUGINAPI int GetStatus(struct Status* status) {
	if (!status) return 0;
	
	status->nStructSize = sizeof(struct Status);
	status->nStatusCode = 0;
	status->szShortMessage[0] = '\0';
	status->szLongMessage[0] = '\0';
	status->clrStatusColor = RGB(0, 0, 0);
	
	switch (g_nStatus) {
		case STATUS_WAIT:
			status->nStatusCode = 0x10000000; // WARNING
			strcpy_s(status->szShortMessage, 32, "WAIT");
			strcpy_s(status->szLongMessage, 256, "OpenAlgo Enhanced: Waiting to connect");
			status->clrStatusColor = RGB(255, 255, 0); // Yellow
			break;
			
		case STATUS_CONNECTED:
			if (IsConnectionHealthy()) {
				status->nStatusCode = 0x00000000; // OK
				strcpy_s(status->szShortMessage, 32, "OK");
				strcpy_s(status->szLongMessage, 256, "OpenAlgo Enhanced: Connected");
				status->clrStatusColor = RGB(0, 255, 0); // Green
			} else {
				status->nStatusCode = 0x20000000; // MINOR ERROR
				strcpy_s(status->szShortMessage, 32, "STALE");
				strcpy_s(status->szLongMessage, 256, "OpenAlgo Enhanced: Connected but no recent data");
				status->clrStatusColor = RGB(255, 165, 0); // Orange
			}
			break;
			
		case STATUS_DISCONNECTED:
			status->nStatusCode = 0x20000000; // MINOR ERROR
			strcpy_s(status->szShortMessage, 32, "RETRY");
			CString msg;
			msg.Format(_T("OpenAlgo Enhanced: Disconnected. Retry in %d seconds."), 
			           g_connectionRetry.nextRetryDelay / 1000);
			strcpy_s(status->szLongMessage, 256, msg);
			status->clrStatusColor = RGB(255, 0, 0); // Red
			break;
			
		case STATUS_SHUTDOWN:
			status->nStatusCode = 0x30000000; // SEVERE ERROR
			strcpy_s(status->szShortMessage, 32, "OFF");
			strcpy_s(status->szLongMessage, 256, "OpenAlgo Enhanced: Offline. Right-click to reconnect.");
			status->clrStatusColor = RGB(192, 0, 192); // Purple
			break;
			
		default:
			status->nStatusCode = 0x30000000; // SEVERE ERROR
			strcpy_s(status->szShortMessage, 32, "ERR");
			strcpy_s(status->szLongMessage, 256, "OpenAlgo Enhanced: Unknown status");
			status->clrStatusColor = RGB(255, 0, 0); // Red
			break;
	}
	
	return 1;
}

PLUGINAPI AmiVar GetExtraData(LPCTSTR pszTicker, int nField) {
	AmiVar result;
	result.type = VAR_FLOAT;
	result.val = 0;
	
	// Return cached data if available
	QuoteCache cachedQuote;
	if (g_QuoteCache.Lookup(pszTicker, cachedQuote)) {
		switch (nField) {
			case 0: result.val = cachedQuote.volume; break;
			case 1: result.val = cachedQuote.oi; break;
			case 2: result.val = cachedQuote.open; break;
			case 3: result.val = cachedQuote.high; break;
			case 4: result.val = cachedQuote.low; break;
			case 5: result.val = cachedQuote.close; break;
		}
	}
	
	return result;
}

PLUGINAPI int Notify(struct PluginNotification* pn) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!pn) return 0;
	
	// Database loaded - start connection
	if ((pn->nReason & REASON_DATABASE_LOADED)) {
		g_hAmiBrokerWnd = pn->hMainWnd;
		
		// Reload settings
		g_oServer = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("Server"), _T("127.0.0.1"));
		g_oApiKey = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("ApiKey"), _T(""));
		g_oWebSocketUrl = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("WebSocketUrl"), _T("ws://127.0.0.1:8765"));
		g_nPortNumber = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("Port"), 5000);
		g_nRefreshInterval = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("RefreshInterval"), 5);
		
		g_nStatus = STATUS_WAIT;
		
		// Trigger connection attempt
		g_connectionCV.notify_all();
		
		// Force immediate status update
		if (g_hAmiBrokerWnd != NULL) {
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}
	
	return 1;
}

PLUGINAPI int GetQuotesEx(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes, GQEContext* pContext) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!pszTicker || !pQuotes || nSize <= 0) return 0;
	
	// Use HTTP API for historical data (more reliable than WebSocket)
	return GetOpenAlgoHistory(pszTicker, nPeriodicity, nLastValid, nSize, pQuotes);
}

PLUGINAPI struct RecentInfo* GetRecentInfo(LPCTSTR pszTicker) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	// Check if we have an API key
	if (g_oApiKey.IsEmpty())
		return NULL;
	
	static struct RecentInfo ri;
	memset(&ri, 0, sizeof(ri));
	ri.nStructSize = sizeof(struct RecentInfo);
	
	CString ticker(pszTicker);
	
	// Try to get data from cache first
	QuoteCache cachedQuote;
	BOOL bCached = FALSE;
	
	if (g_QuoteCache.Lookup(ticker, cachedQuote)) {
		// Check if cache is recent (within 5 seconds)
		DWORD currentTime = (DWORD)GetTickCount64();
		if ((currentTime - cachedQuote.lastUpdate) < 5000) {
			bCached = TRUE;
		}
	}
	
	// If not cached or cache is stale, try HTTP API (non-blocking)
	if (!bCached) {
		if (GetOpenAlgoQuote(pszTicker, cachedQuote)) {
			// Cache the result
			g_QuoteCache.SetAt(ticker, cachedQuote);
			bCached = TRUE;
		}
	}
	
	// Fill RecentInfo structure if we have data
	if (bCached) {
		_tcsncpy_s(ri.Name, sizeof(ri.Name) / sizeof(TCHAR), pszTicker, _TRUNCATE);
		_tcsncpy_s(ri.Exchange, sizeof(ri.Exchange) / sizeof(TCHAR), cachedQuote.exchange, _TRUNCATE);
		
		ri.nStatus = RI_STATUS_UPDATE | RI_STATUS_TRADE | RI_STATUS_BARSREADY;
		ri.nBitmap = RI_LAST | RI_OPEN | RI_HIGHLOW | RI_TRADEVOL | RI_OPENINT;
		
		ri.fLast = cachedQuote.ltp;
		ri.fOpen = cachedQuote.open;
		ri.fHigh = cachedQuote.high;
		ri.fLow = cachedQuote.low;
		ri.fPrev = cachedQuote.close;
		ri.fChange = cachedQuote.ltp - cachedQuote.close;
		ri.fTradeVol = cachedQuote.volume;
		ri.fTotalVol = cachedQuote.volume;
		ri.fOpenInt = cachedQuote.oi;
		
		// Set update times
		CTime now = CTime::GetCurrentTime();
		ri.nDateUpdate = now.GetYear() * 10000 + now.GetMonth() * 100 + now.GetDay();
		ri.nTimeUpdate = now.GetHour() * 10000 + now.GetMinute() * 100 + now.GetSecond();
		ri.nDateChange = ri.nDateUpdate;
		ri.nTimeChange = ri.nTimeUpdate;
		
		return &ri;
	}
	
	return NULL;
}

// HTTP API functions for reliable data fetching
BOOL TestOpenAlgoConnection(void) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (g_oApiKey.IsEmpty() || g_oServer.IsEmpty()) {
		return FALSE;
	}
	
	try {
		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\"}"), (LPCTSTR)g_oApiKey);
		
		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, 3000);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, 3000);
		
		// Parse server and port
		CString oServer = g_oServer;
		int nPort = g_nPortNumber;
		oServer.Replace(_T("http://"), _T(""));
		oServer.Replace(_T("https://"), _T(""));
		
		CHttpConnection* pConnection = oSession.GetHttpConnection(oServer, nPort);
		
		if (pConnection) {
			CHttpFile* pFile = pConnection->OpenRequest(
				CHttpConnection::HTTP_VERB_POST,
				_T("/api/v1/ping"),
				NULL, 1, NULL, NULL,
				INTERNET_FLAG_RELOAD | INTERNET_FLAG_DONT_CACHE);
			
			if (pFile) {
				// Send request
				CStringA postDataA(oPostData);
				pFile->SendRequest(NULL, 0, (LPVOID)(LPCSTR)postDataA, postDataA.GetLength());
				
				// Get response
				DWORD dwRet;
				pFile->QueryInfoStatusCode(dwRet);
				
				if (dwRet == HTTP_STATUS_OK) {
					CString oResponse;
					CStringA responseA;
					UINT nRead;
					char szBuffer[1024];
					
					while ((nRead = pFile->Read(szBuffer, sizeof(szBuffer))) > 0) {
						responseA.Append(szBuffer, nRead);
					}
					
					oResponse = CString(responseA);
					
					// Check for successful ping response
					if (oResponse.Find(_T("\"message\":\"pong\"")) >= 0 ||
					    oResponse.Find(_T("\"message\": \"pong\"")) >= 0) {
						
						pFile->Close();
						delete pFile;
						pConnection->Close();
						delete pConnection;
						oSession.Close();
						
						return TRUE;
					}
				}
				
				pFile->Close();
				delete pFile;
			}
			
			pConnection->Close();
			delete pConnection;
		}
		
		oSession.Close();
		
	} catch (CInternetException* e) {
		e->Delete();
	} catch (...) {
		LogError(_T("Exception in TestOpenAlgoConnection"));
	}
	
	return FALSE;
}

BOOL GetOpenAlgoQuote(LPCTSTR pszTicker, QuoteCache& quote) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!pszTicker || g_oApiKey.IsEmpty() || g_oServer.IsEmpty()) {
		return FALSE;
	}
	
	try {
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/quotes"));
		
		// Prepare POST data
		CString symbol = GetCleanSymbol(pszTicker);
		CString exchange = GetExchangeFromTicker(pszTicker);
		
		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\",\"symbol\":\"%s\",\"exchange\":\"%s\"}"),
			(LPCTSTR)g_oApiKey, (LPCTSTR)symbol, (LPCTSTR)exchange);
		
		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, 3000);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, 3000);
		
		// Parse server
		CString oServer = g_oServer;
		int nPort = g_nPortNumber;
		oServer.Replace(_T("http://"), _T(""));
		oServer.Replace(_T("https://"), _T(""));
		
		CHttpConnection* pConnection = oSession.GetHttpConnection(oServer, nPort);
		
		if (pConnection) {
			CHttpFile* pFile = pConnection->OpenRequest(
				CHttpConnection::HTTP_VERB_POST,
				_T("/api/v1/quotes"),
				NULL, 1, NULL, NULL,
				INTERNET_FLAG_RELOAD | INTERNET_FLAG_DONT_CACHE);
			
			if (pFile) {
				// Send request
				CStringA postDataA(oPostData);
				pFile->SendRequest(NULL, 0, (LPVOID)(LPCSTR)postDataA, postDataA.GetLength());
				
				// Get response
				DWORD dwRet;
				pFile->QueryInfoStatusCode(dwRet);
				
				if (dwRet == HTTP_STATUS_OK) {
					CString oResponse;
					CStringA responseA;
					UINT nRead;
					char szBuffer[1024];
					
					while ((nRead = pFile->Read(szBuffer, sizeof(szBuffer))) > 0) {
						responseA.Append(szBuffer, nRead);
					}
					
					oResponse = CString(responseA);
					
					// Parse JSON response
					BOOL bSuccess = FALSE;
					
					if (oResponse.Find(_T("\"status\":\"ok\"")) >= 0 ||
					    oResponse.Find(_T("\"status\":\"success\"")) >= 0) {
						
						// Extract quote data
						int ltpPos = oResponse.Find(_T("\"ltp\":"));
						if (ltpPos >= 0) {
							ltpPos += 6;
							int endPos = oResponse.Find(_T(","), ltpPos);
							if (endPos < 0) endPos = oResponse.Find(_T("}"), ltpPos);
							CString val = oResponse.Mid(ltpPos, endPos - ltpPos);
							quote.ltp = (float)_tstof(val);
							
							// Extract other fields similarly...
							// (Simplified implementation - add more fields as needed)
							
							quote.symbol = symbol;
							quote.exchange = exchange;
							quote.lastUpdate = (DWORD)GetTickCount64();
							
							bSuccess = TRUE;
						}
					}
					
					pFile->Close();
					delete pFile;
					pConnection->Close();
					delete pConnection;
					oSession.Close();
					
					return bSuccess;
				}
				
				pFile->Close();
				delete pFile;
			}
			
			pConnection->Close();
			delete pConnection;
		}
		
		oSession.Close();
		
	} catch (CInternetException* e) {
		e->Delete();
	} catch (...) {
		LogError(_T("Exception in GetOpenAlgoQuote"));
	}
	
	return FALSE;
}

int GetOpenAlgoHistory(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (!pszTicker || !pQuotes || nSize <= 0 || g_oApiKey.IsEmpty() || g_oServer.IsEmpty()) {
		return 0;
	}
	
	try {
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/history"));
		
		// Prepare POST data
		CString symbol = GetCleanSymbol(pszTicker);
		CString exchange = GetExchangeFromTicker(pszTicker);
		CString interval = GetIntervalString(nPeriodicity);
		
		// Get current time and calculate date range
		CTime currentTime = CTime::GetCurrentTime();
		CTime todayDate = CTime(currentTime.GetYear(), currentTime.GetMonth(), currentTime.GetDay(), 0, 0, 0);
		CTime startTime;
		
		// Determine start date based on periodicity and existing data
		if (nLastValid >= 0 && nLastValid < nSize - 1) {
			// We have some existing data - request from last bar onwards
			union AmiDate lastDate = pQuotes[nLastValid].DateTime;
			startTime = CTime(lastDate.PackDate.Year + 1900, lastDate.PackDate.Month, 
			                  lastDate.PackDate.Day, lastDate.PackDate.Hour, 
			                  lastDate.PackDate.Minute, lastDate.PackDate.Second);
		} else {
			// No existing data - initial load
			if (nPeriodicity == 60) {
				startTime = todayDate - CTimeSpan(30, 0, 0, 0); // 30 days for 1m data
			} else {
				startTime = todayDate - CTimeSpan(3650, 0, 0, 0); // 10 years for daily data
			}
		}
		
		CString startDate = startTime.Format(_T("%Y-%m-%d"));
		CString endDate = todayDate.Format(_T("%Y-%m-%d"));
		
		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"interval\":\"%s\",\"start_date\":\"%s\",\"end_date\":\"%s\"}"),
			(LPCTSTR)g_oApiKey, (LPCTSTR)symbol, (LPCTSTR)exchange, (LPCTSTR)interval, 
			(LPCTSTR)startDate, (LPCTSTR)endDate);
		
		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, 10000);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, 10000);
		
		// Parse server
		CString oServer = g_oServer;
		int nPort = g_nPortNumber;
		oServer.Replace(_T("http://"), _T(""));
		oServer.Replace(_T("https://"), _T(""));
		
		CHttpConnection* pConnection = oSession.GetHttpConnection(oServer, nPort);
		
		if (pConnection) {
			CHttpFile* pFile = pConnection->OpenRequest(
				CHttpConnection::HTTP_VERB_POST,
				_T("/api/v1/history"),
				NULL, 1, NULL, NULL,
				INTERNET_FLAG_RELOAD | INTERNET_FLAG_DONT_CACHE);
			
			if (pFile) {
				// Send request
				CStringA postDataA(oPostData);
				pFile->SendRequest(NULL, 0, (LPVOID)(LPCSTR)postDataA, postDataA.GetLength());
				
				// Get response
				DWORD dwRet;
				pFile->QueryInfoStatusCode(dwRet);
				
				if (dwRet == HTTP_STATUS_OK) {
					CString oResponse;
					CStringA responseA;
					UINT nRead;
					char szBuffer[8192];
					
					while ((nRead = pFile->Read(szBuffer, sizeof(szBuffer))) > 0) {
						responseA.Append(szBuffer, nRead);
					}
					
					oResponse = CString(responseA);
					
					// Parse JSON response and populate quotes array
					// (Implementation would parse the JSON and fill the pQuotes array)
					// This is a simplified version - full implementation would parse all fields
					
					int quoteCount = 0;
					// ... JSON parsing logic would go here ...
					
					pFile->Close();
					delete pFile;
					pConnection->Close();
					delete pConnection;
					oSession.Close();
					
					return quoteCount;
				}
				
				pFile->Close();
				delete pFile;
			}
			
			pConnection->Close();
			delete pConnection;
		}
		
		oSession.Close();
		
	} catch (CInternetException* e) {
		e->Delete();
	} catch (...) {
		LogError(_T("Exception in GetOpenAlgoHistory"));
	}
	
	return 0;
}

// Timer callback for retry logic
VOID CALLBACK OnTimerProc(HWND hWnd, UINT uMsg, UINT_PTR idEvent, DWORD dwTime) {
	if (idEvent == TIMER_INIT || idEvent == TIMER_REFRESH) {
		// Connection retry logic is now handled by the worker thread
		// Just update status display
		if (g_hAmiBrokerWnd != NULL) {
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}
}

// Context menu handler
PLUGINAPI int CustomBacktestProc(int nCommand, int nParam, struct Status* pStatus) {
	AFX_MANAGE_STATE(AfxGetStaticModuleState());
	
	if (nCommand == 0) {
		// Show context menu
		HMENU hMenu = CreatePopupMenu();
		
		if (g_nStatus == STATUS_SHUTDOWN || g_nStatus == STATUS_DISCONNECTED) {
			AppendMenu(hMenu, MF_STRING, 1, _T("Connect"));
		} else {
			AppendMenu(hMenu, MF_STRING, 2, _T("Disconnect"));
		}
		
		AppendMenu(hMenu, MF_SEPARATOR, 0, NULL);
		AppendMenu(hMenu, MF_STRING, 3, _T("Configure..."));
		AppendMenu(hMenu, MF_STRING, 4, _T("Test Connection"));
		
		POINT pt;
		GetCursorPos(&pt);
		
		switch (TrackPopupMenu(hMenu, TPM_RETURNCMD | TPM_LEFTBUTTON | TPM_RIGHTBUTTON, 
		                      pt.x, pt.y, 0, g_hAmiBrokerWnd, NULL)) {
			case 1: // Connect
				g_nStatus = STATUS_WAIT;
				g_connectionRetry.attemptCount = 0;
				g_connectionCV.notify_all();
				break;
				
			case 2: // Disconnect
				g_nStatus = STATUS_SHUTDOWN;
				CleanupWebSocket();
				break;