#!/usr/bin/env python3
"""
OpenAlgo System Diagnostics
Comprehensive diagnostic tool for OpenAlgo integration issues
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

class OpenAlgoDiagnostics:
    """Comprehensive OpenAlgo diagnostics"""
    
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
            
    async def test_api_endpoints(self):
        """Test various API endpoints"""
        endpoints = [
            "/api/v1/ping",
            "/api/v1/funds",
            "/api/v1/positionbook",
            "/api/v1/orderbook",
            "/api/v1/tradebook",
            "/api/v1/holdings",
            "/api/v1/orders",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                async with self.session.get(url) as response:
                    if response.status == 200:
                        self.add_result(f"API Endpoint {endpoint}", "PASS", 
                                      f"Endpoint working (status {response.status})")
                    elif response.status == 401:
                        self.add_result(f"API Endpoint {endpoint}", "WARN", 
                                      f"Authentication required (status {response.status})")
                    elif response.status == 404:
                        self.add_result(f"API Endpoint {endpoint}", "FAIL", 
                                      f"Endpoint not found (status {response.status})")
                    else:
                        self.add_result(f"API Endpoint {endpoint}", "FAIL", 
                                      f"Unexpected status {response.status}")
                        
                    # Try to get response content for debugging
                    try:
                        content = await response.text()
                        if len(content) < 500:  # Only show small responses
                            print(f"   Response: {content[:200]}...")
                    except:
                        pass
                        
            except Exception as e:
                self.add_result(f"API Endpoint {endpoint}", "FAIL", 
                              f"Error accessing endpoint: {e}")
                
    async def test_authentication_flow(self):
        """Test authentication flow"""
        try:
            # Test login page
            login_url = f"{self.base_url}/auth/login"
            async with self.session.get(login_url) as response:
                if response.status == 200:
                    self.add_result("Login Page Access", "PASS", 
                                  "Login page accessible")
                else:
                    self.add_result("Login Page Access", "FAIL", 
                                  f"Login page returned status {response.status}")
                    
            # Test API key page (requires login)
            api_key_url = f"{self.base_url}/apikey"
            async with self.session.get(api_key_url) as response:
                if response.status == 200:
                    self.add_result("API Key Page Access", "PASS", 
                                  "API key page accessible (user may be logged in)")
                elif response.status == 302 or response.status == 401:
                    self.add_result("API Key Page Access", "WARN", 
                                  f"API key page requires login (status {response.status})")
                else:
                    self.add_result("API Key Page Access", "FAIL", 
                                  f"API key page returned status {response.status}")
                    
        except Exception as e:
            self.add_result("Authentication Flow", "FAIL", 
                          f"Error testing authentication: {e}")
            
    async def test_with_api_key(self, api_key):
        """Test API endpoints with provided API key"""
        if not api_key:
            self.add_result("API Key Test", "SKIP", "No API key provided")
            return
            
        headers = {"Authorization": f"Bearer {api_key}"}
        test_endpoints = [
            "/api/v1/ping",
            "/api/v1/funds",
            "/api/v1/positionbook",
        ]
        
        for endpoint in test_endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        self.add_result(f"API Key Test {endpoint}", "PASS", 
                                      f"Authenticated access successful")
                        
                        # Try to parse JSON response
                        try:
                            data = await response.json()
                            if "status" in data:
                                self.add_result(f"API Response {endpoint}", "INFO", 
                                              f"Response status: {data.get('status')}")
                        except:
                            pass
                            
                    elif response.status == 401:
                        self.add_result(f"API Key Test {endpoint}", "FAIL", 
                                      f"API key rejected (status {response.status})")
                    else:
                        self.add_result(f"API Key Test {endpoint}", "FAIL", 
                                      f"Unexpected status {response.status}")
                        
            except Exception as e:
                self.add_result(f"API Key Test {endpoint}", "FAIL", 
                              f"Error with API key: {e}")
                
    async def check_broker_status(self):
        """Check broker connection status"""
        try:
            # Try to access broker status endpoint
            status_url = f"{self.base_url}/api/v1/status"
            async with self.session.get(status_url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        self.add_result("Broker Status", "PASS", 
                                      f"Broker status available: {data}")
                    except:
                        self.add_result("Broker Status", "PASS", 
                                      "Broker status endpoint working")
                else:
                    self.add_result("Broker Status", "WARN", 
                              f"Broker status endpoint returned {response.status}")
                              
        except Exception as e:
            self.add_result("Broker Status", "WARN", 
                          f"Cannot check broker status: {e}")
            
    async def run_diagnostics(self, api_key=None):
        """Run all diagnostics"""
        print(f"🔍 Running OpenAlgo Diagnostics")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Base URL: {self.base_url}")
        print("=" * 60)
        
        await self.test_server_connectivity()
        await self.test_api_endpoints()
        await self.test_authentication_flow()
        await self.test_with_api_key(api_key)
        await self.check_broker_status()
        
        print("\n" + "=" * 60)
        print("📊 DIAGNOSTICS SUMMARY")
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
            print("   - Check OpenAlgo server logs for errors")
            print("   - Verify OpenAlgo configuration files")
            print("   - Ensure all required services are running")
        if warnings > 0:
            print("   - Review warning messages for potential issues")
        if passed == total_tests:
            print("   - All tests passed! System appears to be working correctly.")
            
        # Save results to file
        results_file = Path("openalgo_diagnostics.json")
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "base_url": self.base_url,
                "summary": {
                    "total": total_tests,
                    "passed": passed,
                    "failed": failed,
                    "warnings": warnings
                },
                "results": self.results
            }, f, indent=2)
            
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        return self.results

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenAlgo System Diagnostics")
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
    
    async with OpenAlgoDiagnostics(args.url) as diagnostics:
        results = await diagnostics.run_diagnostics(args.api_key)
        
        # Return exit code based on results
        failed_count = sum(1 for r in results if r["status"] == "FAIL")
        return 1 if failed_count > 0 else 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Diagnostics interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)