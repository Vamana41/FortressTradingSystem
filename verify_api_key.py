#!/usr/bin/env python3
"""Verify OpenAlgo API key storage and connection."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))

from fortress.utils.api_key_manager import SecureAPIKeyManager

def main():
    """Verify API key storage and test connection."""
    manager = SecureAPIKeyManager()

    # Get the stored API key
    api_key = manager.get_api_key('openalgo')

    if api_key:
        print(f"✅ API key found: {api_key[:10]}...")

        # Test connection
        print("Testing connection to OpenAlgo...")
        is_valid = manager.validate_api_key('openalgo')

        if is_valid:
            print("✅ API key is valid and OpenAlgo connection successful!")
            return 0
        else:
            print("❌ API key is invalid or OpenAlgo connection failed")
            return 1
    else:
        print("❌ No OpenAlgo API key found in secure storage")
        print("Please run the storage command first:")
        print("python -c \"from fortress.utils.api_key_manager import SecureAPIKeyManager; manager = SecureAPIKeyManager(); manager.store_api_key('openalgo', 'YOUR_API_KEY')\"")
        return 1

if __name__ == "__main__":
    sys.exit(main())
