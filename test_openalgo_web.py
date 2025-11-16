#!/usr/bin/env python3
"""
Simple test to check if OpenAlgo web interface is accessible
"""

import requests
import webbrowser
import time

def test_web_interface():
    """Test if the OpenAlgo web interface is accessible"""

    base_url = "http://localhost:5000"

    print("Testing OpenAlgo web interface...")
    print(f"URL: {base_url}")

    try:
        # Test main page
        response = requests.get(base_url, timeout=10)

        if response.status_code == 200:
            print("✅ Web interface is accessible!")
            print(f"Status: {response.status_code}")
            print(f"Content length: {len(response.text)} bytes")

            # Check if it contains expected content
            if "OpenAlgo" in response.text or "Login" in response.text:
                print("✅ Contains expected OpenAlgo content")
                return True
            else:
                print("⚠️  Page loaded but may not be OpenAlgo interface")
                return False

        else:
            print(f"❌ Web interface returned status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to web interface: {e}")
        return False

def check_api_docs():
    """Check if API documentation is available"""

    api_docs_url = "http://localhost:5000/api/v1/"

    print(f"\nTesting API documentation...")
    print(f"URL: {api_docs_url}")

    try:
        response = requests.get(api_docs_url, timeout=10)

        if response.status_code == 200:
            print("✅ API documentation is accessible!")
            return True
        else:
            print(f"⚠️  API documentation returned status {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to API documentation: {e}")
        return False

if __name__ == "__main__":
    print("OpenAlgo Web Interface Test")
    print("=" * 40)

    web_success = test_web_interface()
    api_success = check_api_docs()

    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)

    if web_success:
        print("✅ Web interface: WORKING")
        print("\n🌐 You can now access OpenAlgo at: http://localhost:5000")
        print("   - Login or create an account")
        print("   - Configure your Fyers broker connection")
        print("   - Generate your API key")
    else:
        print("❌ Web interface: FAILED")

    if api_success:
        print("✅ API documentation: WORKING")
    else:
        print("⚠️  API documentation: NOT ACCESSIBLE")

    if web_success:
        print("\n🎉 OpenAlgo is ready! Please:")
        print("1. Open http://localhost:5000 in your browser")
        print("2. Login/create account")
        print("3. Get your API key from the dashboard")
        print("4. Share it with me for Fortress integration")
