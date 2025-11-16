# OpenAlgo Comprehensive Symbol Injector

Complete solution that integrates OpenAlgo with your full symbol mapping, including all futures, equities, and automatic ATM option selection.

## 🎯 Problem Solved

**Original Issues**:
1. OpenAlgo requires manual symbol entry for options
2. You need all symbols from your original system (not just ATM options)
3. API key needs refresh after OpenAlgo restart

**Solution**: Complete integration that maintains your full symbol mapping while adding automatic ATM option injection.

## 📋 Complete Symbol Coverage

Your original system manages these symbols:

### MCX Commodities Futures
- CRUDEOILM-FUT, GOLDPETAL-FUT, GOLDM-FUT, NATGASMINI-FUT
- SILVERMIC-FUT, ZINCMINI-FUT, ALUMINI-FUT, COPPER-FUT, LEADMINI-FUT

### NSE Index Futures
- BANKNIFTY-FUT, NIFTY-FUT

### NSE Equities
- SBIN

### Automatic ATM Options (Daily Selection)
- NIFTY ATM CE/PE (nearest + next expiry)
- BANKNIFTY ATM CE/PE (nearest + next expiry)

## 🚀 Key Features

✅ **Complete Symbol Mapping**: All your original futures and equities
✅ **Automatic ATM Selection**: Daily ATM option selection at 09:13:15
✅ **OpenAlgo Integration**: Uses OpenAlgo API for real-time data
✅ **Relay Server Compatible**: Works with your existing ws://localhost:10102
✅ **API Key Management**: Handles API key refresh automatically
✅ **Daily Persistence**: Saves ATM symbols for recovery
✅ **Symbol Discovery**: Auto-injects symbols into AmiBroker

## 🔧 Configuration

### 1. Environment Setup
```bash
# Edit openalgo_symbol_injector.env
OPENALGO_API_KEY=your_fresh_api_key_here
OPENALGO_BASE_URL=http://127.0.0.1:5000
RELAY_SERVER_URI=ws://localhost:10102
MASTER_CONTRACT_PATH=C:\\AmiPyScripts\\fyers_contracts
FYERS_LOG_PATH=C:\\AmiPyScripts\\fyers_logs
```

### 2. Prerequisites
- OpenAlgo running on http://127.0.0.1:5000
- Your relay server on ws://localhost:10102
- Python 3.7+ with packages: asyncio, websockets, requests, pandas, pytz, python-dotenv

## 📅 Daily Workflow

### Morning Setup (Manual - Same as before)
1. Login to OpenAlgo with credentials
2. Login to Fyers broker through OpenAlgo
3. Get fresh API key from OpenAlgo dashboard
4. Update API key in configuration if needed

### Automatic Process (New)
1. Run: `python openalgo_comprehensive_injector.py`
2. System initializes with all your symbols
3. At 09:13:15: Automatic ATM option selection
4. All symbols injected into AmiBroker via relay
5. Daily symbols saved for persistence

## 🏃‍♂️ Quick Start

### Test the Integration
```bash
python test_comprehensive_integration.py
```

### Run the Complete System
```bash
python openalgo_comprehensive_injector.py
```

### Monitor Logs
Check `C:\AmiPyScripts\fyers_logs\openalgo_comprehensive_injector.log`

## 📊 Symbol Management

### Static Symbols (Always Available)
All your original futures and equities are automatically included:
- 10 MCX commodity futures
- 2 NSE index futures
- 1 NSE equity (SBIN)

### Dynamic Symbols (Daily ATM Selection)
- NIFTY ATM options (nearest + next weekly expiry)
- BANKNIFTY ATM options (nearest + next weekly expiry)
- Generated in format: `NIFTY17JAN2519500CE`, `BANKNIFTY17JAN2544000PE`

### Symbol Discovery Process
1. System connects to relay server
2. Sends dummy data bars for each symbol
3. AmiBroker automatically discovers and adds symbols
4. Ready for real-time data feed

## 🔍 Testing & Troubleshooting

### Test Components
```bash
# Test complete integration
python test_comprehensive_integration.py

# Test with market closed (uses mock data)
# Should show symbol generation and relay connection

# Test with market open (real data)
# Should show actual LTP and expiry dates
```

### Common Issues

**API Key Invalid (403 error)**
- Get fresh API key from OpenAlgo dashboard
- Update in openalgo_symbol_injector.env
- Restart the system

**Relay Server Connection Failed**
- Ensure relay server running on ws://localhost:10102
- Check firewall settings
- Verify port availability

**No Symbols Selected**
- Market may be closed
- API key may be invalid
- Check logs for specific errors

**ATM Selection Failed**
- Indices may not be trading
- Option chain data unavailable
- Will retry next day

## 📁 File Structure

```
C:\AmiPyScripts\fyers_contracts\
├── daily_atm_symbols_2025-01-17.json  # Today's ATM options
├── daily_atm_symbols_2025-01-16.json  # Yesterday's ATM options
└── ...

C:\AmiPyScripts\fyers_logs\
├── openalgo_comprehensive_injector.log  # Main system log
└── ...

C:\Users\Admin\Documents\FortressTradingSystem\
├── openalgo_comprehensive_injector.py   # Main system
├── test_comprehensive_integration.py      # Test script
├── openalgo_symbol_injector.env          # Configuration
└── OPENALGO_SYMBOL_INJECTOR_README.md    # Documentation
```

## 🔄 Migration from Fyers Client

To switch from your Fyers client:

1. **Stop Fyers client** (avoid conflicts)
2. **Ensure OpenAlgo is running** (authenticated and ready)
3. **Run comprehensive injector** (`python openalgo_comprehensive_injector.py`)
4. **All symbols automatically available** in AmiBroker

Your relay server and AmiBroker setup remain completely unchanged.

## ⚙️ Advanced Configuration

### Change ATM Selection Time
Edit `ATM_SELECTION_TIME_STR = "09:13:15"` in the script

### Add New Symbols
Update `COMPLETE_SYMBOL_MAPPING` dictionary with new symbol mappings

### Modify Strike Intervals
- NIFTY: `NIFTY_STRIKE_INTERVAL = 50`
- BANKNIFTY: `BANKNIFTY_STRIKE_INTERVAL = 100`

### Adjust Logging Level
Change `level=logging.INFO` to `logging.DEBUG` for detailed logs

## 🎉 Success Indicators

✅ **System Running**: "OpenAlgo Comprehensive Symbol Injector started"
✅ **Symbols Loaded**: "System initialized with 13 total symbols"
✅ **Relay Connected**: "Connected to relay server and sent 'rolesend'"
✅ **ATM Selection**: "ATM selection complete. Added 4 new symbols"
✅ **AmiBroker Ready**: All symbols discoverable in AmiBroker

You're now ready to run the complete system! 🚀
