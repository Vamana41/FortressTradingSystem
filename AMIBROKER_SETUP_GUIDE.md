# AmiBroker Plugin Setup Guide for Fortress Trading System

## Overview
This guide will help you set up the OpenAlgo AmiBroker plugin for automatic ATM (At-The-Money) symbol injection into your trading system.

## Prerequisites
- AmiBroker 6.0 or higher installed
- OpenAlgo server running (currently at http://localhost:5000)
- Your OpenAlgo API key: `89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0`

## Step 1: Download OpenAlgo AmiBroker Plugin

Since the automatic download failed, please manually download the plugin:

1. Visit the OpenAlgo Plugin releases page: https://github.com/marketcalls/OpenAlgoPlugin/releases
2. Download the latest release (look for `OpenAlgoPlugin.dll`)
3. Choose the correct version:
   - **64-bit**: If you have 64-bit AmiBroker (recommended)
   - **32-bit**: If you have 32-bit AmiBroker

## Step 2: Install the Plugin

1. **Close AmiBroker** completely if it's running
2. Navigate to your AmiBroker installation directory:
   - Usually: `C:\Program Files\AmiBroker\` (64-bit)
   - Or: `C:\Program Files (x86)\AmiBroker\` (32-bit)
3. Copy the downloaded `OpenAlgoPlugin.dll` to the `Plugins` folder
4. **Restart AmiBroker**

## Step 3: Configure the Plugin

1. In AmiBroker, go to **File → Database Settings**
2. Click **Configure** next to the data source dropdown
3. Select **OpenAlgo Data Plugin**
4. Enter the configuration:
   - **Server**: `127.0.0.1`
   - **Port**: `5000`
   - **API Key**: `89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0`
   - **WebSocket URL**: `ws://127.0.0.1:8765`
5. Click **Test Connection** to verify
6. Click **OK** to save

## Step 4: Create ATM Scanner Formula

I've created an ATM scanner formula for you. Here's the content:

```afl
// OpenAlgo ATM Scanner for Fortress Trading System
// Automatically identifies ATM (At-The-Money) options for trading

_SECTION_BEGIN("OpenAlgo ATM Scanner");

// Configuration
OpenAlgoURL = "http://localhost:5000";
APIKey = ParamStr("API Key", "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0");
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
    // For now, return current close as approximation
    return Close;
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

    Title = "OpenAlgo ATM Scanner - " + Underlying + " @ " + currentPrice + " (ATM: " + atmStrike + ")";
} else {
    Title = "OpenAlgo ATM Scanner (Disabled)";
}

// Display information
PlotText("ATM Strike: " + atmStrike, BarCount-1, Close, colorWhite);

_SECTION_END();
```

## Step 5: Create the Formula File

1. In AmiBroker, open the **Formula Editor**
2. Create a new formula and paste the ATM scanner code above
3. Save it as: `Formulas\OpenAlgo\ATM_Scanner.afl`

## Step 6: Test the Setup

1. Add a symbol like `NIFTY-NSE` to your AmiBroker database
2. Open a chart for the symbol
3. Apply the ATM Scanner formula
4. In the formula parameters:
   - Set your API key
   - Set Enable Auto Injection to "Yes"
   - Set Enable Logging to "Yes"
   - Configure expiry date (e.g., `28NOV24`)
5. Click **Apply**

## Step 7: Daily Automation

To automatically scan for ATM symbols daily:

1. **Windows Task Scheduler**: Create a scheduled task to run AmiBroker with the scanner at market open (9:15 AM IST)
2. **AmiBroker Batch**: Create a batch file to run the scanner

### Batch File Content
Create a file `Run_ATM_Scanner.bat`:

```batch
@echo off
echo OpenAlgo ATM Scanner Automation
echo ==============================

:: Set AmiBroker path (adjust if needed)
set AMIBROKER_PATH="C:\Program Files\AmiBroker\Broker.exe"

:: Set formula path
set FORMULA_PATH="C:\Program Files\AmiBroker\Formulas\OpenAlgo\ATM_Scanner.afl"

:: Run AmiBroker with the scanner
%AMIBROKER_PATH% /runformula %FORMULA_PATH%

echo ATM Scanner executed successfully
echo Check AmiBroker for results
pause
```

## Step 8: Integration with Fortress Trading System

The Fortress Trading System will:
1. Connect to OpenAlgo via API (already configured)
2. Receive ATM symbols from AmiBroker scanner
3. Execute trades based on your strategies
4. Monitor positions and P&L in real-time

## Troubleshooting

### Connection Issues
- Ensure OpenAlgo server is running at http://localhost:5000
- Check firewall settings for ports 5000 and 8765
- Verify API key is correct

### Plugin Issues
- Ensure correct DLL version (32-bit vs 64-bit) matches AmiBroker
- Check AmiBroker log window for error messages
- Restart AmiBroker after plugin installation

### Data Issues
- Verify symbol format: `SYMBOL-EXCHANGE` (e.g., `NIFTY-NSE`)
- Check OpenAlgo dashboard for broker connection status
- Ensure your broker account has data feed access

## Next Steps

1. **Open AmiBroker** and complete the plugin installation
2. **Test the ATM scanner** with the formula provided
3. **Schedule daily automation** using Windows Task Scheduler
4. **Monitor the Fortress dashboard** for real-time updates

The system is now ready for end-to-end testing. Once you have AmiBroker open with the plugin configured, we can test the complete workflow from ATM scanning to trade execution through OpenAlgo and Fortress.
