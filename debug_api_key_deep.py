#!/usr/bin/env python3
"""
Deep Debug OpenAlgo API Key Verification

This script deeply debugs the API key verification process in OpenAlgo.
"""

import sys
import os
from pathlib import Path

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def deep_debug_api_key():
    """Deep debug API key verification."""
    try:
        from database.user_db import find_user_by_username
        from database.auth_db import get_auth_token_broker, verify_api_key
        from database.auth_db import ApiKeys, Auth
        from database import auth_db
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        import hashlib
        
        # Get admin user
        admin_user = find_user_by_username()
        if not admin_user:
            print("Admin user not found!")
            return
            
        print(f"Admin user: {admin_user.username} (ID: {admin_user.id})")
        
        # Get the API key we created
        api_key = "420ff93cf719bdcd81f5f33db189f9e9b08fa25e76c03fcfcd89762c0868efbd"
        
        print(f"\nTesting API key: {api_key}")
        
        # Test direct verification
        print("\n1. Testing direct verify_api_key function:")
        user_id = verify_api_key(api_key)
        print(f"   Result: {user_id}")
        
        # Test with pepper
        print("\n2. Testing with pepper:")
        PEPPER = os.getenv('API_KEY_PEPPER', 'default-pepper-change-in-production')
        peppered_key = api_key + PEPPER
        print(f"   Pepper: {PEPPER}")
        print(f"   Peppered key: {peppered_key[:50]}...")
        
        # Get all API keys from database
        print("\n3. Database API keys:")
        api_keys = ApiKeys.query.all()
        ph = PasswordHasher()
        
        for key_obj in api_keys:
            print(f"   Key ID: {key_obj.id}")
            print(f"   User ID: {key_obj.user_id}")
            print(f"   Hash: {key_obj.api_key_hash[:50]}...")
            
            # Try to verify against this hash
            try:
                ph.verify(key_obj.api_key_hash, peppered_key)
                print(f"   ✓ Verification successful against this key!")
                print(f"   User ID from key: {key_obj.user_id}")
                
                # Check if user exists
                user_exists = auth_db.User.query.filter_by(username=key_obj.user_id).first()
                if user_exists:
                    print(f"   ✓ User exists: {user_exists.username}")
                else:
                    print(f"   ✗ User not found: {key_obj.user_id}")
                    
            except VerifyMismatchError:
                print(f"   ✗ Verification failed against this key")
            except Exception as e:
                print(f"   ✗ Error verifying: {e}")
                
        # Test get_auth_token_broker
        print(f"\n4. Testing get_auth_token_broker function:")
        auth_token, broker = get_auth_token_broker(api_key)
        print(f"   Auth Token: {auth_token[:50] if auth_token else 'None'}")
        print(f"   Broker: {broker}")
        
        # Check auth tokens
        print(f"\n5. Auth tokens for user:")
        auth_tokens = Auth.query.filter_by(name=admin_user.username).all()
        for auth in auth_tokens:
            print(f"   Auth ID: {auth.id}")
            print(f"   User: {auth.name}")
            print(f"   Broker: {auth.broker}")
            print(f"   Is Revoked: {auth.is_revoked}")
            
    except Exception as e:
        print(f"Error in deep debug: {e}")
        import traceback
        traceback.print_exc()

def test_with_correct_user():
    """Test with the correct user ID."""
    try:
        from database.auth_db import get_auth_token_broker
        
        # The user ID in the database is "Reeshoo" not "admin"
        api_key = "420ff93cf719bdcd81f5f33db189f9e9b08fa25e76c03fcfcd89762c0868efbd"
        
        print(f"\n6. Testing with API key for user 'Reeshoo':")
        auth_token, broker = get_auth_token_broker(api_key)
        print(f"   Auth Token: {auth_token[:50] if auth_token else 'None'}")
        print(f"   Broker: {broker}")
        
        if auth_token and broker:
            print(f"   ✓ Success! Found broker configuration")
        else:
            print(f"   ✗ Failed to find broker configuration")
            
    except Exception as e:
        print(f"Error testing with correct user: {e}")

def main():
    """Main function."""
    print("Deep Debug OpenAlgo API Key Verification")
    print("=" * 50)
    
    deep_debug_api_key()
    test_with_correct_user()

if __name__ == "__main__":
    main()