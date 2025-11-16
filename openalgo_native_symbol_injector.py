#!/usr/bin/env python3
"""
OpenAlgo Native Symbol Injector
Uses OpenAlgo's native API to automatically inject symbols into AmiBroker
Follows OpenAlgo documentation strictly for symbol injection
"""

import asyncio
import websockets
import json
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OpenAlgoNativeInjector')

class OpenAlgoNativeInjector:
    def __init__(self):
        self.api_key = '703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b'
        self.base_url = 'http://127.0.0.1:5000/api/v1'
        self.ws_url = 'ws://127.0.0.1:8765'
        self.websocket = None
        
        # All symbols from your original system
        self.all_symbols = [
            "SBIN", "RELIANCE", "TCS", "INFY", "ITC",
            "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "NICKEL"
        ]
        
        # ATM options placeholders
        self.atm_symbols = []
        
    async def get_atm_options(self):
        """Get ATM options using OpenAlgo native OptionSymbol API"""
        try:
            # Calculate next expiry date (last Thursday of current month)
            from datetime import datetime, timedelta
            import calendar
            
            today = datetime.now()
            last_day = calendar.monthrange(today.year, today.month)[1]
            last_thursday = last_day - ((last_day - calendar.THURSDAY) % 7)
            
            if last_thursday < today.day:
                # Next month
                if today.month == 12:
                    next_month = 1
                    next_year = today.year + 1
                else:
                    next_month = today.month + 1
                    next_year = today.year
                last_day = calendar.monthrange(next_year, next_month)[1]
                last_thursday = last_day - ((last_day - calendar.THURSDAY) % 7)
                expiry_date = f"{last_thursday:02d}{calendar.month_abbr[next_month].upper()}{str(next_year)[2:]}"
            else:
                expiry_date = f"{last_thursday:02d}{calendar.month_abbr[today.month].upper()}{str(today.year)[2:]}"
            
            logger.info(f"Getting ATM options for expiry: {expiry_date}")
            
            # Get NIFTY ATM CE
            nifty_ce_data = {
                "apikey": self.api_key,
                "strategy": "nifty_atm",
                "underlying": "NIFTY",
                "exchange": "NSE_INDEX",
                "expiry_date": expiry_date,
                "strike_int": 50,
                "offset": "ATM",
                "option_type": "CE"
            }
            
            response = requests.post(f"{self.base_url}/optionsymbol", json=nifty_ce_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    nifty_ce = result.get("symbol")
                    logger.info(f"NIFTY ATM CE: {nifty_ce}")
                    self.atm_symbols.append({"symbol": nifty_ce, "exchange": "NFO"})
                    
                    # Get NIFTY ATM PE
                    nifty_pe_data = nifty_ce_data.copy()
                    nifty_pe_data["option_type"] = "PE"
                    response = requests.post(f"{self.base_url}/optionsymbol", json=nifty_pe_data, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            nifty_pe = result.get("symbol")
                            logger.info(f"NIFTY ATM PE: {nifty_pe}")
                            self.atm_symbols.append({"symbol": nifty_pe, "exchange": "NFO"})
            
            # Get BANKNIFTY ATM CE
            banknifty_ce_data = {
                "apikey": self.api_key,
                "strategy": "banknifty_atm",
                "underlying": "BANKNIFTY",
                "exchange": "NSE_INDEX",
                "expiry_date": expiry_date,
                "strike_int": 100,
                "offset": "ATM",
                "option_type": "CE"
            }
            
            response = requests.post(f"{self.base_url}/optionsymbol", json=banknifty_ce_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    banknifty_ce = result.get("symbol")
                    logger.info(f"BANKNIFTY ATM CE: {banknifty_ce}")
                    self.atm_symbols.append({"symbol": banknifty_ce, "exchange": "NFO"})
                    
                    # Get BANKNIFTY ATM PE
                    banknifty_pe_data = banknifty_ce_data.copy()
                    banknifty_pe_data["option_type"] = "PE"
                    response = requests.post(f"{self.base_url}/optionsymbol", json=banknifty_pe_data, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            banknifty_pe = result.get("symbol")
                            logger.info(f"BANKNIFTY ATM PE: {banknifty_pe}")
                            self.atm_symbols.append({"symbol": banknifty_pe, "exchange": "NFO"})
                            
        except Exception as e:
            logger.error(f"ATM options error: {e}")
    
    async def connect_websocket(self):
        """Connect to OpenAlgo WebSocket"""
        try:
            logger.info(f"Connecting to OpenAlgo WebSocket at {self.ws_url}...")
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("✅ Connected to OpenAlgo WebSocket!")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            return False
    
    async def inject_symbol(self, symbol, exchange="NSE"):
        """Inject a single symbol using OpenAlgo native API"""
        try:
            # Use OpenAlgo's native symbol injection method
            injection_data = {
                "apikey": self.api_key,
                "action": "add_symbol",
                "exchange": exchange,
                "symbol": symbol
            }
            
            logger.info(f"Injecting {exchange}:{symbol} into AmiBroker...")
            
            # Send through WebSocket for real-time injection
            if self.websocket:
                await self.websocket.send(json.dumps(injection_data))
                logger.info(f"✅ Injected {exchange}:{symbol} via WebSocket")
                return True
            else:
                logger.error("❌ WebSocket not connected")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to inject {exchange}:{symbol}: {e}")
            return False
    
    async def inject_all_symbols(self):
        """Inject all symbols using native OpenAlgo methods"""
        logger.info("="*60)
        logger.info("OPENALGO NATIVE SYMBOL INJECTOR")
        logger.info("="*60)
        
        # Get ATM options first
        await self.get_atm_options()
        
        # All symbols to inject
        all_symbols_to_inject = []
        
        # Add equity symbols
        for symbol in self.all_symbols:
            if symbol in ["CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "NICKEL"]:
                # MCX commodities
                all_symbols_to_inject.append({"symbol": symbol, "exchange": "MCX"})
            else:
                # NSE stocks
                all_symbols_to_inject.append({"symbol": symbol, "exchange": "NSE"})
        
        # Add ATM options
        for atm_option in self.atm_symbols:
            all_symbols_to_inject.append(atm_option)
        
        logger.info(f"Injecting {len(all_symbols_to_inject)} symbols:")
        for symbol_info in all_symbols_to_inject:
            logger.info(f"  - {symbol_info['exchange']}:{symbol_info['symbol']}")
        
        # Connect to WebSocket
        if not await self.connect_websocket():
            logger.error("❌ Failed to connect to OpenAlgo WebSocket")
            return
        
        # Inject all symbols
        success_count = 0
        for symbol_info in all_symbols_to_inject:
            if await self.inject_symbol(symbol_info["symbol"], symbol_info["exchange"]):
                success_count += 1
            await asyncio.sleep(0.1)  # Small delay between injections
        
        logger.info(f"✅ Successfully injected {success_count}/{len(all_symbols_to_inject)} symbols")
        
        if success_count > 0:
            logger.info("🎉 SYMBOLS INJECTED INTO AMIBROKER!")
            logger.info("✅ Check AmiBroker - symbols should now be available!")
            logger.info("✅ OpenAlgo will now feed real-time data for all injected symbols!")
            
            # Keep connection alive
            await self.keep_alive()
        else:
            logger.error("❌ Failed to inject any symbols")
    
    async def keep_alive(self):
        """Keep WebSocket connection alive"""
        logger.info("Keeping connection alive for symbol data feed...")
        try:
            while True:
                # Send heartbeat every 30 seconds
                await asyncio.sleep(30)
                if self.websocket:
                    await self.websocket.send(json.dumps({"action": "ping"}))
                    logger.debug("Heartbeat sent")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("WebSocket connection closed")

async def main():
    """Main function"""
    injector = OpenAlgoNativeInjector()
    await injector.inject_all_symbols()

if __name__ == "__main__":
    asyncio.run(main())