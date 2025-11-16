#!/usr/bin/env python3
"""
Register API Key in OpenAlgo Database

This script registers the user's API key in the OpenAlgo database
so it can be used for authentication instead of returning 403 errors.
"""

import os
import sys
import sqlite3
import hashlib
import secrets
from pathlib import Path

def get_admin_username():
    """Get the admin username from the database"""
    db_paths = [
        "openalgo/db/openalgo.db",
        "openalgo/openalgo/db/openalgo.db"
    ]

    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print(f"Database not found in any of: {db_paths}")
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("Users table not found. Please set up admin user first.")
            return None

        # Get admin user
        cursor.execute("SELECT username FROM users LIMIT 1")
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            print("No admin user found. Please create admin user first.")
            return None

    except Exception as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()

def register_api_key(username, api_key):
    """Register the API key in OpenAlgo database"""
    # Add the openalgo directory to Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

    try:
        from openalgo.openalgo.database.auth_db import upsert_api_key

        # Register the API key
        success = upsert_api_key(username, api_key)

        if success:
            print(f"✅ API key registered successfully for user: {username}")
            return True
        else:
            print(f"❌ Failed to register API key")
            return False

    except ImportError as e:
        print(f"❌ Could not import OpenAlgo database module: {e}")
        print("Trying alternative method...")
        return register_api_key_manual(username, api_key)
    except Exception as e:
        print(f"❌ Error registering API key: {e}")
        return False

def register_api_key_manual(username, api_key):
    """Manual API key registration using direct database access"""
    db_paths = [
        "openalgo/db/openalgo.db",
        "openalgo/openalgo/db/openalgo.db"
    ]

    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        print(f"Database not found in any of: {db_paths}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if api_keys table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'")
        if not cursor.fetchone():
            print("API keys table not found. Creating it...")
            cursor.execute('''
                CREATE TABLE api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    api_key_hash TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')
            conn.commit()

        # Simple hash for now (in production, use proper encryption)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Insert or update the API key
        cursor.execute('''
            INSERT OR REPLACE INTO api_keys (user_id, api_key_hash, api_key_encrypted)
            VALUES (?, ?, ?)
        ''', (username, api_key_hash, api_key))

        conn.commit()

        print(f"✅ API key registered manually for user: {username}")
        return True

    except Exception as e:
        print(f"❌ Manual registration failed: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("OpenAlgo API Key Registration")
    print("=" * 40)

    # API key to register
    api_key = "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0"

    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")

    # Get admin username
    print("\nFinding admin user...")
    username = get_admin_username()

    if not username:
        # Try default admin
        username = "admin"
        print(f"Using default username: {username}")
    else:
        print(f"Found admin user: {username}")

    # Register the API key
    print("\nRegistering API key...")
    success = register_api_key(username, api_key)

    if success:
        print("\n✅ API key registration complete!")
        print("\nYou can now test the API with:")
        print(f'curl -X POST "http://localhost:5000/api/v1/ping" -H "Content-Type: application/json" -d "{{\"apikey\":\"{api_key}\"}}"')
    else:
        print("\n❌ API key registration failed.")
        print("Please check the error messages above.")

if __name__ == "__main__":
    main()
