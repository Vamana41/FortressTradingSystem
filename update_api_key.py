#!/usr/bin/env python3
"""
Update OpenAlgo API key in secure storage
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))

from fortress.utils.api_key_manager import SecureAPIKeyManager

def update_api_key():
    """Update the API key in secure storage"""

    # New API key provided by user
    new_api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"

    manager = SecureAPIKeyManager()

    # Store the new API key
    manager.store_api_key("openalgo", new_api_key)

    print(f"✅ API key updated successfully!")
    print(f"🔐 Stored securely in: {manager.keys_file}")

    # Verify it was stored correctly
    stored_key = manager.get_api_key("openalgo")
    if stored_key == new_api_key:
        print("✅ Verification: API key retrieved correctly")
    else:
        print("❌ Verification: API key mismatch!")
        return False

    return True

if __name__ == "__main__":
    success = update_api_key()
    sys.exit(0 if success else 1)
