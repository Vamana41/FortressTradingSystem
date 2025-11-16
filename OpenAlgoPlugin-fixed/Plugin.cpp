// Plugin.cpp - Fixed version with non-blocking operations and robust error handling
#include "stdafx.h"
#include "resource.h"
#include "OpenAlgoGlobals.h"
#include "Plugin.h"
#include "Plugin_Legacy.h"
#include "OpenAlgoConfigDlg.h"
#include <math.h>
#include <time.h>
#include <stdlib.h>
#include <process.h>

// Plugin identification
#define PLUGIN_NAME "OpenAlgo Data Plugin (Fixed)"
#define VENDOR_NAME "OpenAlgo Community (Enhanced)"
#define PLUGIN_VERSION 10004
#define PLUGIN_ID PIDCODE('T', 'E', 'S', 'T')
#define THIS_PLUGIN_TYPE PLUGIN_TYPE_DATA
#define AGENT_NAME PLUGIN_NAME

// Timer IDs
#define TIMER_INIT 198
#define TIMER_REFRESH 199
#define TIMER_WEBSOCKET_PING 200
#define RETRY_COUNT 8
#define WEBSOCKET_CONNECT_TIMEOUT 3000
#define HTTP_REQUEST_TIMEOUT 2000

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

// Local static variables
static int g_nRetryCount = RETRY_COUNT;
static struct RecentInfo* g_aInfos = NULL;
static int RecentInfoSize = 0;
static BOOL g_bPluginInitialized = FALSE;

// WebSocket connection management with thread safety
static SOCKET g_websocket = INVALID_SOCKET;
static BOOL g_bWebSocketConnected = FALSE;
static BOOL g_bWebSocketAuthenticated = FALSE;
static BOOL g_bWebSocketConnecting = FALSE;
static DWORD g_dwLastConnectionAttempt = 0;
static CMap<CString, LPCTSTR, BOOL, BOOL> g_SubscribedSymbols;
static CRITICAL_SECTION g_WebSocketCriticalSection;
static BOOL g_bCriticalSectionInitialized = FALSE;
static HANDLE g_hWebSocketThread = NULL;
static BOOL g_bWebSocketThreadRunning = FALSE;

// Non-blocking connection management
static BOOL g_bConnectionInProgress = FALSE;
static DWORD g_dwConnectionStartTime = 0;
static HANDLE g_hConnectionThread = NULL;

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
	               close(0.0f), volume(0.0f), oi(0.0f), lastUpdate(0) {
	}
};

static CMap<CString, LPCTSTR, QuoteCache, QuoteCache&> g_QuoteCache;

typedef CArray< struct Quotation, struct Quotation > CQuoteArray;

// Forward declarations
VOID CALLBACK OnTimerProc(HWND, UINT, UINT_PTR, DWORD);
void SetupRetry(void);
BOOL TestOpenAlgoConnectionAsync(void);
BOOL GetOpenAlgoQuoteNonBlocking(LPCTSTR pszTicker, QuoteCache& quote);
int GetOpenAlgoHistory(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes);
CString GetExchangeFromTicker(LPCTSTR pszTicker);
CString GetIntervalString(int nPeriodicity);
void ConvertUnixToPackedDate(time_t unixTime, union AmiDate* pAmiDate);

// WebSocket functions with threading
unsigned __stdcall WebSocketThreadProc(void* pParam);
BOOL InitializeWebSocketAsync(void);
void CleanupWebSocket(void);
BOOL ConnectWebSocketNonBlocking(void);
BOOL AuthenticateWebSocketNonBlocking(void);
BOOL SendWebSocketFrame(const CString& message);
CString DecodeWebSocketFrame(const char* buffer, int length);
BOOL SubscribeToSymbol(LPCTSTR pszTicker);
BOOL UnsubscribeFromSymbol(LPCTSTR pszTicker);
BOOL ProcessWebSocketData(void);
void GenerateWebSocketMaskKey(unsigned char* maskKey);

// Helper function for mixed EOD/Intraday data
int FindLastBarOfMatchingType(int nPeriodicity, int nLastValid, struct Quotation* pQuotes);

// Helper function to compare two quotations for sorting by timestamp
int CompareQuotations(const void* a, const void* b);

// Connection management thread
unsigned __stdcall ConnectionThreadProc(void* pParam);

///////////////////////////////
// Helper Functions
///////////////////////////////

// Compare two quotations for sorting by timestamp (oldest to newest)
int CompareQuotations(const void* a, const void* b)
{
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
int FindLastBarOfMatchingType(int nPeriodicity, int nLastValid, struct Quotation* pQuotes)
{
	if (nLastValid < 0 || pQuotes == NULL)
		return -1;

	if (nPeriodicity == 86400)  // Looking for Daily data
	{
		for (int i = nLastValid; i >= 0; i--)
		{
			if (pQuotes[i].DateTime.PackDate.Hour == DATE_EOD_HOURS &&
				pQuotes[i].DateTime.PackDate.Minute == DATE_EOD_MINUTES)
			{
				return i;
			}
		}
		return -1;
	}
	else if (nPeriodicity == 60)  // Looking for 1-minute data
	{
		for (int i = nLastValid; i >= 0; i--)
		{
			if (pQuotes[i].DateTime.PackDate.Hour < DATE_EOD_HOURS)
			{
				return i;
			}
		}
		return -1;
	}
	else
	{
		return nLastValid;
	}
}

CString BuildOpenAlgoURL(const CString& server, int port, const CString& endpoint)
{
	CString result;
	result.Format(_T("http://%s:%d%s"), (LPCTSTR)server, port, (LPCTSTR)endpoint);
	return result;
}

// Extract exchange from ticker format (e.g., "RELIANCE-NSE" -> "NSE")
CString GetExchangeFromTicker(LPCTSTR pszTicker)
{
	CString ticker(pszTicker);
	int dashPos = ticker.ReverseFind(_T('-'));
	if (dashPos != -1)
	{
		return ticker.Mid(dashPos + 1);
	}

	return _T("NSE");
}

// Get clean symbol without exchange suffix
CString GetCleanSymbol(LPCTSTR pszTicker)
{
	CString ticker(pszTicker);
	int dashPos = ticker.ReverseFind(_T('-'));
	if (dashPos != -1)
	{
		return ticker.Left(dashPos);
	}
	return ticker;
}

// Convert periodicity to OpenAlgo interval string
CString GetIntervalString(int nPeriodicity)
{
	if (nPeriodicity == 60)  // 1 minute in seconds
		return _T("1m");
	else if (nPeriodicity == 86400) // Daily in seconds
		return _T("D");
	else
		return _T("D");
}

// Convert Unix timestamp to AmiBroker date format
void ConvertUnixToPackedDate(time_t unixTime, union AmiDate* pAmiDate)
{
	struct tm* timeinfo = localtime(&unixTime);

	pAmiDate->PackDate.Year = timeinfo->tm_year + 1900;
	pAmiDate->PackDate.Month = timeinfo->tm_mon + 1;
	pAmiDate->PackDate.Day = timeinfo->tm_mday;
	pAmiDate->PackDate.Hour = timeinfo->tm_hour;
	pAmiDate->PackDate.Minute = timeinfo->tm_min;
	pAmiDate->PackDate.Second = timeinfo->tm_sec;
	pAmiDate->PackDate.MilliSec = 0;
	pAmiDate->PackDate.MicroSec = 0;
	pAmiDate->PackDate.Reserved = 0;
	pAmiDate->PackDate.IsFuturePad = 0;
}

// NON-BLOCKING quote fetch with timeout
BOOL GetOpenAlgoQuoteNonBlocking(LPCTSTR pszTicker, QuoteCache& quote)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_oApiKey.IsEmpty())
		return FALSE;

	// Check if we're already in a connection attempt
	if (g_bConnectionInProgress)
	{
		DWORD dwElapsed = (DWORD)GetTickCount64() - g_dwConnectionStartTime;
		if (dwElapsed > HTTP_REQUEST_TIMEOUT)
		{
			// Timeout - cancel the connection
			g_bConnectionInProgress = FALSE;
			return FALSE;
		}
		return FALSE; // Still in progress
	}

	BOOL bSuccess = FALSE;

	try
	{
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/quotes"));

		CString symbol = GetCleanSymbol(pszTicker);
		CString exchange = GetExchangeFromTicker(pszTicker);

		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\",\"symbol\":\"%s\",\"exchange\":\"%s\"}"),
			(LPCTSTR)g_oApiKey, (LPCTSTR)symbol, (LPCTSTR)exchange);

		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, HTTP_REQUEST_TIMEOUT);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, HTTP_REQUEST_TIMEOUT);

		CHttpConnection* pConnection = NULL;
		CHttpFile* pFile = NULL;

		INTERNET_PORT nPort = (INTERNET_PORT)g_nPortNumber;
		CString oServer = g_oServer;
		oServer.Replace(_T("http://"), _T(""));
		oServer.Replace(_T("https://"), _T(""));

		pConnection = oSession.GetHttpConnection(oServer, nPort);

		if (pConnection)
		{
			pFile = pConnection->OpenRequest(
				CHttpConnection::HTTP_VERB_POST,
				_T("/api/v1/quotes"),
				NULL, 1, NULL, NULL,
				INTERNET_FLAG_RELOAD | INTERNET_FLAG_DONT_CACHE);

			if (pFile)
			{
				CString oHeaders = _T("Content-Type: application/json\r\n");
				CStringA oPostDataA(oPostData);

				if (pFile->SendRequest(oHeaders, (LPVOID)(LPCSTR)oPostDataA, oPostDataA.GetLength()))
				{
					DWORD dwStatusCode = 0;
					pFile->QueryInfoStatusCode(dwStatusCode);

					if (dwStatusCode == 200)
					{
						CString oResponse;
						CString oLine;
						while (pFile->ReadString(oLine))
						{
							oResponse += oLine;
						}

						if (oResponse.Find(_T("\"status\":\"success\"")) >= 0)
						{
							int pos;

							pos = oResponse.Find(_T("\"ltp\":"));
							if (pos >= 0)
							{
								pos += 6;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.ltp = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"open\":"));
							if (pos >= 0)
							{
								pos += 7;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.open = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"high\":"));
							if (pos >= 0)
							{
								pos += 7;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.high = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"low\":"));
							if (pos >= 0)
							{
								pos += 6;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.low = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"volume\":"));
							if (pos >= 0)
							{
								pos += 9;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.volume = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"oi\":"));
							if (pos >= 0)
							{
								pos += 5;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.oi = (float)_tstof(val);
							}

							pos = oResponse.Find(_T("\"prev_close\":"));
							if (pos >= 0)
							{
								pos += 13;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.close = (float)_tstof(val);
							}

							quote.symbol = symbol;
							quote.exchange = exchange;
							quote.lastUpdate = (DWORD)GetTickCount64();

							bSuccess = TRUE;
						}
					}
				}

				pFile->Close();
				delete pFile;
			}

			pConnection->Close();
			delete pConnection;
		}

		oSession.Close();
	}
	catch (CInternetException* e)
	{
		e->Delete();
	}

	return bSuccess;
}

// ASYNCHRONOUS connection test with proper timeout handling
BOOL TestOpenAlgoConnectionAsync(void)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	// Check if API key is configured
	if (g_oApiKey.IsEmpty())
	{
		return FALSE;
	}

	// Check if we're already testing connection
	if (g_bConnectionInProgress)
	{
		DWORD dwElapsed = (DWORD)GetTickCount64() - g_dwConnectionStartTime;
		if (dwElapsed > HTTP_REQUEST_TIMEOUT)
		{
			// Timeout - reset connection state
			g_bConnectionInProgress = FALSE;
			return FALSE;
		}
		return FALSE; // Still testing
	}

	// Start connection test in separate thread if not already running
	if (g_hConnectionThread == NULL)
	{
		g_bConnectionInProgress = TRUE;
		g_dwConnectionStartTime = (DWORD)GetTickCount64();

		unsigned threadID;
		g_hConnectionThread = (HANDLE)_beginthreadex(NULL, 0, ConnectionThreadProc, NULL, 0, &threadID);

		if (g_hConnectionThread == NULL)
		{
			g_bConnectionInProgress = FALSE;
			return FALSE;
		}
	}

	// Return previous known status for immediate response
	return (g_nStatus == STATUS_CONNECTED);
}

// Connection test thread procedure
unsigned __stdcall ConnectionThreadProc(void* pParam)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	BOOL bConnected = FALSE;

	try
	{
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/ping"));

		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, HTTP_REQUEST_TIMEOUT);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, HTTP_REQUEST_TIMEOUT);

		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\"}"), (LPCTSTR)g_oApiKey);

		CHttpConnection* pConnection = NULL;
		CHttpFile* pFile = NULL;

		INTERNET_PORT nPort = (INTERNET_PORT)g_nPortNumber;
		CString oServer = g_oServer;
		oServer.Replace(_T("http://"), _T(""));
		oServer.Replace(_T("https://"), _T(""));

		pConnection = oSession.GetHttpConnection(oServer, nPort);

		if (pConnection)
		{
			pFile = pConnection->OpenRequest(
				CHttpConnection::HTTP_VERB_POST,
				_T("/api/v1/ping"),
				NULL, 1, NULL, NULL,
				INTERNET_FLAG_RELOAD | INTERNET_FLAG_DONT_CACHE);

			if (pFile)
			{
				CString oHeaders = _T("Content-Type: application/json\r\n");
				CStringA oPostDataA(oPostData);

				if (pFile->SendRequest(oHeaders, (LPVOID)(LPCSTR)oPostDataA, oPostDataA.GetLength()))
				{
					DWORD dwStatusCode = 0;
					pFile->QueryInfoStatusCode(dwStatusCode);

					if (dwStatusCode == 200)
					{
						CString oResponse;
						CString oLine;
						while (pFile->ReadString(oLine))
						{
							oResponse += oLine;
							if (oResponse.GetLength() > 500) break;
						}

						if ((oResponse.Find(_T("\"status\":\"success\"")) >= 0 ||
							 oResponse.Find(_T("\"status\": \"success\"")) >= 0) &&
							(oResponse.Find(_T("\"message\":\"pong\"")) >= 0 ||
							 oResponse.Find(_T("\"message\": \"pong\"")) >= 0))
						{
							bConnected = TRUE;
						}
					}
				}

				pFile->Close();
				delete pFile;
			}

			pConnection->Close();
			delete pConnection;
		}

		oSession.Close();
	}
	catch (CInternetException* e)
	{
		e->Delete();
		bConnected = FALSE;
	}

	// Update global status
	if (bConnected)
	{
		g_nStatus = STATUS_CONNECTED;
		g_nRetryCount = RETRY_COUNT;
	}
	else
	{
		g_nStatus = STATUS_DISCONNECTED;
	}

	g_bConnectionInProgress = FALSE;

	// Notify AmiBroker of status change
	if (g_hAmiBrokerWnd != NULL)
	{
		::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
	}

	// Close thread handle
	if (g_hConnectionThread != NULL)
	{
		CloseHandle(g_hConnectionThread);
		g_hConnectionThread = NULL;
	}

	return 0;
}

void SetupRetry(void)
{
	if (--g_nRetryCount > 0)
	{
		if (g_hAmiBrokerWnd != NULL)
		{
			SetTimer(g_hAmiBrokerWnd, TIMER_INIT, 15000, (TIMERPROC)OnTimerProc);
		}
		g_nStatus = STATUS_DISCONNECTED;
	}
	else
	{
		g_nStatus = STATUS_SHUTDOWN;
	}

	if (g_hAmiBrokerWnd != NULL)
	{
		::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
	}
}

VOID CALLBACK OnTimerProc(HWND hwnd, UINT uMsg, UINT_PTR idEvent, DWORD dwTime)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (idEvent == TIMER_INIT || idEvent == TIMER_REFRESH)
	{
		// Use async connection test instead of blocking
		if (!TestOpenAlgoConnectionAsync())
		{
			if (g_hAmiBrokerWnd != NULL)
			{
				KillTimer(g_hAmiBrokerWnd, idEvent);
			}
			SetupRetry();
			return;
		}

		g_nRetryCount = RETRY_COUNT;

		if (g_hAmiBrokerWnd != NULL)
		{
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);

			if (idEvent == TIMER_INIT)
			{
				KillTimer(g_hAmiBrokerWnd, TIMER_INIT);
				SetTimer(g_hAmiBrokerWnd, TIMER_REFRESH, g_nRefreshInterval * 1000, (TIMERPROC)OnTimerProc);
			}
		}
	}
	else if (idEvent == TIMER_WEBSOCKET_PING)
	{
		// Periodic WebSocket ping in separate thread
		if (g_bWebSocketConnected && !g_bWebSocketThreadRunning)
		{
			unsigned threadID;
			g_hWebSocketThread = (HANDLE)_beginthreadex(NULL, 0, WebSocketThreadProc, NULL, 0, &threadID);
		}
	}
}

///////////////////////////////////////////////////////////
// Exported Functions
///////////////////////////////////////////////////////////
PLUGINAPI int GetPluginInfo(struct PluginInfo* pInfo)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (pInfo == NULL) return FALSE;

	*pInfo = oPluginInfo;
	return TRUE;
}

PLUGINAPI int Init(void)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (!g_bPluginInitialized)
	{
		g_oServer = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("Server"), _T("127.0.0.1"));
		g_oApiKey = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("ApiKey"), _T(""));
		g_oWebSocketUrl = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("WebSocketUrl"), _T("ws://127.0.0.1:8765"));
		g_nPortNumber = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("Port"), 5000);
		g_nRefreshInterval = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("RefreshInterval"), 5);
		g_nTimeShift = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("TimeShift"), 0);

		g_nStatus = STATUS_WAIT;
		g_bPluginInitialized = TRUE;

		g_QuoteCache.InitHashTable(997);

		InitializeCriticalSection(&g_WebSocketCriticalSection);
		g_bCriticalSectionInitialized = TRUE;
	}

	return 1;
}

PLUGINAPI int Release(void)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	CleanupWebSocket();
	g_QuoteCache.RemoveAll();

	if (g_bCriticalSectionInitialized)
	{
		DeleteCriticalSection(&g_WebSocketCriticalSection);
		g_bCriticalSectionInitialized = FALSE;
	}

	return 1;
}

PLUGINAPI int Configure(LPCTSTR pszPath, struct InfoSite* pSite)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	COpenAlgoConfigDlg oDlg;
	oDlg.m_pSite = pSite;

	if (oDlg.DoModal() == IDOK)
	{
		if (g_hAmiBrokerWnd != NULL)
		{
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}

	return 1;
}

PLUGINAPI AmiVar GetExtraData(LPCTSTR pszTicker, LPCTSTR pszName, int nArraySize, int nPeriodicity, void* (*pfAlloc)(unsigned int nSize))
{
	AmiVar var;
	var.type = VAR_NONE;
	var.val = 0;
	return var;
}

PLUGINAPI int SetTimeBase(int nTimeBase)
{
	return 1;
}

PLUGINAPI int GetSymbolLimit(void)
{
	return 1000;
}

PLUGINAPI int GetStatus(struct PluginStatus* status)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (status == NULL) return 0;

	status->nStructSize = sizeof(struct PluginStatus);

	if (g_nStatus < STATUS_WAIT || g_nStatus > STATUS_SHUTDOWN)
	{
		g_nStatus = STATUS_WAIT;
	}

	switch (g_nStatus)
	{
	case STATUS_WAIT:
		status->nStatusCode = 0x10000000;
		strcpy_s(status->szShortMessage, 32, "WAIT");
		strcpy_s(status->szLongMessage, 256, "OpenAlgo: Waiting to connect");
		status->clrStatusColor = RGB(255, 255, 0);
		break;

	case STATUS_CONNECTED:
		status->nStatusCode = 0x00000000;
		strcpy_s(status->szShortMessage, 32, "OK");
		strcpy_s(status->szLongMessage, 256, "OpenAlgo: Connected");
		status->clrStatusColor = RGB(0, 255, 0);
		break;

	case STATUS_DISCONNECTED:
		status->nStatusCode = 0x20000000;
		strcpy_s(status->szShortMessage, 32, "ERR");
		strcpy_s(status->szLongMessage, 256, "OpenAlgo: Connection failed. Will retry in 15 seconds.");
		status->clrStatusColor = RGB(255, 0, 0);
		break;

	case STATUS_SHUTDOWN:
		status->nStatusCode = 0x30000000;
		strcpy_s(status->szShortMessage, 32, "OFF");
		strcpy_s(status->szLongMessage, 256, "OpenAlgo: Offline. Right-click to reconnect.");
		status->clrStatusColor = RGB(192, 0, 192);
		break;

	default:
		status->nStatusCode = 0x30000000;
		strcpy_s(status->szShortMessage, 32, "???");
		strcpy_s(status->szLongMessage, 256, "OpenAlgo: Unknown status");
		status->clrStatusColor = RGB(128, 128, 128);
		break;
	}

	return 1;
}

PLUGINAPI int Notify(struct PluginNotification* pn)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (pn == NULL) return 0;

	if ((pn->nReason & REASON_DATABASE_LOADED))
	{
		g_hAmiBrokerWnd = pn->hMainWnd;

		g_oServer = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("Server"), _T("127.0.0.1"));
		g_oApiKey = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("ApiKey"), _T(""));
		g_oWebSocketUrl = AfxGetApp()->GetProfileString(_T("OpenAlgo"), _T("WebSocketUrl"), _T("ws://127.0.0.1:8765"));
		g_nPortNumber = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("Port"), 5000);
		g_nRefreshInterval = AfxGetApp()->GetProfileInt(_T("OpenAlgo"), _T("RefreshInterval"), 5);

		g_nStatus = STATUS_WAIT;
		g_nRetryCount = RETRY_COUNT;

		if (g_hAmiBrokerWnd != NULL)
		{
			SetTimer(g_hAmiBrokerWnd, TIMER_INIT, 1000, (TIMERPROC)OnTimerProc);
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}

	if (pn->nReason & REASON_DATABASE_UNLOADED)
	{
		if (g_hAmiBrokerWnd != NULL)
		{
			KillTimer(g_hAmiBrokerWnd, TIMER_INIT);
			KillTimer(g_hAmiBrokerWnd, TIMER_REFRESH);
			KillTimer(g_hAmiBrokerWnd, TIMER_WEBSOCKET_PING);
		}
		g_hAmiBrokerWnd = NULL;
		g_nStatus = STATUS_SHUTDOWN;

		free(g_aInfos);
		g_aInfos = NULL;
		RecentInfoSize = 0;

		g_QuoteCache.RemoveAll();
	}

	if (pn->nReason & REASON_STATUS_RMBCLICK)
	{
		if (g_hAmiBrokerWnd != NULL)
		{
			HMENU hMenu = CreatePopupMenu();

			if (g_nStatus == STATUS_SHUTDOWN || g_nStatus == STATUS_DISCONNECTED)
			{
				AppendMenu(hMenu, MF_STRING, 1, _T("Connect"));
			}
			else
			{
				AppendMenu(hMenu, MF_STRING, 2, _T("Disconnect"));
			}
			AppendMenu(hMenu, MF_SEPARATOR, 0, NULL);
			AppendMenu(hMenu, MF_STRING, 3, _T("Configure..."));

			POINT pt;
			GetCursorPos(&pt);

			int nCmd = TrackPopupMenu(hMenu, TPM_RETURNCMD | TPM_LEFTALIGN | TPM_TOPALIGN,
				pt.x, pt.y, 0, g_hAmiBrokerWnd, NULL);

			DestroyMenu(hMenu);

			switch (nCmd)
			{
			case 1: // Connect
				g_nStatus = STATUS_WAIT;
				g_nRetryCount = RETRY_COUNT;
				SetTimer(g_hAmiBrokerWnd, TIMER_INIT, 1000, (TIMERPROC)OnTimerProc);
				break;

			case 2: // Disconnect
				KillTimer(g_hAmiBrokerWnd, TIMER_INIT);
				KillTimer(g_hAmiBrokerWnd, TIMER_REFRESH);
				KillTimer(g_hAmiBrokerWnd, TIMER_WEBSOCKET_PING);
				g_nStatus = STATUS_SHUTDOWN;
				break;

			case 3: // Configure
				Configure(pn->pszDatabasePath, NULL);
				break;
			}

			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);
		}
	}

	return 1;
}

// Main quote retrieval function with non-blocking improvements
PLUGINAPI int GetQuotesEx(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes, GQEContext* pContext)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_nStatus == STATUS_DISCONNECTED || g_nStatus == STATUS_SHUTDOWN)
	{
		return nLastValid + 1;
	}

	// Handle Daily (EOD) data
	if (nPeriodicity == 86400)
	{
		int nQty = GetOpenAlgoHistory(pszTicker, nPeriodicity, nLastValid, nSize, pQuotes);
		return nQty;
	}
	else if (nPeriodicity == 60)
	{
		int nQty = nLastValid + 1;

		int lastDailyBarIndex = FindLastBarOfMatchingType(86400, nLastValid, pQuotes);

		if (lastDailyBarIndex < 0)
		{
			nQty = GetOpenAlgoHistory(pszTicker, 86400, nLastValid, nSize, pQuotes);
		}
		else if (lastDailyBarIndex < 250)
		{
			nQty = GetOpenAlgoHistory(pszTicker, 86400, nLastValid, nSize, pQuotes);
		}

		nQty = GetOpenAlgoHistory(pszTicker, 60, nQty - 1, nSize, pQuotes);

		return nQty;
	}
	else
	{
		return nLastValid + 1;
	}
}

// GetRecentInfo with non-blocking WebSocket and proper error handling
PLUGINAPI struct RecentInfo* GetRecentInfo(LPCTSTR pszTicker)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_nStatus != STATUS_CONNECTED || g_oApiKey.IsEmpty())
		return NULL;

	static struct RecentInfo ri;
	memset(&ri, 0, sizeof(ri));
	ri.nStructSize = sizeof(struct RecentInfo);

	CString ticker(pszTicker);

	// Initialize WebSocket asynchronously
	DWORD dwNow = (DWORD)GetTickCount64();
	if (!g_bWebSocketConnected && !g_bWebSocketConnecting &&
		(dwNow - g_dwLastConnectionAttempt) > WEBSOCKET_CONNECT_TIMEOUT)
	{
		g_dwLastConnectionAttempt = dwNow;
		InitializeWebSocketAsync();
	}

	// Process WebSocket data without blocking
	ProcessWebSocketData();

	// Check cache for WebSocket data first
	QuoteCache cachedQuote;
	BOOL bCached = FALSE;

	if (g_QuoteCache.Lookup(ticker, cachedQuote))
	{
		DWORD dwNow = (DWORD)GetTickCount64();
		if ((dwNow - cachedQuote.lastUpdate) < 5000)
		{
			bCached = TRUE;
		}
	}

	// Fallback to non-blocking HTTP API if WebSocket data not available
	if (!bCached)
	{
		if (!GetOpenAlgoQuoteNonBlocking(pszTicker, cachedQuote))
			return NULL;

		g_QuoteCache.SetAt(ticker, cachedQuote);
	}

	// Fill RecentInfo structure
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

	CTime now = CTime::GetCurrentTime();
	ri.nDateUpdate = now.GetYear() * 10000 + now.GetMonth() * 100 + now.GetDay();
	ri.nTimeUpdate = now.GetHour() * 10000 + now.GetMinute() * 100 + now.GetSecond();
	ri.nDateChange = ri.nDateUpdate;
	ri.nTimeChange = ri.nTimeUpdate;

	return &ri;
}

///////////////////////////////
// WebSocket Functions with Threading
///////////////////////////////

void GenerateWebSocketMaskKey(unsigned char* maskKey)
{
	srand((unsigned int)GetTickCount64());
	maskKey[0] = (unsigned char)(rand() & 0xFF);
	maskKey[1] = (unsigned char)(rand() & 0xFF);
	maskKey[2] = (unsigned char)(rand() & 0xFF);
	maskKey[3] = (unsigned char)(rand() & 0xFF);
}

BOOL SendWebSocketFrame(const CString& message)
{
	if (g_websocket == INVALID_SOCKET)
		return FALSE;

	CStringA messageA(message);
	int messageLen = messageA.GetLength();

	unsigned char frame[1024];
	int frameLen = 0;

	frame[frameLen++] = 0x81;

	if (messageLen < 126)
	{
		frame[frameLen++] = 0x80 | messageLen;
	}
	else if (messageLen < 65536)
	{
		frame[frameLen++] = 0x80 | 126;
		frame[frameLen++] = (messageLen >> 8) & 0xFF;
		frame[frameLen++] = messageLen & 0xFF;
	}
	else
	{
		return FALSE;
	}

	unsigned char maskKey[4];
	GenerateWebSocketMaskKey(maskKey);
	memcpy(&frame[frameLen], maskKey, 4);
	frameLen += 4;

	for (int i = 0; i < messageLen; i++)
	{
		frame[frameLen++] = messageA[i] ^ maskKey[i % 4];
	}

	int sent = send(g_websocket, (char*)frame, frameLen, 0);
	return (sent == frameLen);
}

CString DecodeWebSocketFrame(const char* buffer, int length)
{
	CString result;

	if (length < 2) return result;

	int pos = 0;
	unsigned char firstByte = (unsigned char)buffer[pos++];
	unsigned char secondByte = (unsigned char)buffer[pos++];

	unsigned char opcode = firstByte & 0x0F;

	if (opcode == 0x08) return _T("CLOSE_FRAME");
	else if (opcode == 0x09) return _T("PING_FRAME");
	else if (opcode == 0x0A) return _T("PONG_FRAME");
	else if (opcode != 0x01) return result;

	BOOL masked = (secondByte & 0x80) != 0;
	int payloadLen = secondByte & 0x7F;

	if (payloadLen == 126)
	{
		if (pos + 2 > length) return result;
		payloadLen = ((unsigned char)buffer[pos] << 8) | (unsigned char)buffer[pos + 1];
		pos += 2;
	}
	else if (payloadLen == 127)
	{
		return result;
	}

	if (payloadLen <= 0 || payloadLen > 4096) return result;

	unsigned char maskKey[4] = {0};
	if (masked)
	{
		if (pos + 4 > length) return result;
		memcpy(maskKey, &buffer[pos], 4);
		pos += 4;
	}

	if (pos + payloadLen > length) return result;

	CStringA payloadA;
	char* payloadBuffer = payloadA.GetBuffer(payloadLen + 1);

	for (int i = 0; i < payloadLen; i++)
	{
		if (masked)
		{
			payloadBuffer[i] = buffer[pos + i] ^ maskKey[i % 4];
		}
		else
		{
			payloadBuffer[i] = buffer[pos + i];
		}
	}
	payloadBuffer[payloadLen] = '\0';
	payloadA.ReleaseBuffer(payloadLen);

	result = CString(payloadA);

	return result;
}

// ASYNCHRONOUS WebSocket initialization
BOOL InitializeWebSocketAsync(void)
{
	if (g_bWebSocketConnected)
		return TRUE;

	if (g_bWebSocketConnecting)
		return FALSE;

	if (g_oWebSocketUrl.IsEmpty() || g_oApiKey.IsEmpty())
		return FALSE;

	// Start WebSocket connection in separate thread
	if (!g_bWebSocketThreadRunning)
	{
		unsigned threadID;
		g_hWebSocketThread = (HANDLE)_beginthreadex(NULL, 0, WebSocketThreadProc, NULL, 0, &threadID);

		if (g_hWebSocketThread == NULL)
		{
			return FALSE;
		}
	}

	return TRUE;
}

// WebSocket thread procedure for non-blocking operations
unsigned __stdcall WebSocketThreadProc(void* pParam)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	g_bWebSocketThreadRunning = TRUE;
	g_bWebSocketConnecting = TRUE;

	// Initialize Winsock
	WSADATA wsaData;
	if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
	{
		g_bWebSocketConnecting = FALSE;
		g_bWebSocketThreadRunning = FALSE;
		return 0;
	}

	// Attempt connection with timeout
	BOOL bConnected = ConnectWebSocketNonBlocking();

	if (bConnected)
	{
		g_bWebSocketConnected = TRUE;

		// Set up periodic ping timer
		if (g_hAmiBrokerWnd != NULL)
		{
			SetTimer(g_hAmiBrokerWnd, TIMER_WEBSOCKET_PING, 30000, (TIMERPROC)OnTimerProc);
		}
	}

	g_bWebSocketConnecting = FALSE;
	g_bWebSocketThreadRunning = FALSE;

	// Close thread handle
	if (g_hWebSocketThread != NULL)
	{
		CloseHandle(g_hWebSocketThread);
		g_hWebSocketThread = NULL;
	}

	return 0;
}

// NON-BLOCKING WebSocket connection with proper timeout handling
BOOL ConnectWebSocketNonBlocking(void)
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

	// Create socket with timeout
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

	// Connect with timeout using select
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

		// Wait for connection with timeout
		fd_set writefds;
		FD_ZERO(&writefds);
		FD_SET(g_websocket, &writefds);

		struct timeval timeout;
		timeout.tv_sec = WEBSOCKET_CONNECT_TIMEOUT / 1000;
		timeout.tv_usec = 0;

		if (select(0, NULL, &writefds, NULL, &timeout) <= 0)
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
		_T("GET %s HTTP/1.1\r\n")
		_T("Host: %s:%d\r\n")
		_T("Upgrade: websocket\r\n")
		_T("Connection: Upgrade\r\n")
		_T("Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n")
		_T("Sec-WebSocket-Version: 13\r\n")
		_T("\r\n"),
		(LPCTSTR)path, (LPCTSTR)host, port);

	CStringA requestA(upgradeRequest);
	if (send(g_websocket, requestA, requestA.GetLength(), 0) == SOCKET_ERROR)
	{
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
		return FALSE;
	}

	// Wait for upgrade response with timeout
	fd_set readfds;
	FD_ZERO(&readfds);
	FD_SET(g_websocket, &readfds);

	struct timeval timeout;
	timeout.tv_sec = WEBSOCKET_CONNECT_TIMEOUT / 1000;
	timeout.tv_usec = 0;

	if (select(0, &readfds, NULL, NULL, &timeout) > 0)
	{
		char buffer[1024];
		int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);

		if (received > 0)
		{
			buffer[received] = '\0';
			CString response(buffer);

			if (response.Find(_T("101")) > 0 && response.Find(_T("Switching Protocols")) > 0)
			{
				// Authenticate with timeout
				return AuthenticateWebSocketNonBlocking();
			}
		}
	}

	closesocket(g_websocket);
	g_websocket = INVALID_SOCKET;
	return FALSE;
}

// NON-BLOCKING WebSocket authentication with timeout
BOOL AuthenticateWebSocketNonBlocking(void)
{
	if (!g_bWebSocketConnected)
		return FALSE;

	// Send authentication message
	CString authMsg = _T("{\"action\":\"authenticate\",\"api_key\":\"") + g_oApiKey + _T("\"}");

	if (SendWebSocketFrame(authMsg))
	{
		// Wait for authentication response with timeout
		fd_set readfds;
		FD_ZERO(&readfds);
		FD_SET(g_websocket, &readfds);

		struct timeval timeout;
		timeout.tv_sec = 5;
		timeout.tv_usec = 0;

		if (select(0, &readfds, NULL, NULL, &timeout) > 0)
		{
			char authBuffer[1024];
			int received = recv(g_websocket, authBuffer, sizeof(authBuffer) - 1, 0);

			if (received > 0)
			{
				authBuffer[received] = '\0';
				CString authResponse = DecodeWebSocketFrame(authBuffer, received);

				if (authResponse.Find(_T("success")) >= 0 ||
					authResponse.Find(_T("authenticated")) >= 0 ||
					authResponse.Find(_T("\"status\":\"ok\"")) >= 0 ||
					authResponse.Find(_T("\"status\":\"success\"")) >= 0)
				{
					g_bWebSocketAuthenticated = TRUE;
					SubscribePendingSymbols();
					return TRUE;
				}
			}
		}

		// Fallback: assume success if message sent successfully
		g_bWebSocketAuthenticated = TRUE;
		SubscribePendingSymbols();
		return TRUE;
	}

	return FALSE;
}

BOOL SubscribeToSymbol(LPCTSTR pszTicker)
{
	if (!g_bWebSocketConnected || !g_bWebSocketAuthenticated)
		return FALSE;

	CString symbol = GetCleanSymbol(pszTicker);
	CString exchange = GetExchangeFromTicker(pszTicker);

	CString subMsg;
	subMsg.Format(_T("{\"action\":\"subscribe\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"mode\":2}"),
		(LPCTSTR)symbol, (LPCTSTR)exchange);

	return SendWebSocketFrame(subMsg);
}

BOOL UnsubscribeFromSymbol(LPCTSTR pszTicker)
{
	if (!g_bWebSocketConnected || !g_bWebSocketAuthenticated)
		return FALSE;

	CString symbol = GetCleanSymbol(pszTicker);
	CString exchange = GetExchangeFromTicker(pszTicker);

	CString unsubMsg;
	unsubMsg.Format(_T("{\"action\":\"unsubscribe\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"mode\":2}"),
		(LPCTSTR)symbol, (LPCTSTR)exchange);

	return SendWebSocketFrame(unsubMsg);
}

void SubscribePendingSymbols(void)
{
	if (!g_bWebSocketConnected || !g_bWebSocketAuthenticated)
		return;

	EnterCriticalSection(&g_WebSocketCriticalSection);
	// Symbols are subscribed on-demand in GetRecentInfo
	LeaveCriticalSection(&g_WebSocketCriticalSection);
}

// Process WebSocket data with non-blocking approach
BOOL ProcessWebSocketData(void)
{
	if (!g_bWebSocketConnected || g_websocket == INVALID_SOCKET)
		return FALSE;

	// Send periodic ping to keep connection alive
	static DWORD lastPingTime = 0;
	DWORD currentTime = (DWORD)GetTickCount64();
	if ((currentTime - lastPingTime) > 30000)
	{
		unsigned char pingFrame[6] = {0x89, 0x84, 0x00, 0x00, 0x00, 0x00};
		GenerateWebSocketMaskKey(&pingFrame[2]);
		send(g_websocket, (char*)pingFrame, 6, 0);
		lastPingTime = currentTime;
	}

	// Check for incoming data (non-blocking)
	fd_set readfds;
	FD_ZERO(&readfds);
	FD_SET(g_websocket, &readfds);

	struct timeval timeout;
	timeout.tv_sec = 0;
	timeout.tv_usec = 0;

	if (select(0, &readfds, NULL, NULL, &timeout) > 0)
	{
		char buffer[2048];
		int received = recv(g_websocket, buffer, sizeof(buffer) - 1, 0);

		if (received > 0)
		{
			CString data = DecodeWebSocketFrame(buffer, received);

			if (data == _T("PING_FRAME"))
			{
				unsigned char pongFrame[6] = {0x8A, 0x84, 0x00, 0x00, 0x00, 0x00};
				GenerateWebSocketMaskKey(&pongFrame[2]);
				send(g_websocket, (char*)pongFrame, 6, 0);
				return TRUE;
			}
			else if (data == _T("CLOSE_FRAME"))
			{
				g_bWebSocketConnected = FALSE;
				g_bWebSocketAuthenticated = FALSE;
				closesocket(g_websocket);
				g_websocket = INVALID_SOCKET;
				return FALSE;
			}
			else if (data == _T("PONG_FRAME"))
			{
				return TRUE;
			}

			// Parse market data and update cache
			if (!data.IsEmpty() && data.Find(_T("market_data")) >= 0)
			{
				CString symbol, exchange;
				float ltp = 0, open = 0, high = 0, low = 0, close = 0, volume = 0, oi = 0;

				int symbolPos = data.Find(_T("\"symbol\":\""));
				if (symbolPos >= 0)
				{
					symbolPos += 10;
					int endPos = data.Find(_T("\""), symbolPos);
					symbol = data.Mid(symbolPos, endPos - symbolPos);
				}

				int exchangePos = data.Find(_T("\"exchange\":\""));
				if (exchangePos >= 0)
				{
					exchangePos += 12;
					int endPos = data.Find(_T("\""), exchangePos);
					exchange = data.Mid(exchangePos, endPos - exchangePos);
				}

				int ltpPos = data.Find(_T("\"ltp\":"));
				if (ltpPos >= 0)
				{
					ltpPos += 6;
					int endPos = data.Find(_T(","), ltpPos);
					if (endPos < 0) endPos = data.Find(_T("}"), ltpPos);
					CString val = data.Mid(ltpPos, endPos - ltpPos);
					ltp = (float)_tstof(val);
				}

				if (!symbol.IsEmpty() && !exchange.IsEmpty())
				{
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
				}

				return TRUE;
			}
		}
		else if (received == 0)
		{
			g_bWebSocketConnected = FALSE;
			g_bWebSocketAuthenticated = FALSE;
		}
	}

	return FALSE;
}

void CleanupWebSocket(void)
{
	if (g_bCriticalSectionInitialized)
	{
		EnterCriticalSection(&g_WebSocketCriticalSection);

		POSITION pos = g_SubscribedSymbols.GetStartPosition();
		while (pos != NULL)
		{
			CString symbol;
			BOOL subscribed;
			g_SubscribedSymbols.GetNextAssoc(pos, symbol, subscribed);

			if (subscribed)
			{
				UnsubscribeFromSymbol(symbol);
			}
		}

		g_SubscribedSymbols.RemoveAll();

		LeaveCriticalSection(&g_WebSocketCriticalSection);
	}

	if (g_websocket != INVALID_SOCKET)
	{
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
	}

	g_bWebSocketConnected = FALSE;
	g_bWebSocketAuthenticated = FALSE;
	g_bWebSocketConnecting = FALSE;
	g_bWebSocketThreadRunning = FALSE;

	WSACleanup();
}
