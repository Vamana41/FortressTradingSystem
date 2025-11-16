# OpenAlgo Symbol Injector

This solution integrates OpenAlgo's data access with automatic symbol injection into AmiBroker, eliminating the need for manual symbol entry.

## Problem Solved

**Original Issue**: OpenAlgo requires manual symbol entry for options, but you need automatic symbol injection like your existing Fyers client system.

**Solution**: This bridge uses OpenAlgo's API for data access while maintaining your automatic ATM option selection and relay server communication.

## How It Works

1. **Uses OpenAlgo API** for real-time data access (via your stored API key)
2. **Automatically selects ATM options** for both Nifty and BankNifty (nearest + next expiry)
3. **Connects to your existing relay server** at `ws://localhost:10102`
4. **Injects symbols automatically** into AmiBroker without manual typing
5. **Saves daily ATM symbols** for persistence and recovery

## Key Features

- ✅ **Automatic ATM Selection**: Calculates ATM strikes based on current index LTP
- ✅ **Dual Expiry Support**: Selects both nearest and next weekly expiry options
- ✅ **OpenAlgo Integration**: Uses OpenAlgo's quotes and option chain APIs
- ✅ **Relay Server Communication**: Sends data to AmiBroker via your existing relay
- ✅ **Daily Persistence**: Saves selected symbols to JSON files
- ✅ **Scheduled Execution**: Runs automatically at 09:13:15 daily
- ✅ **Symbol Discovery**: Automatically makes AmiBroker discover new symbols

## Setup Instructions

### 1. Prerequisites

- OpenAlgo running on `http://127.0.0.1:5000`
- Your relay server running on `ws://localhost:10102`
- Python 3.7+ with required packages

### 2. Install Dependencies

```bash
pip install asyncio websockets requests pandas pytz python-dotenv
```

### 3. Configure API Key

#### Option A: Use Fortress API Key Manager (Recommended)
The system will automatically use your OpenAlgo API key from:
```
C:\Users\Admin\.fortress\api_keys.enc
```

#### Option B: Set Environment Variable
Set the API key in the environment file:
```
# Edit openalgo_symbol_injector.env
OPENALGO_API_KEY=your_openalgo_api_key_here
```

### 4. Test the Integration

Run the test script to verify everything works:
```bash
python test_openalgo_integration.py
```

This will test:
- API key access
- OpenAlgo connectivity
- Option chain retrieval
- ATM selection logic
- Relay server connection

### 5. Run the Main System

Start the automatic symbol injector:
```bash
python openalgo_symbol_injector.py
```

The system will:
- Wait until 09:13:15 for ATM selection
- Automatically select ATM options for Nifty and BankNifty
- Connect to your relay server
- Inject symbols into AmiBroker
- Save daily symbols for persistence

## Daily Workflow

1. **Manual Steps** (same as before):
   - Login to OpenAlgo with credentials
   - Login to Fyers broker through OpenAlgo
   - Get OpenAlgo API key from dashboard
   - API key is automatically stored by Fortress

2. **Automatic Steps** (new):
   - Symbol injector runs at 09:13:15 daily
   - Automatically selects ATM options
   - Injects symbols into AmiBroker via relay server
   - No manual symbol entry required!

## Symbol Format

The system generates AmiBroker symbols in your familiar format:
- **Nifty**: `NIFTY17JAN2519500CE` (17Jan25 expiry, 19500 strike, CE)
- **BankNifty**: `BANKNIFTY17JAN2544000PE` (17Jan25 expiry, 44000 strike, PE)

## File Structure

```
C:\AmiPyScripts\fyers_contracts\
├── daily_atm_symbols_2025-01-17.json  # Today's ATM symbols
├── daily_atm_symbols_2025-01-16.json  # Yesterday's symbols
└── ...

C:\AmiPyScripts\fyers_logs\
├── openalgo_symbol_injector.log        # Main system log
└── ...
```

## Troubleshooting

### Issue: API key not found
**Solution**: Ensure you've completed the manual login process and the API key is stored in Fortress.

### Issue: Relay server connection failed
**Solution**: Make sure your relay server is running on `ws://localhost:10102`

### Issue: OpenAlgo API errors
**Solution**: Verify OpenAlgo is running on `http://127.0.0.1:5000` and the API key is valid

### Issue: No symbols selected
**Solution**: Check that market is open and indices are trading during ATM selection time

## Integration with Your Existing System

This solution:
- ✅ **Preserves your existing relay server** (no changes needed)
- ✅ **Maintains your AmiBroker setup** (works with existing .dll)
- ✅ **Uses your familiar file paths** (same directories)
- ✅ **Follows your ATM selection logic** (same timing and methodology)
- ✅ **Generates compatible symbol formats** (same naming convention)

## Migration from Fyers Client

To switch from your Fyers client to this OpenAlgo integration:

1. **Stop your Fyers client** (to avoid conflicts)
2. **Start OpenAlgo** (ensure it's running and authenticated)
3. **Run the symbol injector** (this will handle the rest automatically)
4. **AmiBroker continues to work** (no changes needed on AmiBroker side)

The relay server communication remains identical, so your AmiBroker setup stays unchanged.

## Next Steps

1. **Test the integration** using the test script
2. **Verify symbol injection** in AmiBroker
3. **Monitor the logs** for the first few days
4. **Adjust timing** if needed (edit `ATM_SELECTION_TIME_STR`)

Your automatic symbol injection is now restored with OpenAlgo integration! 🎉
