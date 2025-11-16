#!/usr/bin/env python3
"""
AmiBroker Data Access Script via OpenAlgo
This script provides real-time and historical data access for AmiBroker
using your OpenAlgo API key and Fyers broker integration.
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time

class AmiBrokerDataFeed:
    """Data feed for AmiBroker via OpenAlgo"""

    def __init__(self, api_key="471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"):
        """Initialize with your OpenAlgo API key"""
        self.api_key = api_key
        self.base_url = "http://localhost:5000/api/v1"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def get_last_price(self, symbol, exchange="NSE"):
        """Get last traded price for AmiBroker"""
        try:
            response = requests.get(
                f"{self.base_url}/quotes",
                headers=self.headers,
                params={'symbol': symbol, 'exchange': exchange},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'symbol': symbol,
                    'last': float(data.get('last_price', 0)),
                    'bid': float(data.get('bid_price', 0)),
                    'ask': float(data.get('ask_price', 0)),
                    'volume': int(data.get('volume', 0)),
                    'timestamp': data.get('timestamp', datetime.now().isoformat())
                }
            else:
                print(f"Error getting quotes for {symbol}: {response.status_code}")
                return None

        except Exception as e:
            print(f"Exception getting quotes for {symbol}: {e}")
            return None

    def get_ohlc_data(self, symbol, timeframe=1, days=30, exchange="NSE"):
        """Get OHLC data for AmiBroker"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

            response = requests.get(
                f"{self.base_url}/history",
                headers=self.headers,
                params={
                    'symbol': symbol,
                    'exchange': exchange,
                    'interval': str(timeframe),
                    'from': from_date.strftime("%Y-%m-%d"),
                    'to': to_date.strftime("%Y-%m-%d")
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                candles = data.get('data', [])

                # Convert to DataFrame for easy processing
                if candles:
                    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                    return df
                return pd.DataFrame()
            else:
                print(f"Error getting historical data for {symbol}: {response.status_code}")
                return None

        except Exception as e:
            print(f"Exception getting historical data for {symbol}: {e}")
            return None

    def get_multiple_quotes(self, symbols, exchange="NSE"):
        """Get quotes for multiple symbols (batch request)"""
        quotes = {}
        for symbol in symbols:
            quote = self.get_last_price(symbol, exchange)
            if quote:
                quotes[symbol] = quote
            time.sleep(0.1)  # Small delay to avoid rate limiting
        return quotes

    def format_for_amibroker(self, symbol, timeframe=1, days=30):
        """Format data specifically for AmiBroker import"""
        df = self.get_ohlc_data(symbol, timeframe, days)
        if df is not None and not df.empty:
            # AmiBroker expects specific column names and format
            df_amibroker = df.copy()
            df_amibroker['DateTime'] = df_amibroker['timestamp'].dt.strftime('%Y%m%d %H:%M:%S')
            df_amibroker = df_amibroker[['DateTime', 'open', 'high', 'low', 'close', 'volume']]
            df_amibroker.columns = ['Date/Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            return df_amibroker
        return None

    def get_market_depth(self, symbol, exchange="NSE"):
        """Get market depth (Level 2) data"""
        try:
            response = requests.get(
                f"{self.base_url}/depth",
                headers=self.headers,
                params={'symbol': symbol, 'exchange': exchange},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            print(f"Exception getting market depth for {symbol}: {e}")
            return None

    def get_funds_info(self):
        """Get account funds information"""
        try:
            response = requests.get(f"{self.base_url}/funds", headers=self.headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            print(f"Exception getting funds: {e}")
            return None

    def get_holdings_info(self):
        """Get current holdings"""
        try:
            response = requests.get(f"{self.base_url}/holdings", headers=self.headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            print(f"Exception getting holdings: {e}")
            return None

def save_data_for_amibroker(feed, symbol, timeframe=15, days=30):
    """Save data in AmiBroker compatible format"""
    print(f"\\n📊 Getting data for {symbol}...")

    # Get historical data
    df = feed.get_ohlc_data(symbol, timeframe=timeframe, days=days)
    if df is not None and not df.empty:
        # Format for AmiBroker
        df_amibroker = df.copy()
        df_amibroker['DateTime'] = df_amibroker['timestamp'].dt.strftime('%Y%m%d %H:%M:%S')
        df_amibroker = df_amibroker[['DateTime', 'open', 'high', 'low', 'close', 'volume']]
        df_amibroker.columns = ['Date/Time', 'Open', 'High', 'Low', 'Close', 'Volume']

        # Save to CSV
        filename = f"{symbol}_{timeframe}min.csv"
        df_amibroker.to_csv(filename, index=False)
        print(f"💾 Saved {len(df_amibroker)} records to {filename}")

        # Also save real-time quote
        quote = feed.get_last_price(symbol)
        if quote:
            print(f"📈 Current LTP: ₹{quote['last']}, Volume: {quote['volume']}")

        return filename
    else:
        print(f"❌ Could not get data for {symbol}")
        return None

# Example usage and testing
if __name__ == "__main__":
    print("🎯 AmiBroker Data Feed - Test Script")
    print("=" * 50)
    print("This script connects to OpenAlgo to get Fyers data for AmiBroker")

    # Initialize data feed
    feed = AmiBrokerDataFeed()

    # Test connection first
    print("\\n🔍 Testing connection to OpenAlgo...")
    funds = feed.get_funds_info()
    if funds:
        print("✅ Connected to OpenAlgo successfully!")
        if 'available_margin' in funds:
            print(f"💰 Available margin: ₹{funds['available_margin']}")
    else:
        print("⚠️  Could not connect to OpenAlgo")
        print("Please ensure:")
        print("1. OpenAlgo is running on http://localhost:5000")
        print("2. Your API key is correct")
        print("3. Fyers broker is configured in OpenAlgo")
        exit(1)

    # Test symbols (NSE indices and stocks)
    test_symbols = [
        ("NIFTY50", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("RELIANCE", "NSE"),
        ("TCS", "NSE")
    ]

    print("\\n📈 Testing real-time quotes...")
    for symbol, exchange in test_symbols:
        quote = feed.get_last_price(symbol, exchange)
        if quote:
            print(f"{symbol}: LTP ₹{quote['last']}, Bid: ₹{quote['bid']}, Ask: ₹{quote['ask']}, Volume: {quote['volume']}")
        else:
            print(f"{symbol}: Failed to get quote")
        time.sleep(0.2)  # Small delay

    # Test historical data and save for AmiBroker
    print("\\n📊 Testing historical data for AmiBroker...")

    # Save NIFTY data for AmiBroker
    symbol = "NIFTY50"
    timeframe = 15  # 15-minute candles
    days = 7  # Last 7 days

    filename = save_data_for_amibroker(feed, symbol, timeframe, days)

    if filename:
        print(f"\\n✅ Sample data saved to {filename}")
        print("You can now:")
        print("1. Import this CSV file into AmiBroker")
        print("2. Use the AmiBrokerDataFeed class in your scripts")
        print("3. Access real-time data for live trading")

    # Show how to use in other scripts
    print("\\n📚 Example usage in your Python scripts:")
    print("```python")
    print("from amibroker_data_feed import AmiBrokerDataFeed")
    print("")
    print("# Initialize feed")
    print("feed = AmiBrokerDataFeed()")
    print("")
    print("# Get real-time data")
    print("quote = feed.get_last_price('NIFTY50')")
    print("print(f'NIFTY LTP: ₹{quote[\"last\"]}')")
    print("")
    print("# Get historical data")
    print("df = feed.get_ohlc_data('NIFTY50', timeframe=15, days=30)")
    print("# Process for AmiBroker...")
    print("```")

    print("\\n🎯 The script handles all authentication automatically")
    print("   through OpenAlgo, so no direct token management needed!")
    print("\\n✅ Data feed setup completed successfully!")
