#!/usr/bin/env python3
"""
Quick OpenAlgo API Key Retrieval
Simple script to get API key from OpenAlgo web interface
"""

import asyncio
import sys
from pathlib import Path

# Add fortress to path
sys.path.insert(0, str(Path(__file__).parent / "fortress" / "src"))

from fortress.utils.openalgo_api_manager import OpenAlgoAPIManager

async def quick_get_api_key():
    """Quick API key retrieval"""
    print("🚀 Quick OpenAlgo API Key Retrieval")
    print("=" * 40)
    
    # Use default localhost:5000
    base_url = "http://localhost:5000"
    
    print(f"Connecting to OpenAlgo at {base_url}")
    print("\n⚠️  IMPORTANT: Make sure you have:")
    print("   1. Started OpenAlgo server (python openalgo/app.py)")
    print("   2. Created your OpenAlgo account at http://localhost:5000")
    print("   3. Logged in and generated an API key in the dashboard")
    print("\n💡 If you haven't done these steps, please do them first!")
    
    username = input("\nEnter your OpenAlgo username: ").strip()
    password = input("Enter your OpenAlgo password: ").strip()
    
    if not username or not password:
        print("❌ Username and password are required!")
        return
        
    print(f"\n🔍 Getting API key from {base_url}...")
    
    try:
        async with OpenAlgoAPIManager(base_url) as manager:
            api_key = await manager.get_api_key_from_dashboard(username, password)
            
            if api_key:
                print(f"\n✅ SUCCESS! API Key retrieved:")
                print(f"🔐 Full API Key: {api_key}")
                print(f"📋 Partial view: {api_key[:8]}...{api_key[-8:]}")
                
                # Save to secure storage
                from fortress.utils.api_key_manager import SecureAPIKeyManager
                secure_manager = SecureAPIKeyManager()
                secure_manager.store_api_key("openalgo", api_key)
                print("\n💾 API key saved to secure storage!")
                
                # Test the key
                print("\n🧪 Testing API key...")
                if await manager.test_api_key(api_key):
                    print("✅ API key is valid and working!")
                    
                    print("\n🎯 Next steps:")
                    print("1. Restart Fortress Trading System to use the new API key")
                    print("2. Or set OPENALGO_USERNAME and OPENALGO_PASSWORD for automatic updates")
                    print("3. Test the integration with: python test_openalgo_api.py")
                    
                else:
                    print("⚠️  API key test failed - check OpenAlgo configuration")
                    
                return api_key
            else:
                print("\n❌ Failed to retrieve API key")
                print("\n🔧 Troubleshooting:")
                print("1. Check if OpenAlgo server is running: curl http://localhost:5000")
                print("2. Verify your username/password are correct")
                print("3. Make sure you've generated an API key in the OpenAlgo dashboard")
                print("4. Check OpenAlgo logs for any errors")
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n🔧 Make sure OpenAlgo server is running and accessible")

if __name__ == "__main__":
    try:
        asyncio.run(quick_get_api_key())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")