#!/usr/bin/env python3
"""
Debug script to check API key registration in OpenAlgo database.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import init_db, ApiKeys, db_session
from utils.logging import get_logger

logger = get_logger(__name__)

def check_api_keys():
    """Check all registered API keys in the database."""
    try:
        # Query all API keys
        api_keys = db_session.query(ApiKeys).all()

        print(f"Found {len(api_keys)} API key(s) in database:")

        for i, key in enumerate(api_keys):
            print(f"\nAPI Key {i+1}:")
            print(f"  User ID: {key.user_id}")
            print(f"  Created: {key.created_at}")
            print(f"  Hash: {key.api_key_hash[:50]}...")
            print(f"  Encrypted: {key.api_key_encrypted[:50]}...")

        return len(api_keys) > 0

    except Exception as e:
        logger.error(f"Error checking API keys: {e}")
        return False

def main():
    """Main function."""
    print("Checking API keys in OpenAlgo database...")

    # Initialize database
    init_db()

    # Check API keys
    if check_api_keys():
        print("\n✅ API keys found in database!")
    else:
        print("\n❌ No API keys found in database!")

if __name__ == "__main__":
    main()
