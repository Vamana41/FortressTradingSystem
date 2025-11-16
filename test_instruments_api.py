#!/usr/bin/env python3
"""
Test OpenAlgo Instruments API to get all symbols from all exchanges
"""

import requests
import json

# Test the Instruments API
api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
base_url = "http://127.0.0.1:5000/api/v1"

def test_instruments_api():
    """Test getting all instruments from all exchanges"""

    print("Testing OpenAlgo Instruments API...")
    print(f"API Key: {api_key[:10]}...")
    print(f"Base URL: {base_url}")
    print()

    # Test 1: Get all instruments from all exchanges
    print("1. Getting ALL instruments from ALL exchanges...")
    try:
        response = requests.get(
            f"{base_url}/instruments",
            params={"apikey": api_key},
            timeout=30
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data.get('data', []))} instruments")

            # Show some sample instruments
            instruments = data.get('data', [])
            if instruments:
                print("\nSample instruments:")
                for i, instrument in enumerate(instruments[:10]):
                    print(f"  {i+1}. {instrument.get('exchange')}:{instrument.get('symbol')} - {instrument.get('name', 'N/A')}")

                # Show exchanges available
                exchanges = set()
                for instrument in instruments[:100]:  # Check first 100
                    exchange = instrument.get('exchange', '')
                    if exchange:
                        exchanges.add(exchange)

                print(f"\nExchanges found: {sorted(exchanges)}")

        else:
            print(f"❌ Error: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")

    print("\n" + "="*60 + "\n")

    # Test 2: Get instruments by specific exchanges
    exchanges_to_test = ["NSE", "BSE", "NFO", "MCX", "CDS"]

    for exchange in exchanges_to_test:
        print(f"2. Getting instruments from {exchange}...")
        try:
            response = requests.get(
                f"{base_url}/instruments",
                params={"apikey": api_key, "exchange": exchange},
                timeout=30
            )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                instruments = data.get('data', [])
                print(f"✅ Found {len(instruments)} instruments in {exchange}")

                # Show sample instruments from this exchange
                if instruments:
                    print(f"Sample {exchange} instruments:")
                    for i, instrument in enumerate(instruments[:5]):
                        symbol = instrument.get('symbol', 'N/A')
                        name = instrument.get('name', 'N/A')
                        instrument_type = instrument.get('instrumenttype', '')
                        print(f"  {i+1}. {symbol} - {name} ({instrument_type})")

            else:
                print(f"❌ Error: {response.text}")

        except Exception as e:
            print(f"❌ Exception: {e}")

        print()

if __name__ == "__main__":
    test_instruments_api()
