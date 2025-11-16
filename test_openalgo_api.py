#!/usr/bin/env python3
"""
Test script for OpenAlgo API endpoints
"""

import requests
import json

def test_openalgo_api():
    # Test corrected endpoints
    base_url = 'http://localhost:5000/api/v1'
    api_key = '89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0'

    print('Testing corrected OpenAlgo API endpoints...')

    # Test funds endpoint (POST with apikey in body)
    try:
        response = requests.post(f'{base_url}/funds/', json={'apikey': api_key})
        print(f'Funds endpoint: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'Status: {result.get("status")}')
            if result.get('data'):
                print(f'Funds data available: {len(result.get("data", {}))} fields')
        else:
            print(f'Response: {response.text[:200]}')
    except Exception as e:
        print(f'Funds endpoint error: {e}')

    # Test positionbook endpoint
    try:
        response = requests.post(f'{base_url}/positionbook/', json={'apikey': api_key})
        print(f'Positionbook endpoint: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'Status: {result.get("status")}')
        else:
            print(f'Response: {response.text[:200]}')
    except Exception as e:
        print(f'Positionbook endpoint error: {e}')

    # Test orderbook endpoint
    try:
        response = requests.post(f'{base_url}/orderbook/', json={'apikey': api_key})
        print(f'Orderbook endpoint: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'Status: {result.get("status")}')
        else:
            print(f'Response: {response.text[:200]}')
    except Exception as e:
        print(f'Orderbook endpoint error: {e}')

    # Test ping endpoint
    try:
        response = requests.post(f'{base_url}/ping/', json={'apikey': api_key})
        print(f'Ping endpoint: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'Status: {result.get("status")}')
        else:
            print(f'Response: {response.text[:200]}')
    except Exception as e:
        print(f'Ping endpoint error: {e}')

if __name__ == "__main__":
    test_openalgo_api()
