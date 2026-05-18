# Quick Start Guide

## ✅ Setup Complete!

Your intelligent trading agent is now fully configured and ready to trade.

## What's Working

- ✅ **Deriv API Connection** - Live WebSocket connection to Deriv
- ✅ **Real-time Market Data** - Receiving tick data for R_100
- ✅ **Market Analysis** - Feature extraction and state detection
- ✅ **Strategy Selection** - Dynamic strategy matching
- ✅ **Risk Management** - Position sizing and drawdown control
- ✅ **Learning System** - Continuous adaptation from trades

## Running the Agent

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Run the Agent
```bash
python3 agent.py
```

### 3. Monitor Logs
```bash
# In another terminal
tail -f logs/agent.log
tail -f logs/trades.log
tail -f logs/decisions.log
```

## What the Agent Does

1. **Connects** to Deriv API and subscribes to R_100 ticks
2. **Analyzes** market conditions (trending, ranging, volatile, calm)
3. **Selects** best strategy based on market state
4. **Checks** risk constraints before trading
5. **Executes** trades when conditions are favorable
6. **Learns** from results and adapts over time

## Configuration

Edit `.env` to customize:

- `STAKE` - Base stake amount (default: 1.0)
- `MIN_CONFIDENCE` - Minimum confidence to trade (default: 0.60)
- `MAX_DAILY_LOSS` - Daily loss limit (default: 10.0)
- `MAX_CONSEC_LOSSES` - Consecutive loss limit (default: 3)

## Safety Features

- Daily loss limits
- Consecutive loss protection
- Market health checks
- Confidence thresholds
- Dynamic position sizing

## Testing

Test the connection without trading:
```bash
python3 test_connection.py
```

## Stopping the Agent

Press `Ctrl+C` to gracefully stop the agent. It will:
- Disconnect from Deriv
- Save session data
- Export logs

## Next Steps

1. Monitor the agent's performance in logs
2. Adjust configuration based on results
3. Review trade decisions in `logs/decisions.log`
4. Check market analysis in `logs/market_analysis.log`

## ⚠️ Important

- Start with small stakes
- Monitor closely at first
- This is a demo account - test thoroughly before live trading
- Review all trades and adjust parameters as needed

---

**Happy Trading! 🚀**
