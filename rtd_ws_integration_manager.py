#!/usr/bin/env python3
"""
Rtd_Ws_AB_plugin Integration for Fortress Trading System

This module integrates your battle-tested Rtd_Ws_AB_plugin method with Fortress,
using the WsRTD.dll and your existing fyers_client and relay server architecture.
"""

import asyncio
import json
import logging
import websockets
import threading
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import os

# Import token sharing manager
from token_sharing_manager import TokenSharingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rtd_ws_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class MarketDataPoint:
    """Market data point from Rtd_Ws_AB_plugin"""
    symbol: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    bid_price: float = 0.0
    ask_price: float = 0.0
    open_interest: int = 0

class RtdWsIntegrationManager:
    """Manages integration between Rtd_Ws_AB_plugin and Fortress Trading System"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.fyers_client_path = self.base_dir / "fyers_client_Two_expiries - Copy.py.txt"
        self.relay_server_path = self.base_dir / "fyers_gem_serveroptions.py"
        self.wsrtd_dll_path = self.base_dir / "WsRTD.dll"
        
        # Token sharing manager
        self.token_manager = TokenSharingManager()
        
        # Process management
        self.fyers_process = None
        self.relay_process = None
        self.fortress_process = None
        
        # Data management
        self.market_data_cache: Dict[str, MarketDataPoint] = {}
        self.subscribers: List[Callable] = []
        self.data_thread = None
        self.running = False
        
        # WebSocket connections
        self.websocket_clients = set()
        self.relay_websocket = None
        
        # Configuration
        self.config = self.load_configuration()
        
    def load_configuration(self) -> Dict:
        """Load integration configuration"""
        default_config = {
            "fyers": {
                "app_id": os.getenv("FYERS_APP_ID", ""),
                "secret_key": os.getenv("FYERS_SECRET_KEY", ""),
                "redirect_uri": os.getenv("FYERS_REDIRECT_URI", ""),
                "auth_code": os.getenv("FYERS_AUTH_CODE", "")
            },
            "relay_server": {
                "port": 10102,
                "use_fake_data": False,
                "max_size": 16 * 1024 * 1024  # 16 MiB
            },
            "fortress": {
                "redis_url": "redis://localhost:6379",
                "event_bus_port": 6379,
                "dashboard_port": 8000
            },
            "paths": {
                "fyers_log_path": r"C:\AmiPyScripts\fyers_logs",
                "amibroker_plugin_path": r"C:\Program Files (x86)\AmiBroker\Plugins",
                "atm_data_path": r"C:\AmiPyScripts\atm_data"
            },
            "atm_scanner": {
                "enabled": True,
                "update_interval": 300,  # 5 minutes
                "symbols": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
                "expiry_selection": "weekly"  # weekly, monthly
            }
        }
        
        config_file = self.base_dir / "rtd_ws_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults
                    for key, value in loaded_config.items():
                        if key in default_config:
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        return default_config
    
    def save_configuration(self):
        """Save configuration"""
        config_file = self.base_dir / "rtd_ws_config.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def check_prerequisites(self) -> bool:
        """Check if all required files and dependencies are available"""
        logger.info("Checking prerequisites...")
        
        # Check files
        required_files = [
            self.fyers_client_path,
            self.relay_server_path,
            self.wsrtd_dll_path
        ]
        
        missing_files = []
        for file_path in required_files:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            logger.error(f"Missing required files: {missing_files}")
            return False
        
        # Check WsRTD.dll in AmiBroker plugins
        plugin_path = Path(self.config["paths"]["amibroker_plugin_path"]) / "WsRTD.dll"
        if not plugin_path.exists():
            logger.warning(f"WsRTD.dll not found in AmiBroker plugins folder")
            logger.info(f"Please copy {self.wsrtd_dll_path} to {plugin_path}")
            return False
        
        # Check Python dependencies
        try:
            import websockets
            import asyncio
            import fyers_apiv3
        except ImportError as e:
            logger.error(f"Missing Python dependency: {e}")
            return False
        
        logger.info("All prerequisites satisfied")
        return True
    
    def setup_environment(self):
        """Setup environment variables and paths"""
        # First, sync tokens from OpenAlgo
        logger.info("Syncing tokens from OpenAlgo...")
        sync_result = self.token_manager.sync_tokens()
        
        if sync_result['status'] == 'success':
            logger.info("Token sync successful, reloading configuration")
            # Reload configuration to get updated token
            self.config = self.load_configuration()
        else:
            logger.warning(f"Token sync failed: {sync_result['message']}")
            logger.info("Using existing configuration")
        
        # Set Fyers credentials
        fyers_config = self.config["fyers"]
        os.environ["FYERS_APP_ID"] = fyers_config["app_id"]
        os.environ["FYERS_SECRET_KEY"] = fyers_config["secret_key"]
        os.environ["FYERS_REDIRECT_URI"] = fyers_config["redirect_uri"]
        os.environ["FYERS_AUTH_CODE"] = fyers_config.get("auth_code", "")
        
        # Set access token if available
        if "access_token" in fyers_config:
            os.environ["FYERS_ACCESS_TOKEN"] = fyers_config["access_token"]
            logger.info("Fyers access token set from OpenAlgo")
        
        # Create necessary directories
        for path_key in ["fyers_log_path", "atm_data_path"]:
            path = Path(self.config["paths"][path_key])
            path.mkdir(parents=True, exist_ok=True)
        
        logger.info("Environment setup completed")
    
    def start_fyers_client(self) -> bool:
        """Start the Fyers client (your battle-tested version)"""
        try:
            logger.info("Starting Fyers client...")
            
            # Start fyers_client_Two_expiries - Copy.py.txt
            cmd = [sys.executable, str(self.fyers_client_path)]
            
            self.fyers_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.base_dir)
            )
            
            # Wait a bit to check if it starts successfully
            time.sleep(3)
            
            if self.fyers_process.poll() is None:
                logger.info("Fyers client started successfully")
                return True
            else:
                stdout, stderr = self.fyers_process.communicate()
                logger.error(f"Fyers client failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting Fyers client: {e}")
            return False
    
    def start_relay_server(self) -> bool:
        """Start the relay server (your battle-tested version)"""
        try:
            logger.info("Starting relay server...")
            
            # Start fyers_gem_serveroptions.py
            cmd = [sys.executable, str(self.relay_server_path)]
            
            self.relay_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.base_dir)
            )
            
            # Wait a bit to check if it starts successfully
            time.sleep(3)
            
            if self.relay_process.poll() is None:
                logger.info("Relay server started successfully")
                return True
            else:
                stdout, stderr = self.relay_process.communicate()
                logger.error(f"Relay server failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting relay server: {e}")
            return False
    
    def start_fortress_trading_system(self) -> bool:
        """Start the Fortress Trading System"""
        try:
            logger.info("Starting Fortress Trading System...")
            
            # Start fortress main.py
            fortress_path = self.base_dir / "fortress" / "src" / "fortress" / "main.py"
            if not fortress_path.exists():
                logger.error(f"Fortress main.py not found at {fortress_path}")
                return False
            
            cmd = [sys.executable, str(fortress_path), "--test-mode"]
            
            self.fortress_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.base_dir)
            )
            
            # Wait a bit to check if it starts successfully
            time.sleep(5)
            
            if self.fortress_process.poll() is None:
                logger.info("Fortress Trading System started successfully")
                return True
            else:
                stdout, stderr = self.fortress_process.communicate()
                logger.error(f"Fortress failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting Fortress: {e}")
            return False
    
    def connect_to_relay_websocket(self) -> bool:
        """Connect to the relay server WebSocket"""
        try:
            relay_port = self.config["relay_server"]["port"]
            ws_url = f"ws://localhost:{relay_port}"
            
            logger.info(f"Connecting to relay WebSocket at {ws_url}")
            
            # This will be handled by the relay server's WebSocket connection
            # For now, we'll monitor the relay server output
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to relay WebSocket: {e}")
            return False
    
    def parse_market_data(self, data: str) -> Optional[MarketDataPoint]:
        """Parse market data from relay server output"""
        try:
            # Parse JSON data from relay server
            if data.startswith('[{') and data.endswith('}]'):
                market_data = json.loads(data)
                if market_data and len(market_data) > 0:
                    data_point = market_data[0]
                    
                    return MarketDataPoint(
                        symbol=data_point.get('symbol', ''),
                        timestamp=datetime.now(),
                        open_price=float(data_point.get('open', 0)),
                        high_price=float(data_point.get('high', 0)),
                        low_price=float(data_point.get('low', 0)),
                        close_price=float(data_point.get('close', 0)),
                        volume=int(data_point.get('volume', 0)),
                        bid_price=float(data_point.get('bid', 0)),
                        ask_price=float(data_point.get('ask', 0)),
                        open_interest=int(data_point.get('oi', 0))
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing market data: {e}")
            return None
    
    def process_market_data(self, data_point: MarketDataPoint):
        """Process and distribute market data"""
        try:
            # Update cache
            self.market_data_cache[data_point.symbol] = data_point
            
            # Notify subscribers
            for callback in self.subscribers:
                try:
                    callback(data_point)
                except Exception as e:
                    logger.error(f"Error notifying subscriber: {e}")
            
            # Log significant data
            if data_point.symbol in ["NIFTY", "BANKNIFTY"]:
                logger.info(f"Market data: {data_point.symbol} @ {data_point.close_price}")
            
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    def monitor_process_output(self, process: subprocess.Popen, process_name: str):
        """Monitor process output for market data"""
        try:
            while self.running and process.poll() is None:
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    
                    # Look for market data patterns
                    if line.startswith('[{') and line.endswith('}]'):
                        data_point = self.parse_market_data(line)
                        if data_point:
                            self.process_market_data(data_point)
                    
                    # Log important messages
                    if any(keyword in line.lower() for keyword in ["error", "warning", "connected", "disconnected"]):
                        logger.info(f"[{process_name}] {line}")
                    
        except Exception as e:
            logger.error(f"Error monitoring {process_name}: {e}")
    
    def start_data_monitoring(self):
        """Start monitoring processes for market data"""
        self.running = True
        
        # Start monitoring threads
        if self.fyers_process:
            fyers_thread = threading.Thread(
                target=self.monitor_process_output,
                args=(self.fyers_process, "FyersClient"),
                daemon=True
            )
            fyers_thread.start()
        
        if self.relay_process:
            relay_thread = threading.Thread(
                target=self.monitor_process_output,
                args=(self.relay_process, "RelayServer"),
                daemon=True
            )
            relay_thread.start()
        
        logger.info("Data monitoring started")
    
    def subscribe_to_market_data(self, callback: Callable):
        """Subscribe to market data updates"""
        self.subscribers.append(callback)
        logger.info(f"Market data subscriber added. Total subscribers: {len(self.subscribers)}")
    
    def get_market_data(self, symbol: str) -> Optional[MarketDataPoint]:
        """Get latest market data for a symbol"""
        return self.market_data_cache.get(symbol)
    
    def get_all_symbols(self) -> List[str]:
        """Get all available symbols"""
        return list(self.market_data_cache.keys())
    
    def generate_atm_scanner_data(self) -> Dict:
        """Generate ATM scanner data for options trading"""
        try:
            atm_config = self.config["atm_scanner"]
            if not atm_config["enabled"]:
                return {}
            
            # Get current market data for underlying symbols
            atm_data = {}
            
            for symbol in atm_config["symbols"]:
                market_data = self.get_market_data(symbol)
                if market_data:
                    current_price = market_data.close_price
                    atm_strike = round(current_price / 50) * 50  # Round to nearest 50
                    
                    # Generate strikes around ATM
                    strikes = [atm_strike - 200, atm_strike - 150, atm_strike - 100, 
                              atm_strike - 50, atm_strike, atm_strike + 50, 
                              atm_strike + 100, atm_strike + 150, atm_strike + 200]
                    
                    atm_data[symbol] = {
                        "underlying_price": current_price,
                        "atm_strike": atm_strike,
                        "strikes": strikes,
                        "timestamp": datetime.now().isoformat()
                    }
            
            return atm_data
            
        except Exception as e:
            logger.error(f"Error generating ATM scanner data: {e}")
            return {}
    
    def get_integration_status(self) -> Dict:
        """Get current integration status"""
        # Get token sharing status
        token_info = self.token_manager.get_current_token_info()
        
        return {
            "running": self.running,
            "token_sharing": token_info,
            "fyers_client": {
                "running": self.fyers_process is not None and self.fyers_process.poll() is None,
                "pid": self.fyers_process.pid if self.fyers_process else None
            },
            "relay_server": {
                "running": self.relay_process is not None and self.relay_process.poll() is None,
                "pid": self.relay_process.pid if self.relay_process else None
            },
            "fortress_system": {
                "running": self.fortress_process is not None and self.fortress_process.poll() is None,
                "pid": self.fortress_process.pid if self.fortress_process else None
            },
            "market_data": {
                "symbols": len(self.market_data_cache),
                "subscribers": len(self.subscribers)
            },
            "atm_scanner": {
                "enabled": self.config["atm_scanner"]["enabled"],
                "symbols": self.config["atm_scanner"]["symbols"]
            }
        }
    
    def start_integration(self) -> bool:
        """Start the complete Rtd_Ws_AB_plugin integration"""
        try:
            logger.info("Starting Rtd_Ws_AB_plugin integration...")
            
            # Check prerequisites
            if not self.check_prerequisites():
                return False
            
            # Setup environment
            self.setup_environment()
            
            # Start components in sequence
            success = True
            
            # 1. Start Fyers client (your battle-tested version)
            if success:
                success = self.start_fyers_client()
                if not success:
                    logger.error("Failed to start Fyers client")
            
            # 2. Start relay server (your battle-tested version)
            if success:
                success = self.start_relay_server()
                if not success:
                    logger.error("Failed to start relay server")
            
            # 3. Start Fortress Trading System
            if success:
                success = self.start_fortress_trading_system()
                if not success:
                    logger.error("Failed to start Fortress Trading System")
            
            # 4. Connect to relay WebSocket
            if success:
                success = self.connect_to_relay_websocket()
                if not success:
                    logger.error("Failed to connect to relay WebSocket")
            
            # 5. Start data monitoring
            if success:
                self.start_data_monitoring()
                logger.info("Rtd_Ws_AB_plugin integration started successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting integration: {e}")
            return False
    
    def stop_integration(self):
        """Stop the integration"""
        logger.info("Stopping Rtd_Ws_AB_plugin integration...")
        
        self.running = False
        
        # Stop processes
        processes = [
            (self.fyers_process, "Fyers client"),
            (self.relay_process, "Relay server"),
            (self.fortress_process, "Fortress Trading System")
        ]
        
        for process, name in processes:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info(f"{name} stopped")
                except Exception as e:
                    logger.error(f"Error stopping {name}: {e}")
                    try:
                        process.kill()
                    except:
                        pass
        
        logger.info("Rtd_Ws_AB_plugin integration stopped")

def main():
    """Main function for testing the integration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Rtd_Ws_AB_plugin Integration for Fortress")
    parser.add_argument("--start", action="store_true", help="Start the integration")
    parser.add_argument("--stop", action="store_true", help="Stop the integration")
    parser.add_argument("--status", action="store_true", help="Show integration status")
    parser.add_argument("--test-atm", action="store_true", help="Test ATM scanner")
    
    args = parser.parse_args()
    
    integration = RtdWsIntegrationManager()
    
    if args.start:
        success = integration.start_integration()
        if success:
            print("Integration started successfully")
            
            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping integration...")
                integration.stop_integration()
        else:
            print("Failed to start integration")
            return 1
    
    elif args.stop:
        integration.stop_integration()
        print("Integration stopped")
    
    elif args.status:
        status = integration.get_integration_status()
        print(json.dumps(status, indent=2))
    
    elif args.test_atm:
        atm_data = integration.generate_atm_scanner_data()
        print(json.dumps(atm_data, indent=2))
    
    else:
        parser.print_help()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())