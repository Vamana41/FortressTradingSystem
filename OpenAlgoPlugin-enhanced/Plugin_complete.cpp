// Enhanced Plugin.cpp - Complete implementation with non-blocking operations
// Based on Rtd_Ws_AB_plugin patterns for reliability
#include "stdafx.h"
#include "resource.h"
#include "OpenAlgoGlobals.h"
#include "Plugin.h"
#include "Plugin_Legacy.h"
#include "OpenAlgoConfigDlg.h"
#include <math.h>
#include <time.h>
#include <stdlib.h>
#include <process.h>  // For _beginthreadex

// Plugin identification
#define PLUGIN_NAME "OpenAlgo Enhanced Plugin"
#define VENDOR_NAME "Fortress Trading System"
#define PLUGIN_VERSION 10004
#define PLUGIN_ID PIDCODE('F', 'T', 'S', 'E')
#define THIS_PLUGIN_TYPE PLUGIN_TYPE_DATA
#define AGENT_NAME PLUGIN_NAME

// Timer IDs
#define TIMER_INIT 198
#define TIMER_REFRESH 199
#define TIMER_WEBSOCKET_PING 200
#define RETRY_COUNT 8
#define MAX_TIMEOUT_MS 3000
#define CONNECTION_TIMEOUT_MS 5000

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

// WebSocket connection management with robust error handling
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
static DWORD g_dwLastPingTime = 0;

// Enhanced connection state tracking
static BOOL g_bConnectionInProgress = FALSE;
static DWORD g_dwConnectionStartTime = 0;
static int g_nConsecutiveFailures = 0;
static DWORD g_dwLastSuccessfulConnection = 0;

// Cache for recent quotes with TTL
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
	DWORD ttl;  // Time to live in milliseconds

	QuoteCache() : ltp(0.0f), open(0.0f), high(0.0f), low(0.0f),
	               close(0.0f), volume(0.0f), oi(0.0f), lastUpdate(0), ttl(5000) {
	}
};

static CMap<CString, LPCTSTR, QuoteCache, QuoteCache&> g_QuoteCache;

typedef CArray< struct Quotation, struct Quotation > CQuoteArray;

// Forward declarations
VOID CALLBACK OnTimerProc(HWND, UINT, UINT_PTR, DWORD);
void SetupRetry(void);
BOOL TestOpenAlgoConnection(void);
BOOL GetOpenAlgoQuote(LPCTSTR pszTicker, QuoteCache& quote);
int GetOpenAlgoHistory(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes);
CString GetExchangeFromTicker(LPCTSTR pszTicker);
CString GetIntervalString(int nPeriodicity);
void ConvertUnixToPackedDate(time_t unixTime, union AmiDate* pAmiDate);

// Enhanced WebSocket functions with non-blocking operations
unsigned __stdcall WebSocketThreadProc(void* pParam);
BOOL InitializeWebSocket(void);
void CleanupWebSocket(void);
BOOL ConnectWebSocketNonBlocking(void);
BOOL AuthenticateWebSocketNonBlocking(void);
BOOL SendWebSocketFrame(const CString& message);
CString DecodeWebSocketFrame(const char* buffer, int length);
BOOL SubscribeToSymbol(LPCTSTR pszTicker);
BOOL UnsubscribeFromSymbol(LPCTSTR pszTicker);
BOOL ProcessWebSocketDataNonBlocking(void);
void GenerateWebSocketMaskKey(unsigned char* maskKey);
void SubscribePendingSymbols(void);
BOOL IsConnectionTimeout(void);
void ResetConnectionState(void);

// Helper function for mixed EOD/Intraday data
int FindLastBarOfMatchingType(int nPeriodicity, int nLastValid, struct Quotation* pQuotes);

// Helper function to compare two quotations for sorting by timestamp
int CompareQuotations(const void* a, const void* b);

// Enhanced error handling and logging
void LogError(LPCTSTR pszMessage);
void LogWarning(LPCTSTR pszMessage);
void LogInfo(LPCTSTR pszMessage);
BOOL IsValidResponse(const CString& response);

///////////////////////////////
// Enhanced Helper Functions
///////////////////////////////

// Robust logging with error tracking
void LogError(LPCTSTR pszMessage)
{
	// Log to debug output and track errors
	CString logMsg;
	logMsg.Format(_T("[ERROR] %s"), pszMessage);
	OutputDebugString(logMsg);

	// Increment failure counter
	g_nConsecutiveFailures++;

	// If too many consecutive failures, mark as disconnected
	if (g_nConsecutiveFailures > 10)
	{
		g_nStatus = STATUS_DISCONNECTED;
		ResetConnectionState();
	}
}

void LogWarning(LPCTSTR pszMessage)
{
	CString logMsg;
	logMsg.Format(_T("[WARN] %s"), pszMessage);
	OutputDebugString(logMsg);
}

void LogInfo(LPCTSTR pszMessage)
{
	CString logMsg;
	logMsg.Format(_T("[INFO] %s"), pszMessage);
	OutputDebugString(logMsg);
}

// Validate API responses
BOOL IsValidResponse(const CString& response)
{
	if (response.IsEmpty())
		return FALSE;

	// Check for basic JSON structure
	if (response.Find(_T("{")) < 0 || response.Find(_T("}")) < 0)
		return FALSE;

	// Check for error indicators
	if (response.Find(_T("\"error\"")) >= 0 || response.Find(_T("\"failed\"")) >= 0)
		return FALSE;

	return TRUE;
}

// Connection timeout management
BOOL IsConnectionTimeout(void)
{
	if (!g_bConnectionInProgress)
		return FALSE;

	DWORD dwElapsed = GetTickCount64() - g_dwConnectionStartTime;
	return (dwElapsed > CONNECTION_TIMEOUT_MS);
}

void ResetConnectionState(void)
{
	g_bConnectionInProgress = FALSE;
	g_dwConnectionStartTime = 0;
	g_bWebSocketConnecting = FALSE;

	if (g_websocket != INVALID_SOCKET)
	{
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
	}

	g_bWebSocketConnected = FALSE;
	g_bWebSocketAuthenticated = FALSE;
}

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

CString GetIntervalString(int nPeriodicity)
{
	if (nPeriodicity == 60)
		return _T("1m");
	else if (nPeriodicity == 86400)
		return _T("D");
	else
		return _T("D");
}

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

// Enhanced quote fetching with better error handling
BOOL GetOpenAlgoQuote(LPCTSTR pszTicker, QuoteCache& quote)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_oApiKey.IsEmpty())
	{
		LogWarning(_T("API key not configured"));
		return FALSE;
	}

	// Check connection timeout
	if (IsConnectionTimeout())
	{
		LogError(_T("Connection timeout during quote fetch"));
		ResetConnectionState();
		return FALSE;
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
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, MAX_TIMEOUT_MS);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, MAX_TIMEOUT_MS);

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

						if (IsValidResponse(oResponse) && oResponse.Find(_T("\"status\":\"success\"")) >= 0)
						{
							// Parse quote data with error checking
							int pos;

							// Parse LTP
							pos = oResponse.Find(_T("\"ltp\":"));
							if (pos >= 0)
							{
								pos += 6;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.ltp = (float)_tstof(val);
							}

							// Parse Open
							pos = oResponse.Find(_T("\"open\":"));
							if (pos >= 0)
							{
								pos += 7;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.open = (float)_tstof(val);
							}

							// Parse High
							pos = oResponse.Find(_T("\"high\":"));
							if (pos >= 0)
							{
								pos += 7;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.high = (float)_tstof(val);
							}

							// Parse Low
							pos = oResponse.Find(_T("\"low\":"));
							if (pos >= 0)
							{
								pos += 6;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.low = (float)_tstof(val);
							}

							// Parse Volume
							pos = oResponse.Find(_T("\"volume\":"));
							if (pos >= 0)
							{
								pos += 9;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.volume = (float)_tstof(val);
							}

							// Parse OI
							pos = oResponse.Find(_T("\"oi\":"));
							if (pos >= 0)
							{
								pos += 5;
								int endPos = oResponse.Find(_T(","), pos);
								if (endPos < 0) endPos = oResponse.Find(_T("}"), pos);
								CString val = oResponse.Mid(pos, endPos - pos);
								quote.oi = (float)_tstof(val);
							}

							// Parse Previous Close
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
							quote.ttl = 5000; // 5 second TTL

							bSuccess = TRUE;
							g_nConsecutiveFailures = 0; // Reset failure counter
						}
					}
					else
					{
						CString errorMsg;
						errorMsg.Format(_T("Quote API returned status %d"), dwStatusCode);
						LogWarning(errorMsg);
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
		LogError(_T("Exception in GetOpenAlgoQuote"));
		e->Delete();
	}
	catch (...)
	{
		LogError(_T("Unknown exception in GetOpenAlgoQuote"));
	}

	return bSuccess;
}

// Enhanced historical data fetching
int GetOpenAlgoHistory(LPCTSTR pszTicker, int nPeriodicity, int nLastValid, int nSize, struct Quotation* pQuotes)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_oApiKey.IsEmpty())
	{
		LogWarning(_T("API key not configured for history fetch"));
		return nLastValid + 1;
	}

	// Check connection timeout
	if (IsConnectionTimeout())
	{
		LogError(_T("Connection timeout during history fetch"));
		ResetConnectionState();
		return nLastValid + 1;
	}

	try
	{
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/history"));

		CString symbol = GetCleanSymbol(pszTicker);
		CString exchange = GetExchangeFromTicker(pszTicker);
		CString interval = GetIntervalString(nPeriodicity);

		CTime currentTime = CTime::GetCurrentTime();
		CTime todayDate = CTime(currentTime.GetYear(), currentTime.GetMonth(), currentTime.GetDay(), 0, 0, 0);

		CTime startTime;
		CTime endTime = todayDate;

		// Smart backfill logic with safety limits
		if (nLastValid >= 0 && pQuotes != NULL)
		{
			int lastMatchingBarIndex = FindLastBarOfMatchingType(nPeriodicity, nLastValid, pQuotes);

			if (lastMatchingBarIndex < 0)
			{
				if (nPeriodicity == 60)
					startTime = todayDate - CTimeSpan(30, 0, 0, 0);
				else
					startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
			}
			else
			{
				// Extract last bar's date safely
				int lastBarYear = pQuotes[lastMatchingBarIndex].DateTime.PackDate.Year;
				int lastBarMonth = pQuotes[lastMatchingBarIndex].DateTime.PackDate.Month;
				int lastBarDay = pQuotes[lastMatchingBarIndex].DateTime.PackDate.Day;

				CTime lastBarDate;
				try
				{
					lastBarDate = CTime(lastBarYear, lastBarMonth, lastBarDay, 0, 0, 0);
				}
				catch (...)
				{
					// Invalid date - fallback to initial load
					if (nPeriodicity == 60)
						startTime = todayDate - CTimeSpan(30, 0, 0, 0);
					else
						startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
					goto skip_gap_detection;
				}

				if (lastBarDate > todayDate)
				{
					// Future date detected - corrupted data
					if (nPeriodicity == 60)
						startTime = todayDate - CTimeSpan(30, 0, 0, 0);
					else
						startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
				}
				else
				{
					CTimeSpan gap = todayDate - lastBarDate;
					int gapDays = (int)gap.GetDays();

					if (nPeriodicity == 60)  // 1-minute data
					{
						const int MAX_BACKFILL_DAYS_1M = 30;
						if (gapDays > MAX_BACKFILL_DAYS_1M)
							startTime = todayDate - CTimeSpan(MAX_BACKFILL_DAYS_1M, 0, 0, 0);
						else
							startTime = lastBarDate;
					}
					else  // Daily data
					{
						const int MAX_BACKFILL_DAYS_DAILY = 730;
						const int MIN_DAILY_BARS = 250;
						const int STALENESS_THRESHOLD_DAYS = 365;

						if (lastMatchingBarIndex < MIN_DAILY_BARS)
							startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
						else if (gapDays > STALENESS_THRESHOLD_DAYS)
							startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
						else if (gapDays > MAX_BACKFILL_DAYS_DAILY)
							startTime = todayDate - CTimeSpan(MAX_BACKFILL_DAYS_DAILY, 0, 0, 0);
						else
							startTime = lastBarDate;
					}
				}
			}
		}
		else
		{
			if (nPeriodicity == 60)
				startTime = todayDate - CTimeSpan(30, 0, 0, 0);
			else
				startTime = todayDate - CTimeSpan(3650, 0, 0, 0);
		}

skip_gap_detection:

		CString startDate = startTime.Format(_T("%Y-%m-%d"));
		CString endDate = endTime.Format(_T("%Y-%m-%d"));

		CString oPostData;
		oPostData.Format(_T("{\"apikey\":\"%s\",\"symbol\":\"%s\",\"exchange\":\"%s\",\"interval\":\"%s\",\"start_date\":\"%s\",\"end_date\":\"%s\"}"),
			(LPCTSTR)g_oApiKey, (LPCTSTR)symbol, (LPCTSTR)exchange, (LPCTSTR)interval, (LPCTSTR)startDate, (LPCTSTR)endDate);

		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, 10000);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, 10000);

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
				_T("/api/v1/history"),
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

						if (IsValidResponse(oResponse) && oResponse.Find(_T("\"status\":\"success\"")) >= 0)
						{
							// Parse historical data with enhanced error handling
							int dataStart = oResponse.Find(_T("\"data\":["));
							if (dataStart >= 0)
							{
								dataStart += 8;
								int dataEnd = oResponse.Find(_T("]"), dataStart);
								if (dataEnd < 0) dataEnd = oResponse.GetLength();
								CString dataArray = oResponse.Mid(dataStart, dataEnd - dataStart);

								if (dataArray.GetLength() < 10)
								{
									LogWarning(_T("Insufficient historical data returned"));
									return nLastValid + 1;
								}

								// Parse candles with duplicate detection
								int quoteIndex = 0;
								int pos = 0;

								BOOL bHasExistingData = (nLastValid >= 0);
								if (bHasExistingData)
								{
									quoteIndex = nLastValid + 1;
								}

								while (pos < dataArray.GetLength() && quoteIndex < nSize)
								{
									int candleStart = dataArray.Find(_T("{"), pos);
									if (candleStart < 0) break;

									int candleEnd = dataArray.Find(_T("}"), candleStart);
									if (candleEnd < 0) break;

									CString candle = dataArray.Mid(candleStart, candleEnd - candleStart + 1);

									// Parse timestamp with validation
									int tsPos = candle.Find(_T("\"timestamp\":"));
									if (tsPos >= 0)
									{
										tsPos += 12;
										int tsEnd = candle.Find(_T(","), tsPos);
										if (tsEnd < 0) tsEnd = candle.Find(_T("}"), tsPos);
										CString tsStr = candle.Mid(tsPos, tsEnd - tsPos);
										time_t timestamp = (time_t)_tstoi64(tsStr);

										// Validate timestamp
										if (timestamp <= 0 || timestamp > 4102444800) // Sanity check: not after 2100
										{
											pos = candleEnd + 1;
											continue;
										}

										// Convert to AmiBroker date format
										if (nPeriodicity == 86400) // Daily data
										{
											ConvertUnixToPackedDate(timestamp, &pQuotes[quoteIndex].DateTime);
											pQuotes[quoteIndex].DateTime.Date |= DAILY_MASK;
											pQuotes[quoteIndex].DateTime.PackDate.Hour = 31;
											pQuotes[quoteIndex].DateTime.PackDate.Minute = 63;
											pQuotes[quoteIndex].DateTime.PackDate.Second = 0;
											pQuotes[quoteIndex].DateTime.PackDate.MilliSec = 0;
											pQuotes[quoteIndex].DateTime.PackDate.MicroSec = 0;
										}
										else
										{
											ConvertUnixToPackedDate(timestamp, &pQuotes[quoteIndex].DateTime);
											if (nPeriodicity == 60) // 1-minute data
											{
												pQuotes[quoteIndex].DateTime.PackDate.Second = 0;
												pQuotes[quoteIndex].DateTime.PackDate.MilliSec = 0;
												pQuotes[quoteIndex].DateTime.PackDate.MicroSec = 0;
											}
										}

										// Parse OHLCV with validation
										int oPos = candle.Find(_T("\"open\":"));
										if (oPos >= 0)
										{
											oPos += 7;
											int oEnd = candle.Find(_T(","), oPos);
											CString val = candle.Mid(oPos, oEnd - oPos);
											pQuotes[quoteIndex].Open = (float)_tstof(val);
										}

										int hPos = candle.Find(_T("\"high\":"));
										if (hPos >= 0)
										{
											hPos += 7;
											int hEnd = candle.Find(_T(","), hPos);
											CString val = candle.Mid(hPos, hEnd - hPos);
											pQuotes[quoteIndex].High = (float)_tstof(val);
										}

										int lPos = candle.Find(_T("\"low\":"));
										if (lPos >= 0)
										{
											lPos += 6;
											int lEnd = candle.Find(_T(","), lPos);
											CString val = candle.Mid(lPos, lEnd - lPos);
											pQuotes[quoteIndex].Low = (float)_tstof(val);
										}

										int cPos = candle.Find(_T("\"close\":"));
										if (cPos >= 0)
										{
											cPos += 8;
											int cEnd = candle.Find(_T(","), cPos);
											if (cEnd < 0) cEnd = candle.Find(_T("}"), cPos);
											CString val = candle.Mid(cPos, cEnd - cPos);
											pQuotes[quoteIndex].Price = (float)_tstof(val);
										}

										int vPos = candle.Find(_T("\"volume\":"));
										if (vPos >= 0)
										{
											vPos += 9;
											int vEnd = candle.Find(_T(","), vPos);
											if (vEnd < 0) vEnd = candle.Find(_T("}"), vPos);
											CString val = candle.Mid(vPos, vEnd - vPos);
											pQuotes[quoteIndex].Volume = (float)_tstof(val);
										}

										int oiPos = candle.Find(_T("\"oi\":"));
										if (oiPos >= 0)
										{
											oiPos += 5;
											int oiEnd = candle.Find(_T(","), oiPos);
											if (oiEnd < 0) oiEnd = candle.Find(_T("}"), oiPos);
											CString val = candle.Mid(oiPos, oiEnd - oiPos);
											pQuotes[quoteIndex].OpenInterest = (float)_tstof(val);
										}

										// Set auxiliary data
										pQuotes[quoteIndex].AuxData1 = 0;
										pQuotes[quoteIndex].AuxData2 = 0;

										// Duplicate detection
										BOOL bIsDuplicate = FALSE;
										if (bHasExistingData)
										{
											BOOL bNewBarIsEOD = (pQuotes[quoteIndex].DateTime.PackDate.Hour == DATE_EOD_HOURS &&
											                     pQuotes[quoteIndex].DateTime.PackDate.Minute == DATE_EOD_MINUTES);

											for (int i = max(0, nLastValid - 100); i <= nLastValid; i++)
											{
												BOOL bExistingBarIsEOD = (pQuotes[i].DateTime.PackDate.Hour == DATE_EOD_HOURS &&
												                          pQuotes[i].DateTime.PackDate.Minute == DATE_EOD_MINUTES);

												if (bNewBarIsEOD != bExistingBarIsEOD)
													continue;

												BOOL bSameBar = FALSE;
												if (bNewBarIsEOD)
												{
													bSameBar = (pQuotes[quoteIndex].DateTime.PackDate.Year == pQuotes[i].DateTime.PackDate.Year &&
													           pQuotes[quoteIndex].DateTime.PackDate.Month == pQuotes[i].DateTime.PackDate.Month &&
													           pQuotes[quoteIndex].DateTime.PackDate.Day == pQuotes[i].DateTime.PackDate.Day);
												}
												else
												{
													bSameBar = (pQuotes[quoteIndex].DateTime.PackDate.Year == pQuotes[i].DateTime.PackDate.Year &&
													           pQuotes[quoteIndex].DateTime.PackDate.Month == pQuotes[i].DateTime.PackDate.Month &&
													           pQuotes[quoteIndex].DateTime.PackDate.Day == pQuotes[i].DateTime.PackDate.Day &&
													           pQuotes[quoteIndex].DateTime.PackDate.Hour == pQuotes[i].DateTime.PackDate.Hour &&
													           pQuotes[quoteIndex].DateTime.PackDate.Minute == pQuotes[i].DateTime.PackDate.Minute);
												}

												if (bSameBar)
												{
													bIsDuplicate = TRUE;
													pQuotes[i].Price = pQuotes[quoteIndex].Price;
													pQuotes[i].High = max(pQuotes[i].High, pQuotes[quoteIndex].High);
													pQuotes[i].Low = (pQuotes[i].Low == 0) ? pQuotes[quoteIndex].Low : min(pQuotes[i].Low, pQuotes[quoteIndex].Low);
													pQuotes[i].Volume = pQuotes[quoteIndex].Volume;
													pQuotes[i].OpenInterest = pQuotes[quoteIndex].OpenInterest;
													break;
												}
											}
										}

										if (!bIsDuplicate)
										{
											quoteIndex++;
										}
									}

									pos = candleEnd + 1;
								}

								pFile->Close();
								delete pFile;
								pConnection->Close();
								delete pConnection;
								oSession.Close();

								// Sort quotes chronologically
								if (quoteIndex > 0)
								{
									qsort(pQuotes, quoteIndex, sizeof(struct Quotation), CompareQuotations);
								}

								// Handle array overflow
								if (quoteIndex > nSize)
								{
									int excessBars = quoteIndex - nSize;
									memmove(pQuotes, pQuotes + excessBars, nSize * sizeof(struct Quotation));
									quoteIndex = nSize;
								}

								g_nConsecutiveFailures = 0; // Reset failure counter
								return quoteIndex;
							}
						}
					}
					else
					{
						CString errorMsg;
						errorMsg.Format(_T("History API returned status %d"), dwStatusCode);
						LogWarning(errorMsg);
					}
				}

				if (pFile)
				{
					pFile->Close();
					delete pFile;
				}
			}

			if (pConnection)
			{
				pConnection->Close();
				delete pConnection;
			}
		}

		oSession.Close();
	}
	catch (CInternetException* e)
	{
		LogError(_T("Exception in GetOpenAlgoHistory"));
		e->Delete();
	}
	catch (...)
	{
		LogError(_T("Unknown exception in GetOpenAlgoHistory"));
	}

	return nLastValid + 1;
}

// Enhanced connection testing with timeout management
BOOL TestOpenAlgoConnection(void)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	if (g_oApiKey.IsEmpty())
	{
		LogWarning(_T("API key not configured for connection test"));
		return FALSE;
	}

	// Prevent concurrent connection attempts
	if (g_bConnectionInProgress)
	{
		if (IsConnectionTimeout())
		{
			LogError(_T("Connection test timeout"));
			ResetConnectionState();
			return FALSE;
		}
		return FALSE; // Another connection in progress
	}

	g_bConnectionInProgress = TRUE;
	g_dwConnectionStartTime = GetTickCount64();

	BOOL bConnected = FALSE;

	try
	{
		CString oURL = BuildOpenAlgoURL(g_oServer, g_nPortNumber, _T("/api/v1/ping"));

		CInternetSession oSession(AGENT_NAME, 1, INTERNET_OPEN_TYPE_DIRECT, NULL, NULL,
			INTERNET_FLAG_DONT_CACHE);
		oSession.SetOption(INTERNET_OPTION_CONNECT_TIMEOUT, MAX_TIMEOUT_MS);
		oSession.SetOption(INTERNET_OPTION_RECEIVE_TIMEOUT, MAX_TIMEOUT_MS);

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
						while (pFile->ReadString(oLine) && oResponse.GetLength() < 500)
						{
							oResponse += oLine;
						}

						if (IsValidResponse(oResponse) &&
							(oResponse.Find(_T("\"status\":\"success\"")) >= 0 || oResponse.Find(_T("\"status\": \"success\"")) >= 0) &&
							(oResponse.Find(_T("\"message\":\"pong\"")) >= 0 || oResponse.Find(_T("\"message\": \"pong\"")) >= 0))
						{
							bConnected = TRUE;
							g_nConsecutiveFailures = 0;
							g_dwLastSuccessfulConnection = GetTickCount64();
							LogInfo(_T("Connection test successful"));
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
		CString errorMsg;
		errorMsg.Format(_T("Connection test failed: Internet exception"));
		LogError(errorMsg);
		e->Delete();
	}
	catch (...)
	{
		LogError(_T("Connection test failed: Unknown exception"));
	}

	g_bConnectionInProgress = FALSE;
	return bConnected;
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
		LogWarning(_T("Connection retry scheduled"));
	}
	else
	{
		g_nStatus = STATUS_SHUTDOWN;
		LogError(_T("Max retries exceeded, shutting down"));
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
		LogInfo(_T("Timer triggered - testing connection"));

		if (!TestOpenAlgoConnection())
		{
			if (g_hAmiBrokerWnd != NULL)
			{
				KillTimer(g_hAmiBrokerWnd, idEvent);
			}
			SetupRetry();
			return;
		}

		g_nStatus = STATUS_CONNECTED;
		g_nRetryCount = RETRY_COUNT;
		LogInfo(_T("Connection established"));

		if (g_hAmiBrokerWnd != NULL)
		{
			::PostMessage(g_hAmiBrokerWnd, WM_USER_STREAMING_UPDATE, 0, 0);

			if (idEvent == TIMER_INIT)
			{
				KillTimer(g_hAmiBrokerWnd, TIMER_INIT);
				SetTimer(g_hAmiBrokerWnd, TIMER_REFRESH, g_nRefreshInterval * 1000, (TIMERPROC)OnTimerProc);
				LogInfo(_T("Switched to refresh timer"));
			}
		}
	}
	else if (idEvent == TIMER_WEBSOCKET_PING)
	{
		// WebSocket ping timer - non-blocking
		ProcessWebSocketDataNonBlocking();
	}
}

// Enhanced WebSocket thread for non-blocking operations
unsigned __stdcall WebSocketThreadProc(void* pParam)
{
	AFX_MANAGE_STATE(AfxGetStaticModuleState());

	LogInfo(_T("WebSocket thread started"));

	while (g_bWebSocketThreadRunning)
	{
		if (g_bWebSocketConnected && g_bWebSocketAuthenticated)
		{
			ProcessWebSocketDataNonBlocking();
		}

		Sleep(100); // 100ms polling interval
	}

	LogInfo(_T("WebSocket thread stopped"));
	return 0;
}

// Enhanced WebSocket initialization
BOOL InitializeWebSocket(void)
{
	if (g_bWebSocketConnected)
		return TRUE;

	if (g_bWebSocketConnecting)
		return FALSE;

	if (g_oWebSocketUrl.IsEmpty() || g_oApiKey.IsEmpty())
	{
		LogWarning(_T("WebSocket URL or API key not configured"));
		return FALSE;
	}

	// Prevent rapid reconnection attempts
	DWORD dwNow = GetTickCount64();
	if ((dwNow - g_dwLastConnectionAttempt) < 10000) // 10 second minimum delay
	{
		LogWarning(_T("WebSocket connection attempt too soon"));
		return FALSE;
	}

	g_dwLastConnectionAttempt = dwNow;
	g_bWebSocketConnecting = TRUE;

	// Start WebSocket thread for non-blocking operations
	if (!g_bWebSocketThreadRunning)
	{
		g_bWebSocketThreadRunning = TRUE;
		unsigned threadID;
		g_hWebSocketThread = (HANDLE)_beginthreadex(NULL, 0, WebSocketThreadProc, NULL, 0, &threadID);

		if (g_hWebSocketThread == NULL)
		{
			LogError(_T("Failed to create WebSocket thread"));
			g_bWebSocketThreadRunning = FALSE;
			g_bWebSocketConnecting = FALSE;
			return FALSE;
		}
	}

	// Attempt connection
	BOOL result = ConnectWebSocketNonBlocking();
	g_bWebSocketConnecting = FALSE;

	return result;
}

// Non-blocking WebSocket connection
BOOL ConnectWebSocketNonBlocking(void)
{
	// Initialize Winsock
	WSADATA wsaData;
	if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0)
	{
		LogError(_T("WSAStartup failed"));
		return FALSE;
	}

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
	{
		LogError(_T("Failed to create WebSocket socket"));
		WSACleanup();
		return FALSE;
	}

	// Set socket to non-blocking mode immediately
	u_long mode = 1;
	if (ioctlsocket(g_websocket, FIONBIO, &mode) != 0)
	{
		LogError(_T("Failed to set non-blocking mode"));
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
		WSACleanup();
		return FALSE;
	}

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
		LogError(_T("Failed to resolve WebSocket host"));
		closesocket(g_websocket);
		g_websocket = INVALID_SOCKET;
		WSACleanup();
		return FALSE;
	}

	// Connect with timeout using select
	if (connect(g_websocket, result->ai_addr, (int)result->ai_addrlen) == SOCKET_ERROR)
	{
		int error = WSAGetLastError();
		if (error != WSAEWOULDBLOCK)
