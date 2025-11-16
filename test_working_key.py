#!/usr/bin/env python3
import requests

# Test the API key that works in debug script
api_key = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
base_url = "http://127.0.0.1:5000/api/v1"

print(f"Testing working API key: {api_key[:10]}...")

# Test ping endpoint
try:
    response = requests.post(
        f"{base_url}/ping",
        json={'apikey': api_key},
        timeout=10
    )
    print(f"Ping status: {response.status_code}")
    print(f"Ping response: {response.text}")
except Exception as e:
    print(f"Ping error: {e}")

# Test quotes endpoint
try:
    response = requests.post(
        f"{base_url}/quotes",
        json={
            'apikey': api_key,
            'exchange': 'NSE',
            'symbol': 'SBIN'
        },
        timeout=10
    )
    print(f"Quotes status: {response.status_code}")
    print(f"Quotes response: {response.text[:100]}...")
except Exception as e:
    print(f"Quotes error: {e}")