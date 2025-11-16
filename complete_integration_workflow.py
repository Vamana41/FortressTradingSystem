#!/usr/bin/env python3
"""
Complete Fortress Trading System Integration Workflow
This script guides through the entire setup process.
"""

import os
import sys
import time
import requests

def check_openalgo_status():
    """Check if OpenAlgo is running."""
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        return response.status_code == 200
    except:
        return False

def guide_account_creation():
    """Guide through account creation process."""
    
    print("\n🎯 Step 1: Create OpenAlgo Account")
    print("-" * 40)
    print("1. Open your browser and go to: http://127.0.0.1:5000")
    print("2. Click on 'Create Account' or 'Register'")
    print("3. Fill in your details:")
    print("   - Username: Choose a username (e.g., fortress_user)")
    print("   - Email: Your email address")
    print("   - Password: Choose a strong password")
    print("4. Complete the registration process")
    
    input("\nPress Enter after you've created your account...")

def guide_broker_configuration():
    """Guide through broker configuration."""
    
    print("\n🎯 Step 2: Configure Fyers Broker")
    print("-" * 40)
    print("1. Log in to your OpenAlgo account")
    print("2. Navigate to 'Broker Configuration' or 'Settings'")
    print("3. Select 'Fyers' as your broker")
    print("4. Enter your Fyers credentials:")
    print("   - App ID: Your Fyers app ID")
    print("   - App Secret: Your Fyers app secret")
    print("   - Redirect URL: Usually http://localhost:5000/callback")
    print("5. Save the configuration")
    print("6. Complete the OAuth flow if prompted")
    
    input("\nPress Enter after you've configured Fyers...")

def guide_api_key_generation():
    """Guide through API key generation."""
    
    print("\n🎯 Step 3: Generate API Key")
    print("-" * 40)
    print("1. In OpenAlgo dashboard, look for 'API Keys' or 'API Management'")
    print("2. Click 'Generate New API Key'")
    print("3. Give it a name (e.g., 'fortress_integration')")
    print("4. Copy the generated API key")
    print("5. Keep it safe - you'll need it for Fortress")
    
    api_key = input("\nEnter your new API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Please try again.")
        return None
    
    return api_key

def test_api_key(api_key):
    """Test the API key with basic endpoints."""
    
    print("\n🧪 Testing API Key")
    print("-" * 40)
    
    base_url = "http://127.0.0.1:5000/api/v1"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    data = {"apikey": api_key}
    
    try:
        # Test ping endpoint
        response = requests.post(f"{base_url}/ping", headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API key is working!")
            print(f"Response: {result}")
            return True
        else:
            print(f"❌ API key test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return False

def update_fortress_configuration(api_key):
    """Update Fortress configuration with the new API key."""
    
    print("\n🎯 Step 4: Update Fortress Configuration")
    print("-" * 40)
    
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
            else:
                new_lines.append(line)
        
        # If not found, add it
        if not updated:
            new_lines.append(f'OPENALGO_API_KEY={api_key}\n')
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
        
        print(f"✅ Updated {env_file} with new API key")
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def guide_amibroker_setup():
    """Guide through AmiBroker setup."""
    
    print("\n🎯 Step 5: AmiBroker Integration")
    print("-" * 40)
    print("1. Open AmiBroker")
    print("2. Go to File → Database Settings")
    print("3. Configure your data source")
    print("4. Install the OpenAlgo plugin if not already installed")
    print("   - Plugin should be in: AmiBroker/Plugins/OpenAlgo.dll")
    print("5. Restart AmiBroker")
    print("6. The enhanced plugin should now be active")
    
    input("\nPress Enter after AmiBroker setup is complete...")

def final_verification():
    """Perform final verification."""
    
    print("\n🎯 Final Verification")
    print("-" * 40)
    
    # Check if OpenAlgo is running
    if check_openalgo_status():
        print("✅ OpenAlgo server is running")
    else:
        print("❌ OpenAlgo server is not running")
        return False
    
    # Check .env file
    if os.path.exists(".env"):
        print("✅ Fortress configuration file exists")
    else:
        print("❌ Fortress configuration file missing")
        return False
    
    print("\n🎉 Integration setup complete!")
    print("\nNext steps:")
    print("1. Test the complete workflow")
    print("2. Monitor for any issues")
    print("3. Run system checks")
    print("4. Begin trading operations")
    
    return True

def main():
    """Main function."""
    print("🚀 Fortress Trading System Integration Workflow")
    print("=" * 60)
    
    # Check if OpenAlgo is running
    if not check_openalgo_status():
        print("❌ OpenAlgo server is not running!")
        print("Please start it first: python openalgo/app.py")
        return
    
    print("✅ OpenAlgo server is running")
    
    # Step 1: Account creation
    guide_account_creation()
    
    # Step 2: Broker configuration
    guide_broker_configuration()
    
    # Step 3: API key generation
    api_key = None
    while not api_key:
        api_key = guide_api_key_generation()
    
    # Step 4: Test API key
    if not test_api_key(api_key):
        print("❌ API key test failed. Please check your configuration.")
        return
    
    # Step 5: Update Fortress configuration
    if not update_fortress_configuration(api_key):
        print("❌ Failed to update Fortress configuration")
        return
    
    # Step 6: AmiBroker setup
    guide_amibroker_setup()
    
    # Final verification
    final_verification()

if __name__ == "__main__":
    main()