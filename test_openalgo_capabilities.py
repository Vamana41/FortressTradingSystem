#!/usr/bin/env python3
"""
Test what OpenAlgo actually supports - all exchanges and symbol types
"""
import requests

api_key = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
base_url = "http://127.0.0.1:5000/api/v1"

def test_symbol(exchange, symbol):
    """Test a single symbol and return result"""
    try:
        response = requests.post(
            f"{base_url}/quotes",
            json={
                'apikey': api_key,
                'exchange': exchange,
                'symbol': symbol
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return f"SUCCESS - LTP: {data['data']['ltp']}"
            else:
                return f"API Error: {data.get('message', 'Unknown error')}"
        else:
            return f"HTTP {response.status_code}: {response.text[:50]}..."
    except Exception as e:
        return f"Exception: {e}"

# Test comprehensive symbol list from your original system
test_symbols = [
    # MCX Futures (original format)
    ("MCX", "CRUDEOILM25APRFUT"),
    ("MCX", "GOLDPETAL25FEBFUT"),
    ("MCX", "GOLDM25FEBFUT"),
    ("MCX", "NATGASMINI25APRFUT"),
    ("MCX", "SILVERMIC25APRFUT"),
    ("MCX", "ZINCMINI25APRFUT"),
    ("MCX", "ALUMINI25APRFUT"),
    ("MCX", "COPPER25APRFUT"),
    ("MCX", "LEADMINI25APRFUT"),

    # NSE Futures (original format)
    ("NSE", "BANKNIFTY25APRFUT"),
    ("NSE", "NIFTY25APRFUT"),

    # NSE Equities (simple format)
    ("NSE", "SBIN"),
    ("NSE", "RELIANCE"),
    ("NSE", "TCS"),
    ("NSE", "INFY"),
    ("NSE", "ITC"),

    # NSE Equities (with -EQ)
    ("NSE", "SBIN-EQ"),
    ("NSE", "RELIANCE-EQ"),

    # Indices
    ("NSE", "NIFTY"),
    ("NSE", "BANKNIFTY"),
    ("NSE", "NIFTY50"),
    ("NSE", "NIFTYBANK"),

    # NFO Options
    ("NFO", "NIFTY17JAN2519500CE"),
    ("NFO", "BANKNIFTY17JAN2545000PE"),
]

print("Testing OpenAlgo capabilities with comprehensive symbol list...")
print("=" * 80)

working_symbols = []
for exchange, symbol in test_symbols:
    result = test_symbol(exchange, symbol)
    status = "✓" if "SUCCESS" in result else "✗"
    print(f"{status} {exchange}:{symbol} - {result}")

    if "SUCCESS" in result:
        working_symbols.append((exchange, symbol))

print("\n" + "=" * 80)
print(f"WORKING SYMBOLS ({len(working_symbols)}):")
for exchange, symbol in working_symbols:
    print(f"  {exchange}:{symbol}")
