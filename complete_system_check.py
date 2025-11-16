#!/usr/bin/env python3
"""
Complete System Status Checker for Fortress Trading System
Verifies all components are working correctly before deployment.
"""

import os
import sys
import requests
import subprocess
import time
from urllib.parse import urljoin

def check_openalgo_server():
    """Check if OpenAlgo server is running."""
    print("🔍 Checking OpenAlgo Server...")
    
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        if response.status_code == 200:
            print("✅ OpenAlgo server is running")
            return True
        else:
            print(f"❌ OpenAlgo server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ OpenAlgo server is not accessible")
        return False
    except Exception as e:
        print(f"❌ Error checking OpenAlgo: {e}")
        return False

def check_openalgo_api_endpoints():
    """Check OpenAlgo API endpoints."""
    print("\n🔍 Checking OpenAlgo API Endpoints...")
    
    base_url = "http://127.0.0.1:5000/api/v1"
    
    # Test basic connectivity
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ API documentation accessible")
        else:
            print(f"⚠️  API documentation status: {response.status_code}")
    except Exception as e:
        print(f"⚠️  API documentation error: {e}")
    
    # Test ping endpoint without auth
    try:
        response = requests.post(f"{base_url}/ping", json={"apikey": "test"}, timeout=5)
        if response.status_code == 403:
            print("✅ API authentication is working")
            return True
        else:
            print(f"❌ Unexpected API response: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API endpoint error: {e}")
        return False

def check_fortress_configuration():
    """Check Fortress configuration."""
    print("\n🔍 Checking Fortress Configuration...")
    
    # Check if .env file exists
    env_file = ".env"
    if not os.path.exists(env_file):
        print("❌ .env file not found")
        return False
    
    # Check for OpenAlgo API key
    try:
        with open(env_file, 'r') as f:
            content = f.read()
            if 'OPENALGO_API_KEY=' in content:
                # Extract API key
                lines = content.split('\n')
                for line in lines:
                    if line.startswith('OPENALGO_API_KEY='):
                        api_key = line.split('=')[1].strip()
                        if api_key and len(api_key) > 10:
                            print(f"✅ OpenAlgo API key configured: {api_key[:10]}...")
                            return True
                        else:
                            print("❌ Invalid API key in .env file")
                            return False
            else:
                print("❌ OpenAlgo API key not found in .env file")
                return False
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False

def check_amibroker_integration():
    """Check AmiBroker integration components."""
    print("\n🔍 Checking AmiBroker Integration...")
    
    # Check if enhanced plugin exists
    plugin_files = [
        "OpenAlgoPlugin-enhanced/OpenAlgoPlugin.dll",
        "OpenAlgoPlugin-enhanced/Plugin_complete.cpp"
    ]
    
    plugin_found = False
    for plugin_file in plugin_files:
        if os.path.exists(plugin_file):
            print(f"✅ Enhanced plugin found: {plugin_file}")
            plugin_found = True
            break
    
    if not plugin_found:
        print("⚠️  Enhanced AmiBroker plugin not found")
    
    # Check AFL files
    afl_files = [
        "OpenAlgo_ATM_Scanner.afl",
        "setup_amibroker_plugin.py"
    ]
    
    afl_found = 0
    for afl_file in afl_files:
        if os.path.exists(afl_file):
            print(f"✅ AFL file found: {afl_file}")
            afl_found += 1
    
    if afl_found == len(afl_files):
        print("✅ All AmiBroker integration files ready")
        return True
    else:
        print(f"⚠️  {afl_found}/{len(afl_files)} AmiBroker files found")
        return False

def check_fortress_core_files():
    """Check Fortress core files."""
    print("\n🔍 Checking Fortress Core Files...")
    
    core_files = [
        "fortress/src/fortress/main.py",
        "fortress/src/fortress/dashboard/main.py",
        "fortress/src/fortress/brain/brain.py",
        "fortress/src/fortress/integrations/openalgo_gateway.py",
        "fortress/src/fortress/utils/api_key_manager.py"
    ]
    
    missing_files = []
    for file_path in core_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if not missing_files:
        print("✅ All core Fortress files present")
        return True
    else:
        print(f"❌ {len(missing_files)} core files missing")
        return False

def test_api_key_integration():
    """Test API key integration with actual endpoints."""
    print("\n🔍 Testing API Key Integration...")
    
    # Get API key from .env
    try:
        with open(".env", 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('OPENALGO_API_KEY='):
                    api_key = line.split('=')[1].strip()
                    break
            else:
                print("❌ No API key found in .env")
                return False
    except Exception as e:
        print(f"❌ Error reading API key: {e}")
        return False
    
    if not api_key or len(api_key) < 10:
        print("❌ Invalid API key")
        return False
    
    base_url = "http://127.0.0.1:5000/api/v1"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    # Test ping endpoint
    try:
        data = {"apikey": api_key}
        response = requests.post(f"{base_url}/ping", headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API key integration working")
            print(f"Response: {result.get('data', {}).get('message', 'Unknown')}")
            return True
        elif response.status_code == 403:
            print("❌ API key authentication failed")
            print("This means you need to create a new account and get a valid API key")
            return False
        else:
            print(f"❌ API integration test failed: {response.status_code}")
            print(f"Response: {response.text[:100]}")
            return False
            
    except Exception as e:
        print(f"❌ API integration error: {e}")
        return False

def generate_status_report():
    """Generate a comprehensive status report."""
    
    print("\n" + "="*60)
    print("📊 FORTRESS TRADING SYSTEM STATUS REPORT")
    print("="*60)
    
    checks = [
        ("OpenAlgo Server", check_openalgo_server()),
        ("OpenAlgo API Endpoints", check_openalgo_api_endpoints()),
        ("Fortress Configuration", check_fortress_configuration()),
        ("AmiBroker Integration", check_amibroker_integration()),
        ("Fortress Core Files", check_fortress_core_files()),
        ("API Key Integration", test_api_key_integration())
    ]
    
    passed = 0
    total = len(checks)
    
    print("\nCheck Results:")
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {check_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall Status: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 SYSTEM READY FOR DEPLOYMENT!")
        print("\nNext steps:")
        print("1. Test with real trading symbols")
        print("2. Start Fortress main system")
        print("3. Monitor system performance")
        print("4. Begin trading operations")
    elif passed >= total * 0.8:
        print("⚠️  SYSTEM MOSTLY READY")
        print("\nAddress the failed checks before deployment")
    else:
        print("❌ SYSTEM NOT READY")
        print("\nSignificant issues need to be resolved")
    
    return passed, total

def main():
    """Main function."""
    print("🔧 Fortress Trading System - Complete Status Check")
    print("=" * 60)
    print("Checking all system components before deployment...")
    
    passed, total = generate_status_report()
    
    # Create status file
    with open("system_status_report.txt", "w") as f:
        f.write(f"Fortress Trading System Status Report\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Status: {passed}/{total} checks passed\n")
        
        if passed == total:
            f.write("Status: READY FOR DEPLOYMENT\n")
        elif passed >= total * 0.8:
            f.write("Status: MOSTLY READY\n")
        else:
            f.write("Status: NOT READY\n")
    
    print(f"\n📄 Status report saved to: system_status_report.txt")

if __name__ == "__main__":
    main()