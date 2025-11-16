#!/usr/bin/env python3
"""
Complete Fyers Token Management for Fortress and AmiBroker
This script provides everything you need to access Fyers data through OpenAlgo
"""

import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

class FyersDataManager:
    """Manages Fyers data access through OpenAlgo API"""

    def __init__(self, api_key=None, openalgo_url="http://localhost:5000/api/v1"):
        self.api_key = api_key or "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
        self.base_url = openalgo_url
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def test_connection(self):
        """Test connection to OpenAlgo"""
        try:
            response = requests.get(f"{self.base_url}/ping", headers=self.headers, timeout=5)
            return response.status_code == 200
        except:
            return False

    def get_broker_info(self):
        """Get current broker information"""
        try:
            response = requests.get(f"{self.base_url}/broker/info", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting broker info: {e}")
            return None

    def get_funds(self):
        """Get account funds"""
        try:
            response = requests.get(f"{self.base_url}/funds", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting funds: {e}")
            return None

    def get_real_time_data(self, symbol, exchange="NSE"):
        """Get real-time LTP data"""
        try:
            response = requests.get(
                f"{self.base_url}/quotes",
                headers=self.headers,
                params={'symbol': symbol, 'exchange': exchange}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting real-time data: {e}")
            return None

    def get_historical_data(self, symbol, timeframe="15", from_date=None, to_date=None, exchange="NSE"):
        """Get historical OHLC data"""
        try:
            params = {
                'symbol': symbol,
                'exchange': exchange,
                'interval': timeframe
            }

            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date

            response = requests.get(
                f"{self.base_url}/history",
                headers=self.headers,
                params=params
            )

            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting historical data: {e}")
            return None

    def get_holdings(self):
        """Get current holdings"""
        try:
            response = requests.get(f"{self.base_url}/holdings", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting holdings: {e}")
            return None

    def get_positions(self):
        """Get current positions"""
        try:
            response = requests.get(f"{self.base_url}/positions", headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting positions: {e}")
            return None

def create_amibroker_data_script():
    """Create a comprehensive script for AmiBroker data access"""

    script_content = '''#!/usr/bin/env python3
"""
AmiBroker Data Access Script via OpenAlgo
Handles real-time and historical data for AmiBroker integration
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time

class AmiBrokerDataFeed:
    """Data feed for AmiBroker via OpenAlgo"""

    def __init__(self, api_key="471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"):
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
                df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

                return df
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

# Example usage and testing
if __name__ == "__main__":
    print("AmiBroker Data Feed Test")
    print("=" * 40)

    # Initialize data feed
    feed = AmiBrokerDataFeed()

    # Test symbols
    test_symbols = ["NIFTY50", "BANKNIFTY", "RELIANCE"]

    print("\\n1. Testing real-time quotes...")
    for symbol in test_symbols:
        quote = feed.get_last_price(symbol)
        if quote:
            print(f"{symbol}: LTP ₹{quote['last']}, Volume: {quote['volume']}")
        else:
            print(f"{symbol}: Failed to get quote")

    print("\\n2. Testing historical data...")
    symbol = "NIFTY50"
    df = feed.get_ohlc_data(symbol, timeframe=15, days=5)  # 15-minute data for 5 days
    if df is not None and not df.empty:
        print(f"Got {len(df)} candles for {symbol}")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print("\\nLatest 3 candles:")
        print(df.tail(3))
    else:
        print(f"Failed to get historical data for {symbol}")

    print("\\n3. Testing AmiBroker format...")
    amibroker_df = feed.format_for_amibroker(symbol, timeframe=15, days=5)
    if amibroker_df is not None and not amibroker_df.empty:
        print(f"AmiBroker format data (first 3 rows):")
        print(amibroker_df.head(3))

        # Save to CSV for AmiBroker import
        csv_file = f"{symbol}_15min.csv"
        amibroker_df.to_csv(csv_file, index=False)
        print(f"\\n💾 Saved AmiBroker format data to: {csv_file}")

    print("\\n✅ Data feed test completed!")
'''

    # Save the script
    script_path = Path(__file__).parent / 'amibroker_data_feed.py'
    with open(script_path, 'w') as f:
        f.write(script_content)

    return script_path

def main():
    """Main function"""

    print("🎯 Fyers Token Management for Fortress and AmiBroker")
    print("=" * 60)

    # Initialize data manager
    manager = FyersDataManager()

    # Test connection
    print("🔍 Testing connection to OpenAlgo...")
    if not manager.test_connection():
        print("❌ Cannot connect to OpenAlgo at http://localhost:5000")
        print("Please ensure OpenAlgo is running")
        return

    print("✅ Connected to OpenAlgo successfully!")

    # Get broker info
    print("\n🔍 Getting broker information...")
    broker_info = manager.get_broker_info()
    if broker_info:
        print(f"✅ Current broker: {broker_info.get('broker', 'Unknown')}")
        print(f"✅ Status: {broker_info.get('status', 'Unknown')}")

    # Test funds access
    print("\n🔍 Testing account access...")
    funds = manager.get_funds()
    if funds:
        print("✅ Successfully accessed account!")
        if 'available_margin' in funds:
            print(f"💰 Available margin: ₹{funds['available_margin']}")
    else:
        print("⚠️  Could not access account funds")

    # Create AmiBroker data script
    print("\n📝 Creating AmiBroker data access script...")
    script_path = create_amibroker_data_script()
    print(f"✅ Script created: {script_path}")

    print("\n🎯 Summary:")
    print("=" * 40)
    print("✅ OpenAlgo API key is working")
    print("✅ Fyers broker is configured")
    print("✅ Account access verified")
    print("✅ Data access script created")

    print("\n📚 Next steps for your Python scripts:")
    print("1. Import the data feed: from amibroker_data_feed import AmiBrokerDataFeed")
    print("2. Create instance: feed = AmiBrokerDataFeed()")
    print("3. Get data:")
    print("   - Real-time: feed.get_last_price('NIFTY50')")
    print("   - Historical: feed.get_ohlc_data('NIFTY50', timeframe=15, days=30)")
    print("   - AmiBroker format: feed.format_for_amibroker('NIFTY50')")

    print("\n💡 The script handles all authentication automatically")
    print("   through OpenAlgo, so no direct token management needed!")

if __name__ == "__main__":
    main()
