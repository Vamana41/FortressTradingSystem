#!/usr/bin/env python3
"""
Debug script to check API key validation in OpenAlgo.
"""

import os
import sys
import hashlib

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import ApiKeys, verify_api_key, PEPPER
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

def check_api_key_validation():
    """Check API key validation process."""
    
    # Get all API keys from database
    api_keys = ApiKeys.query.all()
    
    print(f"Found {len(api_keys)} API key(s) in database:")
    
    for i, api_key_obj in enumerate(api_keys):
        print(f"\nAPI Key {i+1}:")
        print(f"  User ID: {api_key_obj.user_id}")
        print(f"  Created: {api_key_obj.created_at}")
        print(f"  Has Hash: {'Yes' if api_key_obj.api_key_hash else 'No'}")
        print(f"  Has Encrypted: {'Yes' if api_key_obj.api_key_encrypted else 'No'}")
        
        # Test with user-provided key
        test_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
        
        # Create peppered version
        peppered_test_key = test_key + PEPPER
        
        try:
            # Try to verify against this key's hash
            ph = PasswordHasher()
            ph.verify(api_key_obj.api_key_hash, peppered_test_key)
            print(f"  ✅ User-provided key matches this API key!")
        except VerifyMismatchError:
            print(f"  ❌ User-provided key does NOT match this API key")
        except Exception as e:
            print(f"  ⚠️  Error verifying: {e}")

def test_key_verification():
    """Test the verification process with the user-provided key."""
    test_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"
    
    print(f"\n{'='*60}")
    print("Testing API key verification:")
    print(f"Test key: {test_key[:20]}...")
    
    # Test verification
    user_id = verify_api_key(test_key)
    
    if user_id:
        print(f"✅ API key is valid! User ID: {user_id}")
    else:
        print(f"❌ API key is invalid!")
        
        # Let's check what went wrong
        print(f"\nDebugging verification process:")
        print(f"PEPPER used: {PEPPER}")
        
        # Get all keys and show their hashes
        api_keys = ApiKeys.query.all()
        for api_key_obj in api_keys:
            print(f"\nStored key for user {api_key_obj.user_id}:")
            print(f"  Hash: {api_key_obj.api_key_hash[:50]}...")
            
            # Create our own hash for comparison
            ph = PasswordHasher()
            try:
                # This should work if the key matches
                ph.verify(api_key_obj.api_key_hash, test_key + PEPPER)
                print(f"  ✅ Our test key matches this stored hash!")
            except VerifyMismatchError:
                print(f"  ❌ Our test key does NOT match this stored hash")

def main():
    """Main function."""
    print("🔍 OpenAlgo API Key Validation Debug")
    print("=" * 60)
    
    check_api_key_validation()
    test_key_verification()

if __name__ == "__main__":
    main()