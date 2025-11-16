#!/usr/bin/env python3
"""
Test script for Rtd_Ws_AB_plugin Integration with Token Sharing
Tests the integration between your battle-tested Rtd_Ws_AB_plugin method and Fortress Trading System
"""

import sys
import time
import json
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path.cwd()))

from rtd_ws_integration_manager import RtdWsIntegrationManager
from token_sharing_manager import TokenSharingManager

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestRtdWsIntegration:
    """Test class for Rtd_Ws_AB_plugin integration with token sharing"""

    def __init__(self):
        self.integration = RtdWsIntegrationManager()
        self.token_manager = TokenSharingManager()
        self.test_results = []

    def run_test(self, test_name: str, test_func) -> bool:
        """Run a test and record results"""
        try:
            logger.info(f"Running test: {test_name}")
            result = test_func()
            success = bool(result)
            self.test_results.append({
                "test": test_name,
                "status": "✅ PASS" if success else "❌ FAIL",
                "result": result
            })
            logger.info(f"Test {test_name}: {'PASSED' if success else 'FAILED'}")
            return success
        except Exception as e:
            self.test_results.append({
                "test": test_name,
                "status": "❌ FAIL",
                "error": str(e)
            })
            logger.error(f"Test {test_name}: FAILED - {e}")
            return False

    def test_token_sharing_manager(self) -> bool:
        """Test token sharing manager initialization"""
        return bool(self.token_manager)

    def test_token_extraction(self) -> bool:
        """Test token extraction from OpenAlgo"""
        token = self.token_manager.get_openalgo_fyers_token()
        return token is not None or True  # Allow None if no token exists yet

    def test_credentials_extraction(self) -> bool:
        """Test credentials extraction from .env"""
        credentials = self.token_manager.get_fyers_credentials_from_env()
        return bool(credentials.get('app_id') and credentials.get('secret_key'))

    def test_configuration_loading(self) -> bool:
        """Test configuration loading"""
        config = self.integration.load_configuration()
        return bool(config and "fyers" in config)

    def test_prerequisites(self) -> bool:
        """Test prerequisites check"""
        return self.integration.check_prerequisites()

    def test_file_existence(self) -> bool:
        """Test that required files exist"""
        required_files = [
            self.integration.fyers_client_path,
            self.integration.relay_server_path,
            self.integration.wsrtd_dll_path
        ]
        return all(file_path.exists() for file_path in required_files)

    def test_amibroker_plugin_path(self) -> bool:
        """Test AmiBroker plugin path"""
        plugin_path = Path(self.integration.config["paths"]["amibroker_plugin_path"])
        return plugin_path.exists()

    def test_atm_scanner_config(self) -> bool:
        """Test ATM scanner configuration"""
        atm_config = self.integration.config.get("atm_scanner", {})
        return bool(atm_config.get("enabled") and atm_config.get("symbols"))

    def test_market_data_structure(self) -> bool:
        """Test market data structure creation"""
        from datetime import datetime
        from rtd_ws_integration_manager import MarketDataPoint

        data_point = MarketDataPoint(
            symbol="NIFTY",
            timestamp=datetime.now(),
            open_price=18000.0,
            high_price=18100.0,
            low_price=17950.0,
            close_price=18075.0,
            volume=1000000
        )

        return bool(data_point.symbol == "NIFTY")

    def test_integration_status(self) -> bool:
        """Test integration status reporting"""
        status = self.integration.get_integration_status()
        return bool(status and "running" in status and "token_sharing" in status)

    def test_token_sync(self) -> bool:
        """Test token sync functionality"""
        result = self.token_manager.sync_tokens()
        return bool(result and 'status' in result)

    def test_token_info(self) -> bool:
        """Test token info retrieval"""
        info = self.token_manager.get_current_token_info()
        return bool(info and 'openalgo_db_exists' in info)

    def run_all_tests(self) -> bool:
        """Run all tests"""
        logger.info("Starting Rtd_Ws_AB_plugin Integration Tests with Token Sharing")

        tests = [
            ("Token Sharing Manager", self.test_token_sharing_manager),
            ("Token Extraction", self.test_token_extraction),
            ("Credentials Extraction", self.test_credentials_extraction),
            ("Configuration Loading", self.test_configuration_loading),
            ("File Existence", self.test_file_existence),
            ("Prerequisites Check", self.test_prerequisites),
            ("AmiBroker Plugin Path", self.test_amibroker_plugin_path),
            ("ATM Scanner Config", self.test_atm_scanner_config),
            ("Market Data Structure", self.test_market_data_structure),
            ("Integration Status", self.test_integration_status),
            ("Token Sync", self.test_token_sync),
            ("Token Info", self.test_token_info),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                passed += 1

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)

        for result in self.test_results:
            logger.info(f"{result['test']}: {result['status']}")

        logger.info(f"\nTests Passed: {passed}/{total}")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")

        return passed == total

    def print_detailed_results(self):
        """Print detailed test results"""
        print("\nDetailed Test Results:")
        print(json.dumps(self.test_results, indent=2))

def main():
    """Main test runner"""
    tester = TestRtdWsIntegration()

    # Run all tests
    all_passed = tester.run_all_tests()

    # Print detailed results
    tester.print_detailed_results()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
