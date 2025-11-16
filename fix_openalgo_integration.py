#!/usr/bin/env python3
"""
OpenAlgo Integration Fix Script
Comprehensive solution for OpenAlgo API key and Fyers connection issues
"""

import asyncio
import aiohttp
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add fortress to path
sys.path.insert(0, str(Path(__file__).parent / "fortress" / "src"))

from fortress.utils.api_key_manager import SecureAPIKeyManager

class OpenAlgoIntegrationFix:
    """Comprehensive fix for OpenAlgo integration issues"""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = None
        self.results = []

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def add_result(self, test_name, status, message, details=None):
        """Add test result"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        print(f"{'✅' if status == 'PASS' else '❌' if status == 'FAIL' else '⚠️'} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")

    async def check_server_status(self):
        """Check if OpenAlgo server is running"""
        try:
            async with self.session.get(self.base_url) as response:
                if response.status == 200:
                    self.add_result("Server Status", "PASS", "OpenAlgo server is running")
                    return True
                else:
                    self.add_result("Server Status", "FAIL", f"Server returned status {response.status}")
                    return False
        except Exception as e:
            self.add_result("Server Status", "FAIL", f"Cannot connect to server: {e}")
            return False

    async def test_api_key_validity(self, api_key):
        """Test if API key is valid"""
        try:
            url = f"{self.base_url}/api/v1/ping"
            headers = {"Content-Type": "application/json"}
            data = {"apikey": api_key}

            async with self.session.post(url, headers=headers, json=data) as response:
                response_text = await response.text()

                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        if response_data.get("status") == "success":
                            self.add_result("API Key Validity", "PASS",
                                          f"API key is valid: {response_data.get('message', 'OK')}")
                            return True
                        else:
                            self.add_result("API Key Validity", "FAIL",
                                          f"API key invalid: {response_data.get('message', 'Unknown error')}")
                            return False
                    except json.JSONDecodeError:
                        self.add_result("API Key Validity", "FAIL",
                                      f"Invalid JSON response: {response_text[:100]}")
                        return False
                elif response.status == 403:
                    try:
                        response_data = json.loads(response_text)
                        self.add_result("API Key Validity", "FAIL",
                                      f"API key rejected: {response_data.get('message', 'Forbidden')}")
                    except:
                        self.add_result("API Key Validity", "FAIL",
                                      f"API key rejected: {response_text[:100]}")
                    return False
                else:
                    self.add_result("API Key Validity", "FAIL",
                                  f"Unexpected status {response.status}: {response_text[:100]}")
                    return False

        except Exception as e:
            self.add_result("API Key Validity", "FAIL", f"Error testing API key: {e}")
            return False

    async def check_fyers_credentials(self):
        """Check Fyers credentials in environment"""
        required_vars = [
            "FYERS_APP_ID",
            "FYERS_SECRET_KEY",
            "FYERS_REDIRECT_URI",
            "FYERS_AUTH_CODE"
        ]

        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                # Mask sensitive data
                if "SECRET" in var or "AUTH" in var:
                    masked_value = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
                    self.add_result(f"Fyers Config {var}", "INFO", f"Found: {masked_value}")
                else:
                    self.add_result(f"Fyers Config {var}", "INFO", f"Found: {value}")

        if missing_vars:
            self.add_result("Fyers Credentials", "FAIL",
                          f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        else:
            self.add_result("Fyers Credentials", "PASS", "All required Fyers credentials found")
            return True

    async def test_broker_connection(self, api_key):
        """Test broker connection through OpenAlgo"""
        try:
            url = f"{self.base_url}/api/v1/funds"
            headers = {"Content-Type": "application/json"}
            data = {"apikey": api_key}

            async with self.session.post(url, headers=headers, json=data) as response:
                response_text = await response.text()

                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        if response_data.get("status") == "success":
                            funds = response_data.get("data", {})
                            self.add_result("Broker Connection", "PASS",
                                          f"Broker connection successful: {funds}")
                            return True
                        else:
                            error_msg = response_data.get("message", "Unknown error")
                            if "500" in error_msg or "Internal Server Error" in error_msg:
                                self.add_result("Broker Connection", "FAIL",
                                              f"Broker server error (500): {error_msg}")
                            else:
                                self.add_result("Broker Connection", "FAIL",
                                              f"Broker connection failed: {error_msg}")
                            return False
                    except json.JSONDecodeError:
                        self.add_result("Broker Connection", "FAIL",
                                      f"Invalid JSON response: {response_text[:100]}")
                        return False
                elif response.status == 500:
                    self.add_result("Broker Connection", "FAIL",
                                  f"Broker server error (500): {response_text[:100]}")
                    return False
                else:
                    self.add_result("Broker Connection", "FAIL",
                                  f"Broker connection failed (status {response.status}): {response_text[:100]}")
                    return False

        except Exception as e:
            self.add_result("Broker Connection", "FAIL", f"Error testing broker connection: {e}")
            return False

    async def get_valid_api_key_from_user(self):
        """Guide user to get valid API key"""
        print("\n" + "="*60)
        print("🔑 GETTING VALID OPENALGO API KEY")
        print("="*60)
        print("\n🎯 To get a valid OpenAlgo API key, please follow these steps:")
        print("\n1. 🌐 Open your browser and go to: http://localhost:5000")
        print("2. 🔐 Login with your OpenAlgo credentials (username: Reeshoo, password: Moscow@123)")
        print("3. 📋 Once logged in, navigate to: http://localhost:5000/apikey")
        print("4. 🔄 If you don't see an API key, click 'Generate New API Key'")
        print("5. 📄 Copy the generated API key (it should be 64 characters long)")
        print("\n💡 The API key will look like: a1b2c3d4e5f6... (64 characters total)")

        api_key = input("\n🔑 Please paste your OpenAlgo API key here: ").strip()

        if len(api_key) == 64 and all(c in 'abcdef0123456789' for c in api_key.lower()):
            # Test the key
            print("\n🧪 Testing the provided API key...")
            if await self.test_api_key_validity(api_key):
                # Save to secure storage
                secure_manager = SecureAPIKeyManager()
                secure_manager.store_api_key("openalgo", api_key)
                print("✅ API key saved to secure storage!")
                return api_key
            else:
                print("❌ The provided API key is invalid. Please try again.")
                return None
        else:
            print("❌ Invalid API key format. Should be 64 hex characters.")
            return None

    async def check_environment_setup(self):
        """Check overall environment setup"""
        print("\n" + "="*60)
        print("🔧 ENVIRONMENT SETUP CHECK")
        print("="*60)

        # Check .env file
        env_file = Path(".env")
        if env_file.exists():
            self.add_result("Environment File", "PASS", f".env file found")

            # Check for OpenAlgo configuration
            with open(env_file) as f:
                env_content = f.read()

            if "OPENALGO_API_KEY" in env_content:
                self.add_result("OpenAlgo Config", "PASS", "OpenAlgo configuration found in .env")
            else:
                self.add_result("OpenAlgo Config", "WARN", "OpenAlgo configuration missing from .env")
        else:
            self.add_result("Environment File", "FAIL", ".env file not found")

        # Check Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            self.add_result("Redis Connection", "PASS", "Redis server is running")
        except:
            self.add_result("Redis Connection", "FAIL", "Redis server not accessible")

        # Check Python environment
        try:
            import fortress
            self.add_result("Fortress Environment", "PASS", "Fortress modules importable")
        except:
            self.add_result("Fortress Environment", "FAIL", "Fortress modules not importable")

    async def run_comprehensive_fix(self):
        """Run comprehensive fix process"""
        print("🔧 OPENALGO INTEGRATION FIX SCRIPT")
        print("="*60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 OpenAlgo URL: {self.base_url}")
        print()

        # Step 1: Check environment setup
        await self.check_environment_setup()

        # Step 2: Check server status
        server_running = await self.check_server_status()
        if not server_running:
            print("\n❌ OpenAlgo server is not running. Please start it first:")
            print("   python openalgo/app.py")
            return False

        # Step 3: Check current API key
        secure_manager = SecureAPIKeyManager()
        current_api_key = secure_manager.get_api_key("openalgo")

        if current_api_key:
            print(f"\n🔍 Found stored API key: {current_api_key[:8]}...")
            api_key_valid = await self.test_api_key_validity(current_api_key)

            if not api_key_valid:
                print("\n⚠️  Current API key is invalid. Getting new one...")
                current_api_key = None
        else:
            print("\n⚠️  No API key found in secure storage.")
            api_key_valid = False

        # Step 4: Get valid API key if needed
        if not current_api_key or not api_key_valid:
            print("\n🔄 Need to get a valid API key from OpenAlgo dashboard...")
            new_api_key = await self.get_valid_api_key_from_user()

            if new_api_key:
                current_api_key = new_api_key
                api_key_valid = True
            else:
                print("\n❌ Failed to get valid API key. Cannot proceed.")
                return False

        # Step 5: Check Fyers credentials
        fyers_configured = await self.check_fyers_credentials()

        if not fyers_configured:
            print("\n⚠️  Fyers credentials are not properly configured.")
            print("\n🔧 To fix Fyers connection, please:")
            print("1. 📝 Add these to your .env file:")
            print("   FYERS_APP_ID=your_fyers_app_id")
            print("   FYERS_SECRET_KEY=your_fyers_secret_key")
            print("   FYERS_REDIRECT_URI=http://localhost:8080/fyers/callback")
            print("   FYERS_AUTH_CODE=your_fyers_auth_code")
            print("\n2. 🌐 Go to OpenAlgo dashboard: http://localhost:5000")
            print("3. 🔐 Login and configure Fyers broker credentials")
            print("4. 🔄 Complete the Fyers OAuth flow if required")

        # Step 6: Test broker connection
        if fyers_configured and api_key_valid:
            await self.test_broker_connection(current_api_key)

        # Final summary
        print("\n" + "="*60)
        print("📊 INTEGRATION FIX SUMMARY")
        print("="*60)

        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")

        print(f"Total Checks: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")

        if failed == 0:
            print("\n🎉 SUCCESS! OpenAlgo integration is working correctly.")
            print("\n🚀 Next steps:")
            print("1. Start Fortress Trading System: python fortress/src/fortress/main.py")
            print("2. Test with: python test_openalgo_api_corrected.py")
            print("3. Check dashboard at: http://localhost:8000")
        else:
            print(f"\n⚠️  Found {failed} issues that need attention.")
            print("\n🔧 Please review the failed checks above and fix them.")

        return failed == 0

async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="OpenAlgo Integration Fix Script")
    parser.add_argument("--url", default="http://localhost:5000",
                       help="OpenAlgo base URL")
    parser.add_argument("--skip-interactive", action="store_true",
                       help="Skip interactive API key input")

    args = parser.parse_args()

    async with OpenAlgoIntegrationFix(args.url) as fix:
        success = await fix.run_comprehensive_fix()
        return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Fix script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
