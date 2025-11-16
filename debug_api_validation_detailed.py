#!/usr/bin/env python3
"""
Detailed debug script to trace API key validation in OpenAlgo API.
"""

import os
import sys
import requests
import json

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import verify_api_key, PEPPER
from utils.logging import get_logger

logger = get_logger(__name__)

def debug_api_request():
    """Debug the actual API request process."""
    
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    
    print("🔍 Debugging API Key Validation Process")
    print("=" * 60)
    print(f"API Key: {api_key[:20]}...")
    print(f"PEPPER: {PEPPER}")
    
    # Test direct verification
    print(f"\n1. Testing direct verification...")
    user_id = verify_api_key(api_key)
    print(f"Direct verification result: {user_id}")
    
    # Test API request
    print(f"\n2. Testing API request...")
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    data = {
        "apikey": api_key
    }
    
    try:
        response = requests.post(
            "http://localhost:5000/api/v1/ping", 
            headers=headers, 
            json=data, 
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 403:
            print(f"\n3. Analyzing 403 error...")
            
            # Let's manually trace what happens in the API
            from database.auth_db import get_auth_token_broker
            
            print(f"Testing get_auth_token_broker with our key...")
            auth_token, broker = get_auth_token_broker(api_key)
            print(f"Auth token: {auth_token}")
            print(f"Broker: {broker}")
            
            if auth_token is None:
                print(f"❌ API key verification failed in get_auth_token_broker")
            else:
                print(f"✅ API key verification succeeded!")
                
    except Exception as e:
        print(f"Request error: {e}")

def test_with_different_headers():
    """Test with different header formats."""
    
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    
    print(f"\n{'='*60}")
    print("Testing different header formats...")
    
    # Test different header formats
    header_variations = [
        {"api-key": api_key},
        {"x-api-key": api_key},
        {"Authorization": f"Bearer {api_key}"},
        {"apikey": api_key},
        {"API-KEY": api_key},
    ]
    
    data = {"apikey": api_key}
    
    for i, headers in enumerate(header_variations, 1):
        print(f"\nTest {i}: {list(headers.keys())[0]}")
        
        try:
            response = requests.post(
                "http://localhost:5000/api/v1/ping", 
                headers=headers, 
                json=data, 
                timeout=5
            )
            
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
            else:
                print(f"  Response: {response.text[:100]}")
                
        except Exception as e:
            print(f"  Error: {e}")

def test_direct_service_call():
    """Test calling the service function directly."""
    
    print(f"\n{'='*60}")
    print("Testing direct service call...")
    
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    
    from services.ping_service import get_ping
    
    try:
        success, response_data, status_code = get_ping(api_key=api_key)
        
        print(f"Direct service call results:")
        print(f"  Success: {success}")
        print(f"  Status Code: {status_code}")
        print(f"  Response: {json.dumps(response_data, indent=2)}")
        
    except Exception as e:
        print(f"Direct service call error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function."""
    debug_api_request()
    test_with_different_headers()
    test_direct_service_call()

if __name__ == "__main__":
    main()