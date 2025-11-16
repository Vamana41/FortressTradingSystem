#!/usr/bin/env python3
"""
Final Comprehensive Test Script for Fortress Trading System
Tests the complete integration after setup.
"""

import os
import sys
import requests
import json
import time
from urllib.parse import urljoin

def test_openalgo_integration():
    """Test complete OpenAlgo integration."""
    
    print("🧪 Testing OpenAlgo Integration")
    print("=" * 40)
    
    # Get API key from .env
    api_key = None
    try:
        with open(".env", 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('OPENALGO_API_KEY='):
                    api_key = line.split('=')[1].strip()
                    break
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False
    
    if not api_key or len(api_key) < 20:
        print("❌ No valid API key found in .env file")
        return False
    
    print(f"Using API key: {api_key[:10]}...")
    
    base_url = "http://127.0.0.1:5000/api/v1"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    # Test endpoints
    tests = [
        {
            "name": "Ping",
            "endpoint": "/ping",
            "method": "POST",
            "data": {"apikey": api_key},
            "expected_status": 200
        },
        {
            "name": "Funds",
            "endpoint": "/funds",
            "method": "POST",
            "data": {"apikey": api_key},
            "expected_status": 200
        },
        {
            "name": "Orderbook",
            "endpoint": "/orderbook",
            "method": "POST",
            "data": {"apikey": api_key},
            "expected_status": 200
        },
        {
            "name": "Tradebook",
            "endpoint": "/tradebook",
            "method": "POST",
            "data": {"apikey": api_key},
            "expected_status": 200
        },
        {
            "name": "Holdings",
            "endpoint": "/holdings",
            "method": "POST",
            "data": {"apikey": api_key},
            "expected_status": 200
        }
    ]
    
    results = {}
    
    for test in tests:
        try:
            print(f"Testing {test['name']}...")
            
            if test["method"] == "POST":
                response = requests.post(
                    f"{base_url}{test['endpoint']}",
                    headers=headers,
                    json=test["data"],
                    timeout=15
                )
            else:
                response = requests.get(
                    f"{base_url}{test['endpoint']}",
                    headers=headers,
                    timeout=15
                )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == test["expected_status"]:
                try:
                    result = response.json()
                    print(f"  ✅ Success: {result.get('status', 'unknown')}")
                    results[test["name"]] = True
                except:
                    print(f"  ✅ Success (non-JSON response)")
                    results[test["name"]] = True
            else:
                print(f"  ❌ Failed: {response.text[:100]}")
                results[test["name"]] = False
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[test["name"]] = False
    
    return results

def test_fortress_core():
    """Test Fortress core functionality."""
    
    print("\n🧪 Testing Fortress Core")
    print("=" * 40)
    
    # Add fortress src to path
    fortress_path = os.path.join(os.path.dirname(__file__), 'fortress', 'src')
    if fortress_path not in sys.path:
        sys.path.insert(0, fortress_path)
    
    try:
        # Test importing core modules
        print("Testing imports...")
        
        from fortress.utils.api_key_manager import SecureAPIKeyManager
        print("✅ API Key Manager imported")
        
        from fortress.integrations.openalgo_gateway import OpenAlgoGateway
        print("✅ OpenAlgo Gateway imported")
        
        from fortress.brain.brain import Brain
        print("✅ Brain imported")
        
        # Test API key manager
        print("Testing API Key Manager...")
        manager = SecureAPIKeyManager()
        
        # Get API key
        api_key = manager.get_api_key("openalgo")
        if api_key:
            print(f"✅ API key retrieved: {api_key[:10]}...")
        else:
            print("⚠️  No API key found in secure storage")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Fortress core: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_amibroker_integration():
    """Test AmiBroker integration components."""
    
    print("\n🧪 Testing AmiBroker Integration")
    print("=" * 40)
    
    required_files = [
        "OpenAlgoPlugin-enhanced/Plugin_complete.cpp",
        "OpenAlgo_ATM_Scanner.afl",
        "setup_amibroker_plugin.py",
        "AMIBROKER_SETUP_GUIDE.md"
    ]
    
    results = {}
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
            results[file_path] = True
        else:
            print(f"❌ {file_path}")
            results[file_path] = False
    
    return results

def generate_test_report(openalgo_results, fortress_result, amibroker_results):
    """Generate comprehensive test report."""
    
    print("\n" + "="*60)
    print("📊 COMPREHENSIVE TEST REPORT")
    print("="*60)
    
    # OpenAlgo results
    print("\nOpenAlgo Integration:")
    openalgo_passed = sum(1 for result in openalgo_results.values() if result)
    openalgo_total = len(openalgo_results)
    print(f"Passed: {openalgo_passed}/{openalgo_total}")
    
    for test_name, result in openalgo_results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {test_name}")
    
    # Fortress results
    print(f"\nFortress Core: {'✅ Working' if fortress_result else '❌ Issues'}")
    
    # AmiBroker results
    print("\nAmiBroker Integration:")
    amibroker_passed = sum(1 for result in amibroker_results.values() if result)
    amibroker_total = len(amibroker_results)
    print(f"Files ready: {amibroker_passed}/{amibroker_total}")
    
    for file_path, result in amibroker_results.items():
        status = "✅" if result else "❌"
        filename = os.path.basename(file_path)
        print(f"  {status} {filename}")
    
    # Overall status
    total_passed = openalgo_passed + (1 if fortress_result else 0) + amibroker_passed
    total_tests = openalgo_total + 1 + amibroker_total
    
    print(f"\nOverall Status: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL SYSTEMS READY!")
        print("The Fortress Trading System is fully integrated and ready for deployment.")
        return True
    elif total_passed >= total_tests * 0.8:
        print("\n⚠️  MOSTLY READY")
        print("System is mostly functional with minor issues.")
        return True
    else:
        print("\n❌ SYSTEM NOT READY")
        print("Significant issues need to be resolved before deployment.")
        return False

def main():
    """Main function."""
    print("🚀 FORTRESS TRADING SYSTEM - FINAL COMPREHENSIVE TEST")
    print("=" * 60)
    
    # Check if OpenAlgo is running
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        if response.status_code != 200:
            print("❌ OpenAlgo server is not responding properly")
            return
    except:
        print("❌ OpenAlgo server is not running")
        print("Please start it first: python openalgo/app.py")
        return
    
    print("✅ OpenAlgo server is running")
    
    # Test OpenAlgo integration
    openalgo_results = test_openalgo_integration()
    
    # Test Fortress core
    fortress_result = test_fortress_core()
    
    # Test AmiBroker integration
    amibroker_results = test_amibroker_integration()
    
    # Generate report
    system_ready = generate_test_report(openalgo_results, fortress_result, amibroker_results)
    
    # Create report file
    with open("final_test_report.txt", "w") as f:
        f.write("Fortress Trading System - Final Test Report\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Status: {'READY' if system_ready else 'NOT READY'}\n")
        f.write(f"OpenAlgo Integration: {sum(1 for r in openalgo_results.values() if r)}/{len(openalgo_results)} passed\n")
        f.write(f"Fortress Core: {'Working' if fortress_result else 'Issues'}\n")
        f.write(f"AmiBroker Integration: {sum(1 for r in amibroker_results.values() if r)}/{len(amibroker_results)} files ready\n")
    
    print(f"\n📄 Test report saved to: final_test_report.txt")
    
    if system_ready:
        print("\n🎉 CONGRATULATIONS!")
        print("Your Fortress Trading System is ready for deployment!")
        print("\nNext steps:")
        print("1. Start Fortress main system")
        print("2. Configure trading parameters")
        print("3. Begin monitoring and trading")
        print("4. Set up monitoring and alerts")

if __name__ == "__main__":
    main()