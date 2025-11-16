#!/usr/bin/env python3
"""
OpenAlgo API Test - Corrected Version
Tests OpenAlgo API with proper Flask-RESTX structure
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path
from datetime import datetime

# Add fortress to path
sys.path.insert(0, str(Path(__file__).parent / "fortress" / "src"))

from fortress.utils.api_key_manager import SecureAPIKeyManager

class CorrectedOpenAlgoAPITest:
    """Test OpenAlgo API with correct Flask-RESTX structure"""
    
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
            
    async def test_ping_api(self, api_key):
        """Test ping API with POST request and JSON body"""
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
                            self.add_result("Ping API", "PASS", 
                                          f"Ping successful: {response_data.get('message', 'OK')}")
                        else:
                            self.add_result("Ping API", "FAIL", 
                                          f"Ping failed: {response_data}")
                    except json.JSONDecodeError:
                        self.add_result("Ping API", "FAIL", 
                                      f"Invalid JSON response: {response_text[:100]}")
                else:
                    self.add_result("Ping API", "FAIL", 
                                  f"Status {response.status}: {response_text[:100]}")
                    
        except Exception as e:
            self.add_result("Ping API", "FAIL", f"Error: {e}")
            
    async def test_funds_api(self, api_key):
        """Test funds API"""
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
                            self.add_result("Funds API", "PASS", 
                                          f"Funds retrieved: {funds}")
                        else:
                            self.add_result("Funds API", "FAIL", 
                                          f"Funds failed: {response_data}")
                    except json.JSONDecodeError:
                        self.add_result("Funds API", "FAIL", 
                                      f"Invalid JSON response: {response_text[:100]}")
                else:
                    self.add_result("Funds API", "FAIL", 
                                  f"Status {response.status}: {response_text[:100]}")
                    
        except Exception as e:
            self.add_result("Funds API", "FAIL", f"Error: {e}")
            
    async def test_positionbook_api(self, api_key):
        """Test positionbook API"""
        try:
            url = f"{self.base_url}/api/v1/positionbook"
            headers = {"Content-Type": "application/json"}
            data = {"apikey": api_key}
            
            async with self.session.post(url, headers=headers, json=data) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        if response_data.get("status") == "success":
                            positions = response_data.get("data", [])
                            self.add_result("Positionbook API", "PASS", 
                                          f"Positions retrieved: {len(positions)} positions")
                        else:
                            self.add_result("Positionbook API", "FAIL", 
                                          f"Positionbook failed: {response_data}")
                    except json.JSONDecodeError:
                        self.add_result("Positionbook API", "FAIL", 
                                      f"Invalid JSON response: {response_text[:100]}")
                else:
                    self.add_result("Positionbook API", "FAIL", 
                                  f"Status {response.status}: {response_text[:100]}")
                    
        except Exception as e:
            self.add_result("Positionbook API", "FAIL", f"Error: {e}")
            
    async def test_orderbook_api(self, api_key):
        """Test orderbook API"""
        try:
            url = f"{self.base_url}/api/v1/orderbook"
            headers = {"Content-Type": "application/json"}
            data = {"apikey": api_key}
            
            async with self.session.post(url, headers=headers, json=data) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        if response_data.get("status") == "success":
                            orders = response_data.get("data", [])
                            self.add_result("Orderbook API", "PASS", 
                                          f"Orders retrieved: {len(orders)} orders")
                        else:
                            self.add_result("Orderbook API", "FAIL", 
                                          f"Orderbook failed: {response_data}")
                    except json.JSONDecodeError:
                        self.add_result("Orderbook API", "FAIL", 
                                      f"Invalid JSON response: {response_text[:100]}")
                else:
                    self.add_result("Orderbook API", "FAIL", 
                                  f"Status {response.status}: {response_text[:100]}")
                    
        except Exception as e:
            self.add_result("Orderbook API", "FAIL", f"Error: {e}")
            
    async def test_server_connectivity(self):
        """Test basic server connectivity"""
        try:
            async with self.session.get(self.base_url) as response:
                if response.status == 200:
                    self.add_result("Server Connectivity", "PASS", 
                                  f"Server responding at {self.base_url}")
                else:
                    self.add_result("Server Connectivity", "FAIL", 
                                  f"Server returned status {response.status}")
        except Exception as e:
            self.add_result("Server Connectivity", "FAIL", 
                          f"Cannot connect to server: {e}")
            
    async def run_corrected_tests(self, api_key):
        """Run corrected API tests"""
        print(f"🔍 Running Corrected OpenAlgo API Tests")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Base URL: {self.base_url}")
        print(f"🔐 API Key: {api_key[:8]}...")
        print("=" * 60)
        print("⚠️  Testing with POST requests and JSON body (Flask-RESTX format)")
        print()
        
        await self.test_server_connectivity()
        
        if api_key:
            await self.test_ping_api(api_key)
            await self.test_funds_api(api_key)
            await self.test_positionbook_api(api_key)
            await self.test_orderbook_api(api_key)
        else:
            self.add_result("API Tests", "SKIP", "No API key provided")
            
        print("\n" + "=" * 60)
        print("📊 CORRECTED API TEST SUMMARY")
        print("=" * 60)
        
        # Summary statistics
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        warnings = sum(1 for r in self.results if r["status"] == "WARN")
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        
        # Show failed tests
        if failed > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.results:
                if result["status"] == "FAIL":
                    print(f"   - {result['test']}: {result['message']}")
                    
        # Show recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if failed > 0:
            print("   - Check OpenAlgo server logs for detailed error messages")
            print("   - Verify broker credentials are properly configured")
            print("   - Ensure Fyers API connection is working")
            print("   - Check OpenAlgo configuration files")
        if passed > 0:
            print("   - Some API endpoints are working! Check specific failures above.")
        if passed == total_tests:
            print("   - All tests passed! OpenAlgo API is working correctly.")
            
        return self.results

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenAlgo API Test - Corrected Version")
    parser.add_argument("--url", default="http://localhost:5000", 
                       help="OpenAlgo base URL")
    parser.add_argument("--api-key", help="API key to test")
    
    args = parser.parse_args()
    
    # Also check for API key in secure storage
    if not args.api_key:
        try:
            secure_manager = SecureAPIKeyManager()
            stored_key = secure_manager.get_api_key("openalgo")
            if stored_key:
                args.api_key = stored_key
                print(f"🔐 Using stored API key: {stored_key[:8]}...")
        except:
            pass
    
    if not args.api_key:
        print("❌ No API key provided. Please provide --api-key or ensure one is stored securely.")
        print("💡 You can get your API key from the OpenAlgo dashboard at http://localhost:5000/apikey")
        return 1
    
    async with CorrectedOpenAlgoAPITest(args.url) as test:
        results = await test.run_corrected_tests(args.api_key)
        
        # Return exit code based on results
        failed_count = sum(1 for r in results if r["status"] == "FAIL")
        return 1 if failed_count > 0 else 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 API test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)