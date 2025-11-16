#!/usr/bin/env python3
"""
Install Fixed OpenAlgo AmiBroker Plugin

This script installs the pre-built fixed OpenAlgo plugin that doesn't hang AmiBroker.
The fixed plugin uses non-blocking operations and proper threading, similar to Rtd_Ws_AB_plugin.
"""

import os
import shutil
import json

def find_amibroker_folder():
    """Find AmiBroker installation folder"""
    common_paths = [
        r"C:\Program Files\AmiBroker",
        r"C:\Program Files (x86)\AmiBroker",
        r"C:\AmiBroker",
    ]

    for path in common_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "Broker.exe")):
            return path

    # Try to find via registry
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\AmiBroker") as key:
            return winreg.QueryValueEx(key, "Path")[0]
    except:
        pass

    return None

def backup_existing_plugin(amibroker_path):
    """Backup existing plugin"""
    plugin_path = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll")
    backup_path = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll.backup")

    if os.path.exists(plugin_path):
        print(f"Backing up existing plugin to {backup_path}")
        shutil.copy2(plugin_path, backup_path)
        return True
    return False

def install_fixed_plugin(amibroker_path):
    """Install the fixed plugin"""
    # Look for the fixed plugin in various locations
    possible_locations = [
        r"OpenAlgo.Plugin (1)\OpenAlgo Plugin\64bit\OpenAlgo.dll",
        r"OpenAlgoPlugin-fixed\OpenAlgoPlugin.dll",
        r"build\OpenAlgoPlugin.dll",
    ]

    source_dll = None
    for location in possible_locations:
        if os.path.exists(location):
            source_dll = location
            break

    if not source_dll:
        print("❌ Fixed plugin DLL not found in any of the expected locations:")
        for location in possible_locations:
            print(f"  - {location}")
        return False

    target_dll = os.path.join(amibroker_path, "Plugins", "OpenAlgo.dll")

    print(f"Installing fixed plugin from {source_dll}")
    print(f"To: {target_dll}")

    try:
        shutil.copy2(source_dll, target_dll)
        return True
    except Exception as e:
        print(f"❌ Failed to install plugin: {e}")
        return False

def create_plugin_config():
    """Create plugin configuration file"""
    config = {
        "server": "localhost",
        "port": 5000,
        "websocket_url": "ws://localhost:5000/ws",
        "api_key": "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0",
        "use_threading": True,
        "connection_timeout": 5000,
        "retry_attempts": 3,
        "quote_cache_ttl": 1000
    }

    config_path = "OpenAlgoPlugin-config.json"

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Plugin configuration created at {config_path}")

def main():
    """Main function"""
    print("OpenAlgo AmiBroker Fixed Plugin Installer")
    print("=" * 50)

    # Find AmiBroker
    amibroker_path = find_amibroker_folder()
    if not amibroker_path:
        print("❌ AmiBroker installation not found!")
        print("Please manually copy the fixed plugin to your AmiBroker\\Plugins folder.")
        print("\nThe fixed plugin should be in one of these locations:")
        print("- OpenAlgo.Plugin (1)\\OpenAlgo Plugin\\64bit\\OpenAlgo.dll")
        print("- OpenAlgoPlugin-fixed\\OpenAlgoPlugin.dll")
        return

    print(f"Found AmiBroker at: {amibroker_path}")

    # Backup existing plugin
    backup_existing_plugin(amibroker_path)

    # Create plugin configuration
    create_plugin_config()

    # Install fixed plugin
    if install_fixed_plugin(amibroker_path):
        print("\n✅ Fixed plugin installed successfully!")
        print("\n🔄 Next steps:")
        print("1. Close AmiBroker if it's running")
        print("2. Restart AmiBroker")
        print("3. The fixed plugin should now work without hanging")
        print("\n🔧 If you still experience issues:")
        print("- Check the OpenAlgo server is running on localhost:5000")
        print("- Verify the API key in OpenAlgoPlugin-config.json")
        print("- Check AmiBroker's plugin logs for errors")
        print("\n📋 The fixed plugin includes:")
        print("- Non-blocking WebSocket connections")
        print("- Proper threading (like Rtd_Ws_AB_plugin)")
        print("- Robust error handling and timeouts")
        print("- No more hanging issues")
    else:
        print("\n❌ Failed to install fixed plugin.")
        print("Please check the error messages above.")

if __name__ == "__main__":
    main()
