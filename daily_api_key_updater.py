#!/usr/bin/env python3
"""
Daily API Key Updater for Fortress Trading System
Run this script every day after you get your new OpenAlgo API key
"""

import os
import sys
from pathlib import Path

def update_api_key_manually():
    """Interactive script to update your OpenAlgo API key"""

    print("🔄 Fortress Trading System - Daily API Key Updater")
    print("=" * 55)
    print("\n📋 Instructions:")
    print("1. Login to OpenAlgo manually")
    print("2. Login to your broker (Fyers) through OpenAlgo")
    print("3. Copy the API key from OpenAlgo dashboard")
    print("4. Paste it here when prompted")

    # Get the new API key from user
    print("\n🔑 Please paste your OpenAlgo API key:")
    api_key = input("> ").strip()

    if not api_key:
        print("❌ No API key provided. Exiting.")
        return False

    if len(api_key) < 50:
        print("❌ API key seems too short. Please check and try again.")
        return False

    print(f"\n✅ API key received: {api_key[:10]}...{api_key[-10:]}")

    # Save to a simple text file that Fortress can read
    config_dir = Path.home() / ".fortress"
    config_dir.mkdir(exist_ok=True)

    api_key_file = config_dir / "openalgo_api_key.txt"

    try:
        # Save the API key
        with open(api_key_file, 'w') as f:
            f.write(api_key)

        print(f"💾 API key saved to: {api_key_file}")

        # Also create a simple Python config file
        config_py = config_dir / "daily_config.py"
        with open(config_py, 'w') as f:
            f.write(f"# Daily API key for Fortress\n")
            f.write(f"OPENALGO_API_KEY = '{api_key}'\n")
            f.write(f"# Generated on: {os.path.basename(__file__)}\n")

        print(f"💾 Python config saved to: {config_py}")

        # Create environment file
        env_file = config_dir / ".env"
        with open(env_file, 'w') as f:
            f.write(f"OPENALGO_API_KEY={api_key}\n")
            f.write(f"OPENALGO_BASE_URL=http://localhost:5000/api/v1\n")

        print(f"💾 Environment file saved to: {env_file}")

        print("\n✅ API key updated successfully!")
        print("\n🎯 Next steps:")
        print("1. Restart Fortress Trading System if it's running")
        print("2. Or start Fortress: cd fortress && python src/fortress/main.py")

        return True

    except Exception as e:
        print(f"❌ Error saving API key: {e}")
        return False

def show_current_api_key():
    """Show the current API key if available"""
    config_dir = Path.home() / ".fortress"
    api_key_file = config_dir / "openalgo_api_key.txt"

    if api_key_file.exists():
        try:
            with open(api_key_file, 'r') as f:
                current_key = f.read().strip()
            print(f"\n📊 Current API key: {current_key[:10]}...{current_key[-10:]}")
            return current_key
        except Exception as e:
            print(f"⚠️  Could not read current API key: {e}")
            return None
    else:
        print("\n📊 No API key found. This is your first time setting up.")
        return None

def main():
    """Main function"""

    print("🏰 Fortress Trading System - Daily Setup")
    print("=" * 45)

    # Show current API key if available
    current_key = show_current_api_key()

    print("\n❓ What would you like to do?")
    print("1. Update API key (recommended daily)")
    print("2. View current API key")
    print("3. Exit")

    choice = input("\nEnter your choice (1-3): ").strip()

    if choice == "1":
        success = update_api_key_manually()
        if success:
            print("\n🚀 You can now start Fortress Trading System!")
        else:
            print("\n❌ API key update failed. Please try again.")

    elif choice == "2":
        if current_key:
            print(f"\n✅ Current API key is set and ready to use!")
        else:
            print(f"\n❌ No API key set. Please update it first.")

    elif choice == "3":
        print("\n👋 Goodbye!")

    else:
        print("\n❌ Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
