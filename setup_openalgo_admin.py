#!/usr/bin/env python3
"""
OpenAlgo Admin Setup Script

This script creates the initial admin user for OpenAlgo and generates an API key.
It should be run once when setting up OpenAlgo for the first time.
"""

import sys
import os
import requests
from pathlib import Path

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def setup_admin_user():
    """Create admin user through the web interface."""

    # Setup data
    setup_data = {
        "username": "admin",
        "email": "admin@fortress.local",
        "password": "FortressAdmin2025!",
        "confirm_password": "FortressAdmin2025!"
    }

    try:
        # First, get the CSRF token from the setup page
        session = requests.Session()
        response = session.get("http://localhost:5000/setup")

        if response.status_code != 200:
            print(f"Failed to access setup page: {response.status_code}")
            return False

        # Extract CSRF token from the response
        csrf_token = None
        import re
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)

        if not csrf_token:
            print("Could not extract CSRF token from setup page")
            return False

        print(f"Extracted CSRF token: {csrf_token[:20]}...")

        # Submit the setup form
        setup_data["csrf_token"] = csrf_token
        response = session.post("http://localhost:5000/setup", data=setup_data)

        if response.status_code == 200 and "Account created successfully" in response.text:
            print("Admin user created successfully!")
            print(f"Username: {setup_data['username']}")
            print(f"Password: {setup_data['password']}")
            return True
        else:
            print(f"Setup failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"Error during setup: {e}")
        return False

def get_api_key_after_login():
    """Login and get the API key."""

    login_data = {
        "username": "admin",
        "password": "FortressAdmin2025!"
    }

    try:
        session = requests.Session()

        # Get login page to extract CSRF token
        response = session.get("http://localhost:5000/auth/login")
        if response.status_code != 200:
            print(f"Failed to access login page: {response.status_code}")
            return None

        # Extract CSRF token
        import re
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        else:
            print("Could not extract CSRF token from login page")
            return None

        # Login
        login_data["csrf_token"] = csrf_token
        response = session.post("http://localhost:5000/auth/login", data=login_data)

        if response.status_code != 200 or "login" in response.url:
            print("Login failed")
            return None

        print("Login successful!")

        # Now get the API key page
        response = session.get("http://localhost:5000/apikey")
        if response.status_code != 200:
            print(f"Failed to access API key page: {response.status_code}")
            return None

        # Check if API key exists
        if "has_api_key: true" in response.text or "has_api_key=True" in response.text:
            # Extract existing API key
            api_key_match = re.search(r'api_key: "([^"]+)"', response.text)
            if api_key_match:
                api_key = api_key_match.group(1)
                print(f"Found existing API key: {api_key}")
                return api_key
            else:
                print("API key exists but could not extract it")
                return None
        else:
            # Generate new API key
            print("No API key found, generating new one...")

            # Get CSRF token for API key generation
            csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
            else:
                print("Could not extract CSRF token for API key generation")
                return None

            # Generate API key via AJAX
            headers = {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf_token
            }

            api_response = session.post(
                "http://localhost:5000/apikey",
                json={"user_id": "admin"},
                headers=headers
            )

            if api_response.status_code == 200:
                api_data = api_response.json()
                if "api_key" in api_data:
                    api_key = api_data["api_key"]
                    print(f"Generated new API key: {api_key}")
                    return api_key
                else:
                    print(f"API key generation response: {api_data}")
                    return None
            else:
                print(f"API key generation failed: {api_response.status_code}")
                return None

    except Exception as e:
        print(f"Error getting API key: {e}")
        return None

def main():
    """Main setup function."""
    print("OpenAlgo Admin Setup Script")
    print("=" * 40)

    # Check if OpenAlgo is running
    try:
        response = requests.get("http://localhost:5000/", timeout=5)
        if response.status_code != 200:
            print("OpenAlgo server is not responding properly")
            return False
    except Exception as e:
        print(f"Cannot connect to OpenAlgo server: {e}")
        print("Please make sure OpenAlgo is running on http://localhost:5000")
        return False

    print("OpenAlgo server is running ✓")

    # Check if setup is needed
    response = requests.get("http://localhost:5000/setup", allow_redirects=False)
    if response.status_code == 302:
        print("Setup already completed, trying to login...")
        api_key = get_api_key_after_login()
        if api_key:
            print(f"\nSuccessfully retrieved API key: {api_key}")
            print(f"\nPlease update your .env file with:")
            print(f"OPENALGO_API_KEY={api_key}")
            return True
        else:
            print("Failed to retrieve existing API key")
            return False
    elif response.status_code == 200:
        print("Setup needed, creating admin user...")

        # Create admin user
        if setup_admin_user():
            print("\nAdmin user created successfully!")

            # Get API key
            api_key = get_api_key_after_login()
            if api_key:
                print(f"\nSuccessfully retrieved API key: {api_key}")
                print(f"\nPlease update your .env file with:")
                print(f"OPENALGO_API_KEY={api_key}")
                return True
            else:
                print("Failed to retrieve API key after setup")
                return False
        else:
            print("Failed to create admin user")
            return False
    else:
        print(f"Unexpected response from setup page: {response.status_code}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
