#!/usr/bin/env python3
"""
OpenAlgo API Integration Test Script
Use this script to test API endpoints once you have a valid API key.
"""

import requests
import json

def test_with_api_key(api_key):
    """Test all API endpoints with a valid API key."""

    base_url = "http://127.0.0.1:5000/api/v1"

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Test ping endpoint
    print("Testing ping endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/ping", headers=headers, json=data)
    print(f"Ping: {response.status_code} - {response.text[:100]}")

    # Test quotes endpoint
    print("\nTesting quotes endpoint...")
    data = {
        "apikey": api_key,
        "symbol": "NIFTY",
        "exchange": "NSE"
    }
    response = requests.post(f"{base_url}/quotes", headers=headers, json=data)
    print(f"Quotes: {response.status_code} - {response.text[:100]}")

    # Test funds endpoint
    print("\nTesting funds endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/funds", headers=headers, json=data)
    print(f"Funds: {response.status_code} - {response.text[:100]}")

    # Test orderbook endpoint
    print("\nTesting orderbook endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/orderbook", headers=headers, json=data)
    print(f"Orderbook: {response.status_code} - {response.text[:100]}")

if __name__ == "__main__":
    # Replace with your actual API key
    API_KEY = "your_api_key_here"
    test_with_api_key(API_KEY)
