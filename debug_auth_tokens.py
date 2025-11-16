#!/usr/bin/env python3
"""
Debug script to check auth tokens in OpenAlgo database.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import init_db, Auth
from utils.logging import get_logger

logger = get_logger(__name__)

def check_auth_tokens():
    """Check all auth tokens in the database."""
    try:
        # Query all auth tokens
        auth_tokens = Auth.query.all()
        
        print(f"Found {len(auth_tokens)} auth token(s) in database:")
        
        for i, auth in enumerate(auth_tokens):
            print(f"\nAuth Token {i+1}:")
            print(f"  Name: {auth.name}")
            print(f"  Broker: {auth.broker}")
            print(f"  Auth: {auth.auth[:50]}...")
            print(f"  Feed Token: {auth.feed_token[:50] if auth.feed_token else 'None'}")
            print(f"  Created: {auth.created_at}")
            print(f"  Is Revoked: {auth.is_revoked}")
        
        return len(auth_tokens) > 0
        
    except Exception as e:
        logger.error(f"Error checking auth tokens: {e}")
        return False

def main():
    """Main function."""
    print("Checking auth tokens in OpenAlgo database...")
    
    # Initialize database
    init_db()
    
    # Check auth tokens
    if check_auth_tokens():
        print("\n✅ Auth tokens found in database!")
    else:
        print("\n❌ No auth tokens found in database!")

if __name__ == "__main__":
    main()