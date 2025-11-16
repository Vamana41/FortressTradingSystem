#!/usr/bin/env python3
"""
Fortress Trading System - Status Check Script
Checks the status of all integrated components
"""

import requests
import json
import sys
from pathlib import Path

def check_openalgo_server():
    """Check if OpenAlgo server is running"""
    try:
        response = requests.get("http://localhost:5000/auth/login", timeout=5)
        if response.status_code == 200:
            return True, "OpenAlgo server is running"
        else:
            return False, f"OpenAlgo server returned status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"OpenAlgo server not accessible: {e}"

def check_openalgo_endpoints():
    """Check OpenAlgo API endpoints"""
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    headers = {"Content-Type": "application/json"}
    
    # Test endpoints that should work with POST and basic data
    endpoints = [
        {
            "path": "/api/v1/ping",
            "data": {"apikey": api_key}
        },
        {
            "path": "/api/v1/quotes", 
            "data": {"apikey": api_key, "symbol": "NIFTY", "exchange": "NSE"}
        }
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.post(f"http://localhost:5000{endpoint['path']}", 
                                   json=endpoint['data'], headers=headers, timeout=5)
            results.append({
                "endpoint": endpoint['path'],
                "status": response.status_code,
                "accessible": response.status_code in [200, 400],  # 400 is OK (invalid key)
                "response": response.text[:100] if response.text else ""
            })
        except requests.exceptions.RequestException as e:
            results.append({
                "endpoint": endpoint['path'],
                "status": "error",
                "accessible": False,
                "error": str(e)
            })
    
    return results

def check_fyers_connection():
    """Check Fyers connection through OpenAlgo"""
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    
    try:
        # Test with a simple quote request
        data = {
            "apikey": api_key,
            "symbol": "NIFTY",
            "exchange": "NSE"
        }
        
        response = requests.post("http://localhost:5000/api/v1/quotes", 
                               json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return True, "Fyers connection active", result.get("data")
            else:
                return False, f"Fyers connection failed: {result.get('message', 'Unknown error')}", None
        else:
            return False, f"Fyers connection returned status {response.status_code}", None
            
    except requests.exceptions.RequestException as e:
        return False, f"Fyers connection error: {e}", None

def check_fortress_integration():
    """Check Fortress Trading System integration"""
    try:
        # Add the fortress src to Python path
        import sys
        sys.path.insert(0, 'c:\\Users\\Admin\\Documents\\FortressTradingSystem\\fortress\\src')
        
        # Import and test the secure API key manager
        from fortress.utils.api_key_manager import SecureAPIKeyManager
        
        manager = SecureAPIKeyManager()
        api_key = manager.get_api_key("openalgo")
        
        if api_key:
            return True, f"Fortress API key stored securely (length: {len(api_key)})", api_key[:8] + "..."
        else:
            return False, "Fortress API key not found in secure storage", None
            
    except Exception as e:
        return False, f"Fortress integration error: {e}", None

def main():
    """Main status check function"""
    print("🔍 Fortress Trading System - Status Check")
    print("=" * 50)
    
    # Check OpenAlgo server
    print("\n1. Checking OpenAlgo Server...")
    server_ok, server_msg = check_openalgo_server()
    print(f"   {'✅' if server_ok else '❌'} {server_msg}")
    
    if not server_ok:
        print("\n⚠️  OpenAlgo server is not running. Please start it first.")
        return False
    
    # Check OpenAlgo API endpoints
    print("\n2. Checking OpenAlgo API Endpoints...")
    api_results = check_openalgo_endpoints()
    api_accessible = False
    
    for result in api_results:
        status_icon = "✅" if result["accessible"] else "❌"
        print(f"   {status_icon} {result['endpoint']}: {result['status']}")
        if result["accessible"]:
            api_accessible = True
    
    # Check Fyers connection
    print("\n3. Checking Fyers Connection...")
    fyers_ok, fyers_msg, fyers_data = check_fyers_connection()
    print(f"   {'✅' if fyers_ok else '❌'} {fyers_msg}")
    
    if fyers_ok and fyers_data:
        print(f"   📊 Sample data: {str(fyers_data)[:100]}...")
    
    # Check Fortress integration
    print("\n4. Checking Fortress Integration...")
    try:
        fortress_ok, fortress_msg, fortress_data = check_fortress_integration()
        print(f"   {'✅' if fortress_ok else '❌'} {fortress_msg}")
    except Exception as e:
        print(f"   ❌ Fortress integration error: {e}")
        fortress_ok = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 STATUS SUMMARY:")
    print(f"   OpenAlgo Server: {'✅ Running' if server_ok else '❌ Down'}")
    print(f"   API Access: {'✅ Available' if api_accessible else '❌ Limited'}")
    print(f"   Fyers Connection: {'✅ Active' if fyers_ok else '❌ Issues'}")
    print(f"   Fortress Integration: {'✅ Configured' if fortress_ok else '❌ Issues'}")
    
    # Overall status
    all_ok = server_ok and api_accessible and fyers_ok and fortress_ok
    print(f"\n🎯 Overall Status: {'✅ SYSTEM READY' if all_ok else '⚠️  ISSUES DETECTED'}")
    
    if all_ok:
        print("\n🚀 The system is ready for trading operations!")
        print("   - Open AmiBroker and configure the plugin")
        print("   - Run the ATM scanner formula")
        print("   - Monitor the Fortress dashboard")
    else:
        print("\n🔧 Please address the issues above before proceeding.")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)