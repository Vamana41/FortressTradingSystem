#!/usr/bin/env python3
"""
Utility script to register an API key in the OpenAlgo database.
This is needed for external systems like Fortress to authenticate with OpenAlgo.
"""

import os
import sys
import hashlib

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from argon2 import PasswordHasher
from database.auth_db import init_db, ApiKeys, db_session
from utils.logging import get_logger

logger = get_logger(__name__)
ph = PasswordHasher()

def register_api_key(api_key, user_id="fortress_system"):
    """
    Register an API key in the OpenAlgo database.

    Args:
        api_key: The API key to register
        user_id: The user ID to associate with the API key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get pepper from environment
        pepper = os.getenv('API_KEY_PEPPER', 'default-pepper-change-in-production')
        peppered_key = api_key + pepper

        # Hash the API key
        api_key_hash = ph.hash(peppered_key)

        # Use global database session
        session = db_session

        # Check if API key already exists for this user
        existing_key = session.query(ApiKeys).filter_by(user_id=user_id).first()
        if existing_key:
            logger.info(f"Updating existing API key for user: {user_id}")
            existing_key.api_key_hash = api_key_hash
            existing_key.api_key_encrypted = api_key  # Store encrypted version
        else:
            logger.info(f"Creating new API key for user: {user_id}")
            new_key = ApiKeys(
                user_id=user_id,
                api_key_hash=api_key_hash,
                api_key_encrypted=api_key
            )
            session.add(new_key)

        session.commit()

        logger.info(f"API key registered successfully for user: {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error registering API key: {e}")
        return False

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) != 2:
        print("Usage: python register_api_key.py <api_key>")
        print("Example: python register_api_key.py 89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0")
        sys.exit(1)

    api_key = sys.argv[1]

    # Initialize database
    init_db()

    # Register the API key
    if register_api_key(api_key):
        print(f"✅ API key registered successfully!")
        print(f"You can now use this API key with OpenAlgo endpoints.")
        print(f"Test with: curl -X POST -H 'Content-Type: application/json' -d '{{\"apikey\":\"{api_key}\"}}' http://localhost:5000/api/v1/ping")
    else:
        print("❌ Failed to register API key")
        sys.exit(1)

if __name__ == "__main__":
    main()
