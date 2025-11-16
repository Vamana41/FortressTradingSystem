#!/usr/bin/env python3
"""
Final Integration Script - Complete Fortress Trading System Setup
This script will guide you through the final steps to get everything working.
"""

import os
import sys
import requests
import time

def check_openalgo_status():
    """Check if OpenAlgo is running."""
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        return response.status_code == 200
    except:
        return False

def create_account_guide():
    """Guide through creating a new OpenAlgo account."""
    
    print("🎯 STEP 1: Create OpenAlgo Account")
    print("=" * 50)
    print("Since we performed a database reset, you need to create a new account.")
    print()
    print("1. Open your browser and go to: http://127.0.0.1:5000")
    print("2. You should see a registration/login page")
    print("3. Click on 'Create Account' or 'Register'")
    print("4. Fill in the registration form:")
    print("   - Username: Choose any username you like")
    print("   - Email: Your email address")
    print("   - Password: Choose a strong password")
    print("5. Complete the registration process")
    print()
    
    input("Press Enter after you've created your account and can see the dashboard...")
    return True

def configure_broker_guide():
    """Guide through broker configuration."""
    
    print("\n🎯 STEP 2: Configure Fyers Broker")
    print("=" * 50)
    print("Now you need to configure your Fyers broker credentials.")
    print()
    print("1. In the OpenAlgo dashboard, look for 'Broker' or 'Settings'")
    print("2. Find 'Broker Configuration' or similar option")
    print("3. Select 'Fyers' as your broker")
    print("4. Enter your Fyers credentials:")
    print("   - App ID: Your Fyers App ID")
    print("   - App Secret: Your Fyers App Secret")
    print("   - Redirect URL: http://localhost:5000/callback")
    print("5. Save the configuration")
    print("6. You may be redirected to Fyers for authorization")
    print("7. Complete the OAuth flow")
    print()
    
    input("Press Enter after you've configured Fyers and can see broker status as connected...")
    return True

def generate_api_key_guide():
    """Guide through API key generation."""
    
    print("\n🎯 STEP 3: Generate API Key")
    print("=" * 50)
    print("Now you need to generate an API key for Fortress to use.")
    print()
    print("1. In OpenAlgo dashboard, look for 'API Keys' or 'API Management'")
    print("2. Click 'Generate New API Key' or similar")
    print("3. Give it a name like 'fortress_trading'")
    print("4. Copy the generated API key (it's a long string)")
    print("5. Keep it safe - you'll need it in the next step")
    print()
    
    api_key = input("Enter your new API key: ").strip()
    
    if not api_key or len(api_key) < 20:
        print("❌ Invalid API key. Please try again.")
        return None
    
    return api_key

def test_api_key(api_key):
    """Test the API key."""
    
    print("\n🧪 Testing API Key...")
    print("=" * 30)
    
    base_url = "http://127.0.0.1:5000/api/v1"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    data = {"apikey": api_key}
    
    try:
        response = requests.post(f"{base_url}/ping", headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API key is working!")
            print(f"Response: {result.get('data', {}).get('message', 'pong')}")
            return True
        else:
            print(f"❌ API key test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False

def update_fortress_config(api_key):
    """Update Fortress configuration with new API key."""
    
    print("\n🎯 STEP 4: Update Fortress Configuration")
    print("=" * 50)
    
    env_file = ".env"
    
    if not os.path.exists(env_file):
        print(f"❌ .env file not found at {env_file}")
        return False
    
    try:
        # Read current .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add OPENALGO_API_KEY
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith('OPENALGO_API_KEY='):
                new_lines.append(f'OPENALGO_API_KEY={api_key}\n')
                updated = True
                print(f"Updated existing API key")
            else:
                new_lines.append(line)
        
        # If not found, add it
        if not updated:
            new_lines.append(f'OPENALGO_API_KEY={api_key}\n')
            print(f"Added new API key")
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
        
        print(f"✅ Successfully updated {env_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def final_verification():
    """Perform final verification."""
    
    print("\n🎯 FINAL VERIFICATION")
    print("=" * 50)
    
    # Test OpenAlgo server
    if check_openalgo_status():
        print("✅ OpenAlgo server is running")
    else:
        print("❌ OpenAlgo server is not running")
        return False
    
    # Check .env file
    try:
        with open(".env", 'r') as f:
            content = f.read()
            if 'OPENALGO_API_KEY=' in content:
                for line in content.split('\n'):
                    if line.startswith('OPENALGO_API_KEY='):
                        api_key = line.split('=')[1].strip()
                        if api_key and len(api_key) > 20:
                            print(f"✅ Fortress configured with new API key")
                            break
                else:
                    print("❌ Invalid API key in .env")
                    return False
            else:
                print("❌ API key not found in .env")
                return False
    except Exception as e:
        print(f"❌ Error reading .env: {e}")
        return False
    
    print("\n🎉 INTEGRATION COMPLETE!")
    print("\nYour Fortress Trading System is now ready:")
    print("✅ OpenAlgo server running with fresh database")
    print("✅ New account created with Fyers broker configured")
    print("✅ New API key generated and configured in Fortress")
    print("✅ All systems integrated and ready")
    
    print("\nNext steps:")
    print("1. Test the complete workflow")
    print("2. Configure AmiBroker if needed")
    print("3. Start trading operations")
    print("4. Monitor system performance")
    
    return True

def main():
    """Main function."""
    print("🚀 FORTRESS TRADING SYSTEM - FINAL INTEGRATION")
    print("=" * 60)
    
    # Check if OpenAlgo is running
    if not check_openalgo_status():
        print("❌ OpenAlgo server is not running!")
        print("Please start it first: python openalgo/app.py")
        return
    
    print("✅ OpenAlgo server is running")
    
    # Step 1: Create account
    if not create_account_guide():
        return
    
    # Step 2: Configure broker
    if not configure_broker_guide():
        return
    
    # Step 3: Generate API key
    api_key = None
    while not api_key:
        api_key = generate_api_key_guide()
        if not api_key:
            print("Please try again...")
    
    # Step 4: Test API key
    if not test_api_key(api_key):
        print("❌ API key test failed. Please check your configuration.")
        return
    
    # Step 5: Update Fortress
    if not update_fortress_config(api_key):
        print("❌ Failed to update Fortress configuration")
        return
    
    # Final verification
    final_verification()

if __name__ == "__main__":
    main()