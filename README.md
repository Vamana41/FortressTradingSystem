# Fortress Trading System

[![CI/CD Pipeline](https://github.com/your-username/fortress-trading-system/workflows/Fortress%20Trading%20System%20CI%2FCD/badge.svg)](https://github.com/your-username/fortress-trading-system/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🏰 Overview

Fortress Trading System is a comprehensive, event-driven trading platform designed for Indian markets. It provides multi-timeframe strategy support, advanced risk management, real-time market scanning, and seamless integration with OpenAlgo for broker connectivity.

### Key Features

- **🎯 Multi-Timeframe Strategy Support**: Run strategies across multiple timeframes simultaneously
- **🔄 Event-Driven Architecture**: Redis-backed event system for real-time signal processing
- **📊 Advanced Risk Management**: Position sizing, margin calculations, and risk controls
- **🔍 Market Scanner**: ChartInk/PKScreener-style market screening with custom rules
- **📈 Real-time Dashboard**: Web-based monitoring and control interface
- **⚡ OpenAlgo Integration**: Unified broker API through OpenAlgo gateway
- **📱 Mobile Responsive**: Modern web interface with real-time updates
- **🔧 Extensible**: Plugin architecture for custom strategies and integrations

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis Server
- OpenAlgo Server (for broker connectivity)
- Node.js (for dashboard build tools)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/fortress-trading-system.git
   cd fortress-trading-system
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run setup validation**
   ```bash
   python setup_fortress.py
   ```

5. **Start the system**
   ```bash
   # Start Redis
   redis-server
   
   # Start OpenAlgo (in separate terminal)
   python openalgo/app.py
   
   # Start Fortress Trading System
   python fortress/src/fortress/main.py
   
   # Start Dashboard (optional, separate terminal)
   python -m fortress.dashboard.main
   ```

## 📋 System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AmiBroker     │───▶│   Fortress      │───▶│   OpenAlgo      │
│   Signals       │    │   Brain         │    │   Gateway       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Event Bus     │    │   Brokers       │
                       │   (Redis)       │    │   (Fyers, etc)  │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Dashboard     │
                       │   (Web UI)      │
                       └─────────────────┘
```

## 🔧 Configuration

### Environment Variables

```bash
# OpenAlgo Configuration
OPENALGO_BASE_URL=http://localhost:8080/api/v1
OPENALGO_API_KEY=your_openalgo_api_key

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Trading Configuration
TRADING_MODE=paper  # paper, live, backtest
LOG_LEVEL=INFO
```

### Strategy Configuration

Strategies are configured in JSON format with parameters:

```json
{
  "strategy_name": "MA_Crossover",
  "timeframe": "15min",
  "symbol": "NIFTY24NOVFUT",
  "parameters": {
    "fast_ma": 20,
    "slow_ma": 50,
    "ma_type": "EMA"
  }
}
```

## 📊 Dashboard Features

- **Real-time Monitoring**: Live positions, P&L, and system status
- **Strategy Management**: Activate/deactivate strategies, view performance
- **Risk Management**: Position sizing, margin usage, risk metrics
- **Market Scanner**: Custom screening with ChartInk-style rules
- **Multi-timeframe Analysis**: Correlation analysis across timeframes
- **Performance Metrics**: System performance and benchmarking

## 🎯 Market Scanner

The integrated scanner supports ChartInk-style English rules:

```
Latest RSI(14) > 50 AND
Latest Close > SMA(Close, 20) AND
Latest Volume > SMA(Volume, 10)
```

### Pre-built Scanners

- **Momentum Scanner**: High RSI + Volume surge
- **Breakout Scanner**: Price above resistance + volume
- **Mean Reversion**: Oversold conditions
- **Moving Average Crossovers**: MA strategy signals

## 🔒 Risk Management

- **Position Sizing**: Dynamic sizing based on account equity
- **Stop Loss**: Automatic stop loss placement
- **Margin Checks**: Real-time margin requirement validation
- **Drawdown Limits**: Maximum drawdown protection
- **Correlation Analysis**: Multi-timeframe signal validation

## 🧪 Testing

### Unit Tests
```bash
pytest fortress/tests/ -v --cov=fortress
```

### Integration Tests
```bash
python setup_fortress.py --test-full-system
```

### Performance Tests
```bash
python -m fortress.performance.benchmark
```

## 🚀 Deployment

### Local Development
```bash
python fortress/src/fortress/main.py
```

### Production (Vercel)
```bash
# Environment variables must be configured
vercel --prod
```

### Docker
```bash
docker-compose up -d
```

## 📈 Performance Monitoring

The system includes comprehensive monitoring:

- **System Metrics**: CPU, memory, disk usage
- **Trading Metrics**: Orders per second, latency, success rates
- **Event Bus Metrics**: Queue depths, processing times
- **Database Metrics**: Query performance, connection pooling

## 🔌 API Documentation

### REST API

- `GET /api/status` - System status
- `GET /api/positions` - Current positions
- `GET /api/signals` - Recent signals
- `POST /api/strategies` - Create strategy
- `GET /api/scanner/results` - Scanner results

### WebSocket API

- `ws://localhost:8000/ws` - Real-time updates
- Topics: signals, positions, orders, system_events

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Use type hints
- Add error handling

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-username/fortress-trading-system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/fortress-trading-system/discussions)

## 🙏 Acknowledgments

- **OpenAlgo**: For providing unified broker API
- **Redis**: For high-performance event streaming
- **FastAPI**: For modern web framework
- **ChartInk**: For scanner rule inspiration
- **Trading Community**: For feedback and testing

## 📊 Project Status

- ✅ Core Architecture
- ✅ Event System
- ✅ Risk Management
- ✅ Multi-timeframe Support
- ✅ Market Scanner
- ✅ Dashboard UI
- ✅ OpenAlgo Integration
- ✅ Performance Monitoring
- 🔄 Production Testing
- 📝 Documentation (Ongoing)

---

**⚠️ Disclaimer**: This is a trading system that involves financial risk. Use at your own risk and ensure proper testing before live trading.