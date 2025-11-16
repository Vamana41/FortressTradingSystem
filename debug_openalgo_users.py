#!/usr/bin/env python3
"""
Debug script to check users and auth in OpenAlgo database.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import init_db, ApiKeys, Auth
from database.user_db import User  # Import User model
from utils.logging import get_logger

logger = get_logger(__name__)

def check_users():
    """Check all users in the database."""
    try:
        # Query all users
        users = User.query.all()

        print(f"Found {len(users)} user(s) in database:")

        for i, user in enumerate(users):
            print(f"\nUser {i+1}:")
            print(f"  Username: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  Created: {user.created_at}")
            print(f"  Active: {user.is_active}")

        return len(users) > 0

    except Exception as e:
        logger.error(f"Error checking users: {e}")
        return False

def check_api_keys():
    """Check all API keys in the database."""
    try:
        # Query all API keys
        api_keys = ApiKeys.query.all()

        print(f"\nFound {len(api_keys)} API key(s) in database:")

        for i, key in enumerate(api_keys):
            print(f"\nAPI Key {i+1}:")
            print(f"  User ID: {key.user_id}")
            print(f"  Created: {key.created_at}")

        return len(api_keys) > 0

    except Exception as e:
        logger.error(f"Error checking API keys: {e}")
        return False

def check_auth_tokens():
    """Check all auth tokens in the database."""
    try:
        # Query all auth tokens
        auth_tokens = Auth.query.all()

        print(f"\nFound {len(auth_tokens)} auth token(s) in database:")

        for i, auth in enumerate(auth_tokens):
            print(f"\nAuth Token {i+1}:")
            print(f"  Name: {auth.name}")
            print(f"  Broker: {auth.broker}")
            print(f"  User ID: {auth.user_id}")
            print(f"  Is Revoked: {auth.is_revoked}")

        return len(auth_tokens) > 0

    except Exception as e:
        logger.error(f"Error checking auth tokens: {e}")
        return False

def main():
    """Main function."""
    print("Checking OpenAlgo database structure...")

    # Initialize database
    init_db()

    # Check users
    has_users = check_users()
    has_api_keys = check_api_keys()
    has_auth_tokens = check_auth_tokens()

    if has_users and has_api_keys and has_auth_tokens:
        print("\n✅ All database components found!")
    else:
        print(f"\n❌ Missing components - Users: {has_users}, API Keys: {has_api_keys}, Auth Tokens: {has_auth_tokens}")

if __name__ == "__main__":
    main()
