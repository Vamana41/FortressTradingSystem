#!/usr/bin/env python3
"""
Debug OpenAlgo Broker Configuration

This script checks the broker configuration and login status for the admin user.
"""

import sys
import os
from pathlib import Path

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def check_broker_status():
    """Check broker configuration and login status."""
    try:
        from database.user_db import find_user_by_username
        from database.auth_db import get_auth_token_broker
        from database.auth_db import Auth
        from database import auth_db
        
        # Check admin user
        admin_user = find_user_by_username()
        if not admin_user:
            print("Admin user not found!")
            return
            
        print(f"Admin user: {admin_user.username} (ID: {admin_user.id})")
        
        # Check auth tokens
        auth_tokens = Auth.query.filter_by(name=admin_user.username).all()
        print(f"\nFound {len(auth_tokens)} auth tokens:")
        
        for auth in auth_tokens:
            print(f"\nAuth Token {auth.id}:")
            print(f"  User: {auth.name}")
            print(f"  Broker: {auth.broker}")
            print(f"  Auth Token: {auth.auth[:50]}..." if auth.auth else "None")
            print(f"  Feed Token: {auth.feed_token[:50]}..." if auth.feed_token else "None")
            print(f"  Is Revoked: {auth.is_revoked}")
            print(f"  Created: {auth.created_at}")
            
            # Test get_auth_token_broker function
            auth_token, broker = get_auth_token_broker("420ff93cf719bdcd81f5f33db189f9e9b08fa25e76c03fcfcd89762c0868efbd")
            print(f"  API Key Test - Auth Token: {auth_token[:50] if auth_token else 'None'}...")
            print(f"  API Key Test - Broker: {broker}")
            
    except Exception as e:
        print(f"Error checking broker status: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function."""
    print("OpenAlgo Broker Configuration Debug")
    print("=" * 40)
    
    check_broker_status()

if __name__ == "__main__":
    main()