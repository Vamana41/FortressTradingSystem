#!/usr/bin/env python3
"""
OpenAlgo Debug - Test API key and authentication issues
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpenAlgoDebug")

# Test different API keys and formats
API_KEYS = [
    "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371",
    "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
]

REST_API_URL = "http://127.0.0.1:5000/api/v1"

def test_api_key(api_key):
    """Test API key with different formats"""
    logger.info(f"Testing API key: {api_key[:10]}...")

    # Test 1: Standard format (apikey in JSON body)
    try:
        url = f"{REST_API_URL}/ping"
        payload = {"apikey": api_key}

        response = requests.post(url, json=payload, timeout=5)
        logger.info(f"Ping test - Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Ping response: {data}")
            return True
        else:
            logger.error(f"Ping failed: {response.text}")

    except Exception as e:
        logger.error(f"Ping error: {e}")

    # Test 2: Quotes endpoint
    try:
        url = f"{REST_API_URL}/quotes"
        payload = {
            "apikey": api_key,
            "exchange": "NSE",
            "symbol": "SBIN"
        }

        response = requests.post(url, json=payload, timeout=5)
        logger.info(f"Quotes test - Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Quotes response: {data}")
            return True
        else:
            logger.error(f"Quotes failed: {response.text}")

    except Exception as e:
        logger.error(f"Quotes error: {e}")

    return False

def main():
    logger.info("Testing OpenAlgo API keys...")

    for api_key in API_KEYS:
        logger.info("=" * 50)
        if test_api_key(api_key):
            logger.info(f"✅ API key {api_key[:10]}... is WORKING")
            break
        else:
            logger.info(f"❌ API key {api_key[:10]}... is NOT working")

if __name__ == "__main__":
    main()
