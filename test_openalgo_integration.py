#!/usr/bin/env python3
"""
Test script for OpenAlgo Symbol Injector

This script tests the integration with OpenAlgo API and relay server
to ensure automatic symbol injection works correctly.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from our config file
load_dotenv("openalgo_symbol_injector.env")

from openalgo_symbol_injector import OpenAlgoSymbolInjector

async def test_integration():
    """Test the OpenAlgo integration"""
    print("Testing OpenAlgo Symbol Injector Integration...")
    print("=" * 60)
    
    # Create injector instance
    injector = OpenAlgoSymbolInjector()
    
    # Test API key availability
    print("1. Testing API key access...")
    api_key_available = await injector.get_api_key_from_fortress()
    if api_key_available:
        print("   ✓ API key is available")
    else:
        print("   ✗ API key is not available")
        print("   Please ensure you have set the OPENALGO_API_KEY environment variable")
        print("   or that the Fortress API key manager has the key stored.")
        return False
    
    # Test OpenAlgo connectivity
    print("\n2. Testing OpenAlgo connectivity...")
    try:
        # Test getting Nifty LTP
        nifty_ltp = await injector.get_index_ltp("NSE:NIFTY50-INDEX")
        if nifty_ltp:
            print(f"   ✓ Successfully got Nifty LTP: {nifty_ltp}")
        else:
            print("   ✗ Failed to get Nifty LTP")
            return False
        
        # Test getting BankNifty LTP
        banknifty_ltp = await injector.get_index_ltp("NSE:NIFTYBANK-INDEX")
        if banknifty_ltp:
            print(f"   ✓ Successfully got BankNifty LTP: {banknifty_ltp}")
        else:
            print("   ✗ Failed to get BankNifty LTP")
            return False
            
    except Exception as e:
        print(f"   ✗ Error testing OpenAlgo connectivity: {e}")
        return False
    
    # Test option chain retrieval
    print("\n3. Testing option chain retrieval...")
    try:
        nifty_option_chain = await injector.get_option_chain("NSE:NIFTY50-INDEX")
        if nifty_option_chain:
            print(f"   ✓ Successfully got Nifty option chain")
            if 'expiryData' in nifty_option_chain:
                expiries = [exp.get('date') for exp in nifty_option_chain['expiryData'] if exp.get('date')]
                print(f"   ✓ Available expiries: {expiries[:2]}")  # Show first 2
            if 'optionsChain' in nifty_option_chain:
                print(f"   ✓ Option chain has {len(nifty_option_chain['optionsChain'])} strikes")
        else:
            print("   ✗ Failed to get Nifty option chain")
            return False
            
    except Exception as e:
        print(f"   ✗ Error testing option chain retrieval: {e}")
        return False
    
    # Test ATM selection logic
    print("\n4. Testing ATM selection logic...")
    try:
        # Test Nifty ATM selection
        nifty_symbols = await injector.select_and_subscribe_atm_options(
            "NSE:NIFTY50-INDEX", "NIFTY", 50
        )
        if nifty_symbols:
            print(f"   ✓ Successfully selected Nifty ATM symbols:")
            for fyers_symbol, ami_symbol in nifty_symbols.items():
                print(f"     - {fyers_symbol} -> {ami_symbol}")
        else:
            print("   ✗ Failed to select Nifty ATM symbols")
            return False
        
        # Test BankNifty ATM selection
        banknifty_symbols = await injector.select_and_subscribe_atm_options(
            "NSE:NIFTYBANK-INDEX", "BANKNIFTY", 100
        )
        if banknifty_symbols:
            print(f"   ✓ Successfully selected BankNifty ATM symbols:")
            for fyers_symbol, ami_symbol in banknifty_symbols.items():
                print(f"     - {fyers_symbol} -> {ami_symbol}")
        else:
            print("   ✗ Failed to select BankNifty ATM symbols")
            return False
            
    except Exception as e:
        print(f"   ✗ Error testing ATM selection logic: {e}")
        return False
    
    # Test relay server connection
    print("\n5. Testing relay server connection...")
    try:
        connected = await injector.connect_to_relay_server()
        if connected:
            print("   ✓ Successfully connected to relay server")
            
            # Test symbol discovery
            test_symbols = list(nifty_symbols.values()) + list(banknifty_symbols.values())
            if test_symbols:
                print(f"   ✓ Testing symbol discovery for {len(test_symbols)} symbols...")
                for symbol in test_symbols[:2]:  # Test first 2 symbols
                    await injector.send_symbol_discovery_to_amibroker(symbol)
                    print(f"     ✓ Sent discovery for {symbol}")
        else:
            print("   ✗ Failed to connect to relay server")
            print("   Please ensure your relay server is running on ws://localhost:10102")
            return False
            
    except Exception as e:
        print(f"   ✗ Error testing relay server connection: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! The integration is working correctly.")
    print("\nNext steps:")
    print("1. Set your OpenAlgo API key in the environment or Fortress API manager")
    print("2. Ensure your relay server is running on ws://localhost:10102")
    print("3. Run the main script: python openalgo_symbol_injector.py")
    print("4. The system will automatically select ATM options at 09:13:15 daily")
    
    return True

async def main():
    """Main test function"""
    print("OpenAlgo Symbol Injector - Integration Test")
    print("=" * 60)
    
    try:
        success = await test_integration()
        if success:
            print("\n🎉 Integration test completed successfully!")
            return 0
        else:
            print("\n❌ Integration test failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error during test: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)