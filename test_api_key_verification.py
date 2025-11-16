#!/usr/bin/env python3
"""
Debug script to test API key verification in OpenAlgo database.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import verify_api_key
from utils.logging import get_logger

logger = get_logger(__name__)

def test_api_key_verification():
    """Test API key verification."""
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"

    print(f"Testing API key verification for: {api_key[:20]}...")

    try:
        user_id = verify_api_key(api_key)

        if user_id:
            print(f"✅ API key verified successfully!")
            print(f"   User ID: {user_id}")
            return True
        else:
            print(f"❌ API key verification failed!")
            return False

    except Exception as e:
        print(f"❌ Error during API key verification: {e}")
        return False

def main():
    """Main function."""
    print("Testing API key verification...")

    if test_api_key_verification():
        print("\n✅ API key verification test passed!")
    else:
        print("\n❌ API key verification test failed!")

if __name__ == "__main__":
    main()
