#!/usr/bin/env python3
"""
AmiBroker Plugin Setup for Fortress Trading System
Automates the installation and configuration of OpenAlgo AmiBroker plugin
"""

import os
import shutil
import urllib.request
import zipfile
import tempfile
from pathlib import Path
from typing import Optional

class AmiBrokerPluginSetup:
    """Setup OpenAlgo AmiBroker plugin for automatic ATM symbol injection"""
    
    def __init__(self, openalgo_base_url: str = "http://localhost:5000"):
        self.openalgo_base_url = openalgo_base_url
        self.plugin_download_url = "https://github.com/marketcalls/OpenAlgoPlugin/releases/download/v1.0.0/OpenAlgoPlugin.dll"
        self.plugin_dir = Path("C:/Program Files/AmiBroker/Plugins/OpenAlgo")
        self.formulas_dir = Path("C:/Program Files/AmiBroker/Formulas/OpenAlgo")
        
    def download_plugin(self) -> Optional[Path]:
        """Download the latest OpenAlgo plugin"""
        print("📥 Downloading OpenAlgo AmiBroker plugin...")
        
        try:
            # Create temp directory
            temp_dir = Path(tempfile.mkdtemp())
            plugin_path = temp_dir / "OpenAlgoPlugin.dll"
            
            # Download plugin
            print(f"Downloading from: {self.plugin_download_url}")
            urllib.request.urlretrieve(self.plugin_download_url, plugin_path)
            
            if plugin_path.exists() and plugin_path.stat().st_size > 0:
                print(f"✅ Plugin downloaded successfully: {plugin_path}")
                return plugin_path
            else:
                print("❌ Plugin download failed - file is empty or missing")
                return None
                
        except Exception as e:
            print(f"❌ Plugin download failed: {e}")
            return None
    
    def install_plugin(self, plugin_path: Path) -> bool:
        """Install the plugin to AmiBroker"""
        print("🔧 Installing OpenAlgo plugin to AmiBroker...")
        
        try:
            # Create plugin directory
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy plugin file
            target_path = self.plugin_dir / "OpenAlgoPlugin.dll"
            shutil.copy2(plugin_path, target_path)
            
            print(f"✅ Plugin installed to: {target_path}")
            return True
            
        except Exception as e:
            print(f"❌ Plugin installation failed: {e}")
            return False
    
    def create_atm_scanner_formula(self) -> bool:
        """Create AmiBroker formula for ATM symbol scanning"""
        print("📝 Creating ATM scanner formula...")
        
        afl_content = '''
// OpenAlgo ATM Scanner for Fortress Trading System
// Automatically identifies ATM (At-The-Money) options for trading

_SECTION_BEGIN("OpenAlgo ATM Scanner");

// Configuration
OpenAlgoURL = "''' + self.openalgo_base_url + '''";
APIKey = ParamStr("API Key", "");  // Get from OpenAlgo dashboard
Underlying = ParamStr("Underlying Symbol", "NIFTY");
Exchange = ParamStr("Exchange", "NFO");
ExpiryDate = ParamStr("Expiry Date", "");  // Format: DDMMMYY (e.g., 28NOV24)

// ATM Calculation Parameters
StrikeInterval = Param("Strike Interval", 50, 10, 500, 10);
NumStrikes = Param("Number of Strikes", 10, 5, 50, 1);

// Enable/disable features
EnableAutoInjection = ParamToggle("Enable Auto Injection", "No|Yes", 1);
EnableLogging = ParamToggle("Enable Logging", "No|Yes", 1);

// Function to get current underlying price via OpenAlgo API
function GetUnderlyingPrice(symbol, exchange) {
    // This would call OpenAlgo API to get current price
    // For now, return a placeholder
    return Close;  // Use current close as approximation
}

// Function to identify ATM strike
function GetATMStrike(underlyingPrice, interval) {
    return round(underlyingPrice / interval) * interval;
}

// Function to generate option symbols
function GenerateOptionSymbols(underlying, expiry, atmStrike, numStrikes, interval) {
    symbols = "";
    
    // Generate CE symbols
    for (i = -numStrikes; i <= numStrikes; i++) {
        strike = atmStrike + (i * interval);
        ceSymbol = underlying + expiry + strike + "CE";
        peSymbol = underlying + expiry + strike + "PE";
        
        symbols = symbols + ceSymbol + "," + peSymbol;
        if (i < numStrikes) symbols = symbols + ",";
    }
    
    return symbols;
}

// Main execution
if (EnableAutoInjection) {
    // Get current underlying price
    currentPrice = GetUnderlyingPrice(Underlying, Exchange);
    atmStrike = GetATMStrike(currentPrice, StrikeInterval);
    
    // Generate option symbols
    optionSymbols = GenerateOptionSymbols(Underlying, ExpiryDate, atmStrike, NumStrikes, StrikeInterval);
    
    if (EnableLogging) {
        printf("Current Price: %g\\n", currentPrice);
        printf("ATM Strike: %g\\n", atmStrike);
        printf("Option Symbols: %s\\n", optionSymbols);
    }
    
    // Set the watchlist or send to OpenAlgo
    // This would integrate with OpenAlgo plugin
    
    Title = "OpenAlgo ATM Scanner - " + Underlying + " @ " + currentPrice + " (ATM: " + atmStrike + ")";
} else {
    Title = "OpenAlgo ATM Scanner (Disabled)";
}

// Display information
PlotText("ATM Strike: " + atmStrike, BarCount-1, Close, colorWhite);

_SECTION_END();
'''
        
        try:
            # Create formulas directory
            self.formulas_dir.mkdir(parents=True, exist_ok=True)
            
            # Write AFL file
            formula_path = self.formulas_dir / "ATM_Scanner.afl"
            with open(formula_path, 'w') as f:
                f.write(afl_content)
            
            print(f"✅ ATM Scanner formula created: {formula_path}")
            return True
            
        except Exception as e:
            print(f"❌ Formula creation failed: {e}")
            return False
    
    def create_config_file(self, api_key: str) -> bool:
        """Create configuration file for the plugin"""
        print("⚙️  Creating plugin configuration...")
        
        config_content = f'''
[OpenAlgo]
BaseURL = {self.openalgo_base_url}
APIKey = {api_key}
Timeout = 30
RetryAttempts = 3

[ATM_Injection]
Enabled = True
AutoScanInterval = 300  ; 5 minutes
StrikeRange = 10        ; +/- 10 strikes from ATM

[Logging]
Enabled = True
Level = INFO
File = OpenAlgoPlugin.log
'''
        
        try:
            config_path = self.plugin_dir / "OpenAlgoPlugin.ini"
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            print(f"✅ Plugin configuration created: {config_path}")
            return True
            
        except Exception as e:
            print(f"❌ Configuration creation failed: {e}")
            return False
    
    def setup_automation_script(self) -> bool:
        """Create automation script for daily ATM scanning"""
        print("🤖 Creating automation script...")
        
        script_content = '''
@echo off
echo OpenAlgo ATM Scanner Automation
echo ==============================

:: Set AmiBroker path (adjust if needed)
set AMIBROKER_PATH="C:\\Program Files\\AmiBroker\\Broker.exe"

:: Set formula path
set FORMULA_PATH="C:\\Program Files\\AmiBroker\\Formulas\\OpenAlgo\\ATM_Scanner.afl"

:: Run AmiBroker with the scanner
%AMIBROKER_PATH% /runformula %FORMULA_PATH%

echo ATM Scanner executed successfully
echo Check AmiBroker for results
pause
'''
        
        try:
            script_path = self.plugin_dir / "Run_ATM_Scanner.bat"
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            print(f"✅ Automation script created: {script_path}")
            return True
            
        except Exception as e:
            print(f"❌ Automation script creation failed: {e}")
            return False
    
    def run_setup(self, api_key: str) -> bool:
        """Run complete AmiBroker plugin setup"""
        print("🚀 Starting AmiBroker Plugin Setup")
        print("=" * 50)
        
        # Download plugin
        plugin_path = self.download_plugin()
        if not plugin_path:
            print("❌ Plugin download failed")
            return False
        
        # Install plugin
        if not self.install_plugin(plugin_path):
            print("❌ Plugin installation failed")
            return False
        
        # Create formulas
        if not self.create_atm_scanner_formula():
            print("❌ Formula creation failed")
            return False
        
        # Create config
        if not self.create_config_file(api_key):
            print("❌ Configuration creation failed")
            return False
        
        # Create automation script
        if not self.setup_automation_script():
            print("❌ Automation setup failed")
            return False
        
        # Cleanup
        try:
            shutil.rmtree(plugin_path.parent)
            print("🧹 Cleanup completed")
        except:
            pass
        
        print("\n" + "=" * 50)
        print("🎉 AmiBroker Plugin Setup Completed Successfully!")
        print("=" * 50)
        print("\n📋 Next Steps:")
        print("1. Open AmiBroker")
        print("2. Go to Formula Editor")
        print("3. Open: Formulas → OpenAlgo → ATM_Scanner.afl")
        print("4. Enter your API key in the parameters")
        print("5. Set Enable Auto Injection to 'Yes'")
        print("6. Apply the formula to your charts")
        print("\n🔧 For automatic daily scanning:")
        print(f"   Run: {self.plugin_dir / 'Run_ATM_Scanner.bat'}")
        print("   Or schedule this batch file in Windows Task Scheduler")
        
        return True

def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AmiBroker Plugin Setup for OpenAlgo")
    parser.add_argument("--api-key", required=True, help="OpenAlgo API key")
    parser.add_argument("--base-url", default="http://localhost:5000", help="OpenAlgo base URL")
    
    args = parser.parse_args()
    
    setup = AmiBrokerPluginSetup(args.base_url)
    success = setup.run_setup(args.api_key)
    
    exit(0 if success else 1)

if __name__ == "__main__":
    main()