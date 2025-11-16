#!/usr/bin/env python3
import requests

# Test MCX symbols with MCX exchange
api_key = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
base_url = "http://127.0.0.1:5000/api/v1"

# Test MCX symbols - try different formats
mcx_symbols = [
    ("MCX", "CRUDEOILM"),
    ("MCX", "CRUDEOILM25APRFUT"),
    ("MCX", "GOLDPETAL"),
    ("MCX", "GOLDM"),
]

print("Testing MCX symbols...")
for exchange, symbol in mcx_symbols:
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
        print(f"{exchange}:{symbol} - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                print(f"  LTP: {data['data']['ltp']}")
            else:
                print(f"  Error: {data.get('message', 'Unknown error')}")
        else:
            print(f"  Response: {response.text[:100]}...")
    except Exception as e:
        print(f"{exchange}:{symbol} - Error: {e}")
    print()