#!/usr/bin/env python3
import requests

# Test the API key that's currently being used
api_key = "259af85739164007c25ffd2b136acfa5b8d3fea95e17f9f8b897155e6c6be17b"
base_url = "http://127.0.0.1:5000/api/v1"

print(f"Testing API key: {api_key[:10]}...")

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