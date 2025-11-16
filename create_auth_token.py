#!/usr/bin/env python3
"""
Script to create auth token for fortress_system user in OpenAlgo database.
This is needed for the API key to work properly.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import init_db, Auth, encrypt_token, db_session
from utils.logging import get_logger

logger = get_logger(__name__)

def create_auth_token():
    """Create auth token for fortress_system user."""
    try:
        # Check if auth token already exists
        existing_auth = Auth.query.filter_by(name="fortress_system").first()
        
        if existing_auth:
            print(f"Auth token already exists for fortress_system")
            print(f"Broker: {existing_auth.broker}")
            return True
        
        # Create new auth token
        # We need to get the Fyers credentials from environment
        fyers_auth_token = os.getenv("FYERS_AUTH_TOKEN", "")
        
        if not fyers_auth_token:
            print("❌ FYERS_AUTH_TOKEN not found in environment!")
            print("Please set FYERS_AUTH_TOKEN in your .env file")
            return False
        
        # Encrypt the auth token
        encrypted_token = encrypt_token(fyers_auth_token)
        
        # Create auth object
        auth_obj = Auth(
            name="fortress_system",
            auth=encrypted_token,
            broker="fyers",
            user_id="fortress_system"
        )
        
        db_session.add(auth_obj)
        db_session.commit()
        
        print("✅ Auth token created successfully for fortress_system!")
        print(f"Broker: fyers")
        return True
        
    except Exception as e:
        logger.error(f"Error creating auth token: {e}")
        return False

def main():
    """Main function."""
    print("Creating auth token for fortress_system...")
    
    # Initialize database
    init_db()
    
    # Create auth token
    if create_auth_token():
        print("\n✅ Auth token creation completed!")
        print("You should now be able to use the API key with OpenAlgo endpoints.")
    else:
        print("\n❌ Auth token creation failed!")

if __name__ == "__main__":
    main()