#!/usr/bin/env python3
"""
Get Fyers tokens from OpenAlgo API
This script calls OpenAlgo's API to get the current broker tokens
"""

import requests
import json
import os
from pathlib import Path

def get_fyers_tokens_from_openalgo(api_key):
    """
    Get Fyers tokens from OpenAlgo API
    
    Args:
        api_key: Your OpenAlgo API key
        
    Returns:
        dict: Token information from OpenAlgo
    """
    
    # OpenAlgo API endpoints
    base_url = "http://localhost:5000/api/v1"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        print("🔍 Getting broker info from OpenAlgo...")
        
        # First, let's check what broker is currently active
        response = requests.get(f"{base_url}/broker/info", headers=headers)
        
        if response.status_code == 200:
            broker_info = response.json()
            print(f"✅ Current broker: {broker_info.get('broker', 'Unknown')}")
            print(f"✅ Broker status: {broker_info.get('status', 'Unknown')}")
        else:
            print(f"⚠️  Could not get broker info: {response.status_code}")
            print(f"Response: {response.text}")
            
        # Now let's try to get the funds/info which requires valid tokens
        print("\n🔍 Getting account info (this will show if tokens are working)...")
        
        response = requests.get(f"{base_url}/funds", headers=headers)
        
        if response.status_code == 200:
            funds_data = response.json()
            print("✅ Successfully connected to broker!")
            print(f"✅ Account status: {funds_data.get('status', 'Unknown')}")
            
            # Extract token information from headers or response
            token_info = {
                'api_key': api_key,
                'broker': broker_info.get('broker', 'fyers'),
                'status': 'connected',
                'funds_data': funds_data
            }
            
            return token_info
            
        elif response.status_code == 401:
            print("❌ API key is invalid or expired")
            return None
            
        else:
            print(f"⚠️  Could not get funds info: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Even if funds call fails, we might still have basic broker info
            if broker_info.get('broker') == 'fyers':
                return {
                    'api_key': api_key,
                    'broker': 'fyers',
                    'status': 'broker_configured',
                    'note': 'Basic broker info available, but tokens may need refresh'
                }
            
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to OpenAlgo server at localhost:5000")
        print("Please ensure OpenAlgo is running")
        return None
        
    except Exception as e:
        print(f"❌ Error getting tokens: {e}")
        return None

def create_fyers_data_script(token_info):
    """Create a Python script that can be used to get real-time and historical data"""
    
    script_content = f'''#!/usr/bin/env python3
"""
Fyers Data Access Script
Generated automatically for AmiBroker integration
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta

# Configuration from OpenAlgo
API_KEY = "{token_info['api_key']}"
BASE_URL = "http://localhost:5000/api/v1"

HEADERS = {{
    'Authorization': f'Bearer {{API_KEY}}',
    'Content-Type': 'application/json'
}}

def get_real_time_data(symbol, exchange="NSE"):
    """Get real-time LTP data for a symbol"""
    try:
        response = requests.get(
            f"{{BASE_URL}}/quotes",
            headers=HEADERS,
            params={{
                'symbol': symbol,
                'exchange': exchange
            }}
        )
        
        if response.status_code == 200:
            data = response.json()
            return {{
                'symbol': symbol,
                'ltp': data.get('last_price'),
                'bid': data.get('bid_price'),
                'ask': data.get('ask_price'),
                'volume': data.get('volume'),
                'timestamp': data.get('timestamp')
            }}
        else:
            print(f"Error getting quotes: {{response.status_code}}")
            return None
            
    except Exception as e:
        print(f"Error getting real-time data: {{e}}")
        return None

def get_historical_data(symbol, timeframe="15", from_date=None, to_date=None, exchange="NSE"):
    """Get historical OHLC data"""
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
            
        response = requests.get(
            f"{{BASE_URL}}/history",
            headers=HEADERS,
            params={{
                'symbol': symbol,
                'exchange': exchange,
                'interval': timeframe,
                'from': from_date,
                'to': to_date
            }}
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            print(f"Error getting historical data: {{response.status_code}}")
            return []
            
    except Exception as e:
        print(f"Error getting historical data: {{e}}")
        return []

def get_funds_info():
    """Get account funds information"""
    try:
        response = requests.get(f"{{BASE_URL}}/funds", headers=HEADERS)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting funds: {{response.status_code}}")
            return None
            
    except Exception as e:
        print(f"Error getting funds: {{e}}")
        return None

# Example usage for AmiBroker integration
if __name__ == "__main__":
    print("Fyers Data Access - Test Script")
    print("=" * 40)
    
    # Test real-time data
    print("\\n1. Getting real-time data for NIFTY...")
    nifty_data = get_real_time_data("NIFTY50", "NSE")
    if nifty_data:
        print(f"NIFTY LTP: {{nifty_data['ltp']}}")
    
    # Test historical data
    print("\\n2. Getting historical data...")
    hist_data = get_historical_data("NIFTY50", "15", exchange="NSE")
    if hist_data:
        print(f"Got {{len(hist_data)}} historical data points")
        if hist_data:
            print(f"Latest: {{hist_data[-1]}}")
    
    # Test funds
    print("\\n3. Getting funds info...")
    funds = get_funds_info()
    if funds:
        print(f"Available margin: {{funds.get('available_margin', 'N/A')}}")
'''
    
    # Save the script
    script_path = Path(__file__).parent / 'fyers_data_access.py'
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print(f"📝 Data access script saved to: {script_path}")
    return script_path

def main():
    """Main function"""
    
    # Your OpenAlgo API key
    api_key = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
    
    print("🔍 Getting Fyers tokens from OpenAlgo API...")
    print(f"Using API key: {api_key[:10]}...{api_key[-10:]}")
    
    # Get token info
    token_info = get_fyers_tokens_from_openalgo(api_key)
    
    if token_info:
        print("\n✅ Successfully connected to OpenAlgo with Fyers!")
        print(f"✅ Broker: {token_info.get('broker', 'Unknown')}")
        print(f"✅ Status: {token_info.get('status', 'Unknown')}")
        
        # Create data access script
        script_path = create_fyers_data_script(token_info)
        
        print("\n🎯 Next steps for your AmiBroker Python scripts:")
        print("1. Use the generated script: fyers_data_access.py")
        print("2. Import functions: from fyers_data_access import get_real_time_data, get_historical_data")
        print("3. Call functions to get data for AmiBroker")
        
        print("\n📚 Example usage in your script:")
        print("```python")
        print("# Get real-time data")
        print("nifty_ltp = get_real_time_data('NIFTY50', 'NSE')")
        print("print(f'NIFTY LTP: {{nifty_ltp[\"ltp\"]}}')")
        print("")
        print("# Get historical data for AmiBroker")
        print("hist_data = get_historical_data('NIFTY50', '15', exchange='NSE')")
        print("# Process data for AmiBroker format")
        print("```")
        
        print(f"\n💡 The script handles all token management automatically")
        print(f"   through OpenAlgo, so you don't need to manage tokens directly!")
        
    else:
        print("\n❌ Could not get tokens from OpenAlgo")
        print("Please ensure:")
        print("1. OpenAlgo is running on http://localhost:5000")
        print("2. You have successfully logged into Fyers through OpenAlgo")
        print("3. Your API key is correct")

if __name__ == "__main__":
    main()