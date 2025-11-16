#!/usr/bin/env python3
"""
Extract Fyers tokens from OpenAlgo for use in Fortress/AmiBroker
This script retrieves the stored Fyers authentication and feed tokens
"""

import os
import sys
import requests
import json
from pathlib import Path

# Add OpenAlgo to path
sys.path.append(str(Path(__file__).parent / 'openalgo'))

from openalgo.database.auth_db import get_auth_token_broker, verify_api_key
from openalgo.utils.logging import get_logger

logger = get_logger(__name__)

def extract_fyers_tokens(api_key):
    """
    Extract Fyers tokens from OpenAlgo database
    
    Args:
        api_key: Your OpenAlgo API key
        
    Returns:
        dict: Contains access_token, feed_token, and broker info
    """
    try:
        # Verify the API key first
        user_id = verify_api_key(api_key)
        if not user_id:
            print("❌ Invalid API key")
            return None
            
        print(f"✅ API key verified for user: {user_id}")
        
        # Get both auth token and feed token
        access_token, feed_token, broker = get_auth_token_broker(api_key, include_feed_token=True)
        
        if not access_token:
            print("❌ No authentication token found")
            return None
            
        if broker != 'fyers':
            print(f"⚠️  Warning: Current broker is '{broker}', not Fyers")
            
        print(f"✅ Successfully retrieved tokens for broker: {broker}")
        
        # Create token data structure
        token_data = {
            'broker': broker,
            'user_id': user_id,
            'access_token': access_token,
            'feed_token': feed_token,
            'token_type': 'Bearer',
            'status': 'active'
        }
        
        # Show token summary (truncated for security)
        print(f"📊 Access Token: {access_token[:20]}...{access_token[-10:]}")
        if feed_token:
            print(f"📊 Feed Token: {feed_token[:20]}...{feed_token[-10:]}")
        else:
            print("⚠️  No feed token found (may be normal for some brokers)")
            
        return token_data
        
    except Exception as e:
        print(f"❌ Error extracting tokens: {e}")
        return None

def save_tokens_for_fortress(token_data):
    """Save tokens in a format that Fortress can use"""
    if not token_data:
        return
        
    # Create tokens directory in Fortress
    fortress_dir = Path(__file__).parent / 'fortress' / 'config'
    fortress_dir.mkdir(exist_ok=True)
    
    # Save tokens as JSON
    tokens_file = fortress_dir / 'fyers_tokens.json'
    
    with open(tokens_file, 'w') as f:
        json.dump(token_data, f, indent=2)
        
    print(f"💾 Tokens saved to: {tokens_file}")
    
    # Also create a Python config file for easy import
    config_file = fortress_dir / 'fyers_config.py'
    
    config_content = f'''# Fyers configuration for Fortress
# Generated automatically from OpenAlgo tokens

FYERS_CONFIG = {{
    'broker': '{token_data['broker']}',
    'user_id': '{token_data['user_id']}',
    'access_token': '{token_data['access_token']}',
    'feed_token': '{token_data.get('feed_token', '')}',
    'token_type': 'Bearer',
    'api_base_url': 'https://api-t1.fyers.in/api/v3',
    'data_base_url': 'https://api-t1.fyers.in/data',
    'websocket_url': 'wss://websocket.fyers.in/v3'
}}

# Headers for API calls
FYERS_HEADERS = {{
    'Authorization': f"{{FYERS_CONFIG['token_type']}} {{FYERS_CONFIG['access_token']}}",
    'Content-Type': 'application/json'
}}
'''
    
    with open(config_file, 'w') as f:
        f.write(config_content)
        
    print(f"⚙️  Config saved to: {config_file}")

def main():
    """Main function to extract and save Fyers tokens"""
    
    # Your OpenAlgo API key
    api_key = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
    
    print("🔍 Extracting Fyers tokens from OpenAlgo...")
    print(f"Using API key: {api_key[:10]}...{api_key[-10:]}")
    
    # Extract tokens
    tokens = extract_fyers_tokens(api_key)
    
    if tokens:
        print("\n✅ Token extraction successful!")
        save_tokens_for_fortress(tokens)
        
        print("\n🎯 Next steps for your Python scripts:")
        print("1. Import the config: from fortress.config.fyers_config import FYERS_CONFIG, FYERS_HEADERS")
        print("2. Use the tokens for API calls:")
        print("   - Access Token for trading APIs")
        print("   - Feed Token for WebSocket/real-time data")
        
        print("\n📚 Example usage:")
        print("```python")
        print("import requests")
        print("from fortress.config.fyers_config import FYERS_HEADERS")
        print("")
        print("# Get user profile")
        print("response = requests.get('https://api-t1.fyers.in/api/v3/profile', headers=FYERS_HEADERS)")
        print("print(response.json())")
        print("```")
        
    else:
        print("\n❌ Token extraction failed")
        print("Please ensure:")
        print("1. OpenAlgo is running")
        print("2. You have successfully logged into Fyers through OpenAlgo")
        print("3. Your API key is correct")

if __name__ == "__main__":
    main()