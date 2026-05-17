# Intelligent Trading Agent

An AI-powered trading agent that understands market conditions and adapts strategies accordingly.

## 🤖 Features

- **Market Intelligence**: Detects market states (trending, ranging, volatile, calm)
- **Adaptive Strategies**: Selects best strategy based on market conditions
- **Continuous Learning**: Learns from trades and improves over time
- **Risk Management**: Dynamic stake sizing and drawdown protection
- **Multi-Strategy**: Supports Higher/Lower, Accumulator, and Rise/Fall trading

## 🚀 Quick Start

### 1. Setup

```bash
# Navigate to the agent directory
cd intelligent_trading_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 3. Run

```bash
python agent.py
```

## 📋 Current Status

### ✅ Phase 1 Complete: Foundation

- Agent orchestrator structure
- Configuration management
- Logging infrastructure
- Deriv API client wrapper

### 🔄 Phase 2 In Progress: Market Intelligence

- Market state detection
- Feature engineering (50+ indicators)
- Market health scoring

### ⏳ Upcoming Phases

- Phase 3: Strategy Adaptation
- Phase 4: Learning & Adaptation
- Phase 5: Risk Management
- Phase 6: Testing & Deployment

## 🏗️ Architecture

```
IntelligentTradingAgent
├── Market Analysis Engine
│   ├── Tick collection
│   ├── Feature extraction
│   └── Market state detection
├── Strategy Selector
│   ├── Accumulator strategy
│   ├── Higher/Lower strategy
│   └── Rise/Fall strategy
├── Learning System
│   ├── Model training
│   └── Performance tracking
└── Risk Manager
    ├── Dynamic risk sizing
    └── Drawdown protection
```

## 📊 Configuration

Edit `.env` to customize:

```env
# API
DERIV_API_TOKEN=your_token
DERIV_APP_ID=1089

# Trading
STAKE=1.0              # Base stake amount
MIN_CONFIDENCE=0.60    # Minimum confidence to trade
HIGH_CONFIDENCE=0.75   # Good quality trades

# Risk
MAX_DAILY_LOSS=10.0    # Stop trading if daily loss exceeds this
MAX_CONSEC_LOSSES=3    # Pause after N consecutive losses
MAX_DRAWDOWN=20.0      # Maximum portfolio drawdown

# Learning
RETRAIN_EVERY=50       # Retrain model every N trades
CONTINUOUS_LEARNING=True  # Learn from each trade
```

## 📈 Performance Goals

- **Win Rate**: > 65% across all market conditions
- **Consistency**: Profitable over 7-day periods
- **Adaptability**: Successfully switches strategies based on market state
- **Learning**: Improves performance over time

## 🛡️ Risk Management

The agent implements multiple safety mechanisms:

1. **Daily Loss Limit**: Stops trading if losses exceed MAX_DAILY_LOSS
2. **Consecutive Loss Limit**: Pauses after MAX_CONSEC_LOSSES
3. **Drawdown Protection**: Stops if portfolio drawdown exceeds MAX_DRAWDOWN
4. **Confidence Threshold**: Only trades with sufficient confidence
5. **Market Health Check**: Refuses to trade in unfavorable markets

## 📝 Logging

Logs are saved to the `logs/` directory:

- `agent.log` - Main agent operations
- `trades.log` - Trade execution records
- `market_analysis.log` - Market analysis results
- `decisions.log` - Trading decisions

## ⚠️ Disclaimer

**Trading involves substantial risk.** This agent is for educational purposes.

- Test thoroughly on demo accounts first
- Only trade with money you can afford to lose
- Past performance doesn't guarantee future results
- The author is not responsible for losses

## 🔧 Troubleshooting

### Connection Issues

```bash
# Verify API token is valid
# Check internet connection
# Ensure app_id is correct (1089)
```

### Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Model Issues

```bash
# Delete old models and retrain
rm models/*.pkl
python agent.py
```

## 📚 File Structure

```
intelligent_trading_agent/
├── agent.py              # Main agent orchestrator
├── config.py             # Configuration management
├── logger.py             # Logging infrastructure
├── deriv_client.py       # Deriv API client
├── market_analyzer.py    # Market analysis (phase 2)
├── strategy_selector.py  # Strategy selection (phase 3)
├── learning_system.py    # Learning & adaptation (phase 4)
├── risk_manager.py       # Risk management (phase 5)
├── features/
│   ├── indicators.py     # Technical indicators
│   ├── patterns.py       # Pattern recognition
│   └── volatility.py     # Volatility metrics
├── strategies/
│   ├── accumulator.py    # Accumulator strategy
│   ├── higher_lower.py   # Higher/Lower strategy
│   └── rise_fall.py      # Rise/Fall strategy
├── models/               # Persisted models
├── logs/                 # Trade and analysis logs
└── requirements.txt      # Python dependencies
```

## 🤝 Contributing

Have ideas to improve the agent?

1. Test thoroughly on demo first
2. Submit improvements with performance data
3. Document any new features

## 📞 Support

- Check the logs for detailed information
- Review the main README for bot comparison
- Test on demo account before live trading

---

**Happy Trading! 🚀**
