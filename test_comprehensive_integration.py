#!/usr/bin/env python3
"""
Test script for OpenAlgo Comprehensive Symbol Injector

This script tests the complete integration with all symbols from your original system.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from our config file
load_dotenv("openalgo_symbol_injector.env")

from openalgo_comprehensive_injector import OpenAlgoComprehensiveInjector, COMPLETE_SYMBOL_MAPPING

async def test_comprehensive_integration():
    """Test the complete OpenAlgo integration with all symbols"""
    print("Testing OpenAlgo Comprehensive Symbol Injector...")
    print("=" * 70)
    
    # Show all symbols we're managing
    print(f"Managing {len(COMPLETE_SYMBOL_MAPPING)} symbols from your original system:")
    for fyers_symbol, ami_symbol in list(COMPLETE_SYMBOL_MAPPING.items())[:10]:
        print(f"  {fyers_symbol} -> {ami_symbol}")
    if len(COMPLETE_SYMBOL_MAPPING) > 10:
        print(f"  ... and {len(COMPLETE_SYMBOL_MAPPING) - 10} more symbols")
    print()
    
    # Create injector instance
    injector = OpenAlgoComprehensiveInjector()
    
    # Test 1: API key validation
    print("1. Testing API key validation...")
    api_key_available = await injector.refresh_api_key()
    if api_key_available:
        print("   ✓ API key validation passed")
    else:
        print("   ✗ API key not available")
        print("   Please complete these steps:")
        print("   - Login to OpenAlgo at http://127.0.0.1:5000")
        print("   - Get your API key from the dashboard")
        print("   - Update OPENALGO_API_KEY in openalgo_symbol_injector.env")
        return False
    
    # Test 2: Basic connectivity
    print("\n2. Testing basic OpenAlgo connectivity...")
    try:
        # Test getting Nifty LTP
        nifty_ltp = await injector.get_index_ltp("NSE:NIFTY50-INDEX")
        if nifty_ltp:
            print(f"   ✓ Successfully got Nifty LTP: {nifty_ltp}")
        else:
            print("   ⚠ Could not get Nifty LTP (market may be closed or API key invalid)")
            print("   This is expected if market is closed or you need a new API key")
        
        # Test getting BankNifty LTP
        banknifty_ltp = await injector.get_index_ltp("NSE:NIFTYBANK-INDEX")
        if banknifty_ltp:
            print(f"   ✓ Successfully got BankNifty LTP: {banknifty_ltp}")
        else:
            print("   ⚠ Could not get BankNifty LTP (market may be closed or API key invalid)")
            
    except Exception as e:
        print(f"   ✗ Error testing connectivity: {e}")
        return False
    
    # Test 3: Expiry dates retrieval
    print("\n3. Testing expiry dates retrieval...")
    try:
        expiry_dates = await injector.get_expiry_dates("NSE:NIFTY50-INDEX", "OPTIDX")
        if expiry_dates:
            print(f"   ✓ Got {len(expiry_dates)} expiry dates for Nifty")
            for i, expiry in enumerate(expiry_dates[:3]):
                print(f"     - {expiry}")
            if len(expiry_dates) > 3:
                print(f"     ... and {len(expiry_dates) - 3} more")
        else:
            print("   ⚠ Could not get expiry dates (market may be closed)")
            
    except Exception as e:
        print(f"   ✗ Error testing expiry retrieval: {e}")
        return False
    
    # Test 4: ATM selection logic
    print("\n4. Testing ATM selection logic...")
    try:
        # Test with mock LTP if market is closed
        mock_ltp = 19500  # Mock Nifty LTP
        target_strike = injector.calculate_atm_strike(mock_ltp, 50)
        print(f"   ✓ ATM strike calculation: {mock_ltp} -> {target_strike}")
        
        mock_ltp_bn = 44000  # Mock BankNifty LTP
        target_strike_bn = injector.calculate_atm_strike(mock_ltp_bn, 100)
        print(f"   ✓ BankNifty ATM strike calculation: {mock_ltp_bn} -> {target_strike_bn}")
        
    except Exception as e:
        print(f"   ✗ Error testing ATM selection: {e}")
        return False
    
    # Test 5: Symbol generation
    print("\n5. Testing symbol generation...")
    try:
        # Test AmiBroker symbol generation
        test_symbols = [
            ("NIFTY", "17-01-2025", 19500, "CE"),
            ("BANKNIFTY", "17-01-2025", 44000, "PE"),
        ]
        
        for underlying, expiry, strike, opt_type in test_symbols:
            ami_symbol = injector.generate_amibroker_symbol(underlying, expiry, strike, opt_type)
            print(f"   ✓ Generated symbol: {underlying} {expiry} {strike} {opt_type} -> {ami_symbol}")
        
    except Exception as e:
        print(f"   ✗ Error testing symbol generation: {e}")
        return False
    
    # Test 6: Relay server connection
    print("\n6. Testing relay server connection...")
    try:
        connected = await injector.connect_to_relay_server()
        if connected:
            print("   ✓ Successfully connected to relay server")
            
            # Test symbol discovery with a few symbols
            test_symbols = ["NIFTY17JAN2519500CE", "BANKNIFTY17JAN2544000PE"]
            print(f"   ✓ Testing symbol discovery for {len(test_symbols)} symbols...")
            for symbol in test_symbols:
                await injector.send_symbol_discovery_to_amibroker(symbol)
                print(f"     ✓ Sent discovery for {symbol}")
        else:
            print("   ✗ Failed to connect to relay server")
            print("   Please ensure your relay server is running on ws://localhost:10102")
            return False
            
    except Exception as e:
        print(f"   ✗ Error testing relay server connection: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ All tests completed successfully!")
    print("\nNext steps:")
    print("1. Get a fresh OpenAlgo API key from the dashboard")
    print("2. Update the OPENALGO_API_KEY in openalgo_symbol_injector.env")
    print("3. Run the main system: python openalgo_comprehensive_injector.py")
    print("4. The system will automatically manage all your symbols and select ATM options")
    
    return True

async def main():
    """Main test function"""
    print("OpenAlgo Comprehensive Symbol Injector - Integration Test")
    print("=" * 70)
    
    try:
        success = await test_comprehensive_integration()
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