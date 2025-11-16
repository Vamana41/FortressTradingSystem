#!/usr/bin/env python3
"""
Debug script to check which users have valid auth tokens and brokers.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import ApiKeys, Auth, verify_api_key
from database.user_db import User

def check_user_credentials():
    """Check which users have valid auth tokens and brokers."""
    
    print("🔍 Checking User Credentials and Auth Tokens")
    print("=" * 60)
    
    # Get all users
    users = User.query.all()
    print(f"Found {len(users)} user(s):")
    
    for user in users:
        print(f"\n👤 User: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Admin: {user.is_admin}")
        
        # Check if user has API keys
        api_keys = ApiKeys.query.filter_by(user_id=user.username).all()
        print(f"  API Keys: {len(api_keys)}")
        
        for api_key in api_keys:
            print(f"    - Created: {api_key.created_at}")
            print(f"      Has Hash: {'Yes' if api_key.api_key_hash else 'No'}")
        
        # Check if user has auth tokens
        auth_tokens = Auth.query.filter_by(name=user.username).all()
        print(f"  Auth Tokens: {len(auth_tokens)}")
        
        for auth in auth_tokens:
            print(f"    - Broker: {auth.broker}")
            print(f"      Is Revoked: {auth.is_revoked}")
            print(f"      Has Auth Token: {'Yes' if auth.auth else 'No'}")
            print(f"      Has Feed Token: {'Yes' if auth.feed_token else 'No'}")

def test_existing_users():
    """Test API keys for users that have auth tokens."""
    
    print(f"\n{'='*60}")
    print("Testing API keys for users with auth tokens...")
    
    # Get users with auth tokens
    users_with_auth = []
    users = User.query.all()
    
    for user in users:
        auth_tokens = Auth.query.filter_by(name=user.username).all()
        for auth in auth_tokens:
            if not auth.is_revoked and auth.auth:
                users_with_auth.append((user.username, auth.broker))
                break
    
    print(f"Found {len(users_with_auth)} users with valid auth tokens:")
    
    for username, broker in users_with_auth:
        print(f"\n🧪 Testing {username} ({broker}):")
        
        # Find API key for this user
        api_key_obj = ApiKeys.query.filter_by(user_id=username).first()
        
        if api_key_obj:
            # Test verification
            result = verify_api_key("89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0")
            print(f"  API key verification: {'✅ Valid' if result == username else '❌ Invalid'}")
            
            # Test auth token retrieval
            from database.auth_db import get_auth_token_broker
            auth_token, broker_name = get_auth_token_broker("89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0")
            print(f"  Auth token retrieval: {'✅ Success' if auth_token else '❌ Failed'}")
            print(f"  Broker: {broker_name}")
        else:
            print(f"  ❌ No API key found for this user")

def find_working_api_key():
    """Find an API key that actually works with the API."""
    
    print(f"\n{'='*60}")
    print("Finding working API key...")
    
    # Get all API keys
    api_keys = ApiKeys.query.all()
    
    for api_key_obj in api_keys:
        print(f"\nTesting API key for user: {api_key_obj.user_id}")
        
        # Check if this user has auth tokens
        auth_tokens = Auth.query.filter_by(name=api_key_obj.user_id).all()
        valid_auth = None
        
        for auth in auth_tokens:
            if not auth.is_revoked and auth.auth:
                valid_auth = auth
                break
        
        if valid_auth:
            print(f"  ✅ User has valid auth token for broker: {valid_auth.broker}")
            print(f"  ✅ This should be a working API key!")
            
            # We can't extract the actual API key plaintext, but we know this user has credentials
            return api_key_obj.user_id
        else:
            print(f"  ❌ User has no valid auth tokens")
    
    return None

def main():
    """Main function."""
    check_user_credentials()
    test_existing_users()
    working_user = find_working_api_key()
    
    if working_user:
        print(f"\n🎯 SOLUTION: Use API key for user '{working_user}'")
        print(f"This user has valid broker credentials and should work with the API.")
    else:
        print(f"\n⚠️  No working API key found!")
        print(f"You need to set up broker credentials for one of the users through the OpenAlgo web interface.")

if __name__ == "__main__":
    main()