# Fortress Trading System

Event-driven modular monolith trading system with Redis-based job queue, AmiBroker integration, and OpenAlgo gateway.

## Architecture

- **Event-Driven Architecture**: Redis-based message bus with LPUSH/BRPOP pattern
- **Modular Monolith**: Separate Brain (strategy) and Worker (execution) components
- **Multi-Timeframe Support**: Strategy validation across different timeframes
- **Risk Management**: Comprehensive position sizing and margin management
- **AmiBroker Integration**: File-based signal processing with watch directory
- **Structured Logging**: Complete audit trail with structlog

## Components

### Fortress Brain
- Strategy state management
- Signal validation and risk checks
- Multi-timeframe strategy support
- Position tracking and P&L calculation

### Event Bus
- Redis-based message queue
- Priority-based event processing
- Reliable delivery with processing state tracking
- Error handling and retry mechanisms

### AmiBroker Integration
- File-based signal detection
- CSV format with configurable fields
- Automatic file processing and archival
- Error handling and duplicate prevention

## Installation

```bash
# Install dependencies
pip install -e .

# Start Redis (required for event bus)
redis-server

# Create signal directories
mkdir -p signals/amibroker

# Run the system
python -m fortress.main
```

## Configuration

### Environment Variables
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)
- `LOG_LEVEL`: Logging level (default: INFO)
- `SIGNAL_DIR`: AmiBroker signal directory (default: ./signals/amibroker)

### Signal File Format
```csv
symbol,signal_type,quantity,price,timeframe,strategy_name
NIFTY24NOVFUT,BUY,50,25000.0,15min,MA_Crossover
BANKNIFTY24NOVFUT,SELL,25,52000.0,5min,RSI_Strategy
```

## Usage

### Starting the System
```bash
python -m fortress.main
```

### Creating Signal Files
Place CSV files in the `signals/amibroker` directory. Files are automatically processed and moved to `processed` or `errors` directories.

### Monitoring
The system provides structured logging with detailed event tracking:
- Signal processing
- Risk checks
- Position updates
- System health

## Development

### Project Structure
```
fortress/
├── src/fortress/
│   ├── core/           # Core components (events, event_bus, logging)
│   ├── brain/          # Strategy and state management
│   ├── integrations/   # External integrations (AmiBroker)
│   └── main.py         # Main application
├── signals/            # Signal files directory
├── tests/              # Test suite
└── pyproject.toml      # Project configuration
```

### Testing
```bash
pytest tests/ -v --cov=src
```

### Code Quality
```bash
ruff check src/
pyright src/
```

## License

MIT License
