# 🤖 Intelligent Trading Agent - Complete Documentation

## Overview

A production-ready AI trading agent that combines **Machine Learning**, **Pattern Recognition**, and **Technical Indicators** for intelligent multi-market trading on the Deriv platform.

### Key Capabilities

✅ **Hybrid Intelligence**

- ML-based price predictions (50% weight)
- Chart pattern recognition (30% weight)
- Technical indicators analysis (20% weight)
- Ensemble decision making (votes on agreement)

✅ **Multi-Market Monitoring**

- Simultaneously monitors 5+ trading pairs
- Opportunity scoring across all markets
- Automatic best-market selection

✅ **Real-Time Dashboard**

- Beautiful web UI (http://localhost:5000)
- Live P&L tracking with history chart
- Decision engine signal visualization
- Trade performance statistics
- Market opportunity scanner

✅ **Risk Management**

- Dynamic position sizing (0.25x - 2.0x)
- Daily loss limits
- Consecutive loss protection
- Drawdown monitoring
- Confidence-based filtering

✅ **Continuous Learning**

- Trade performance tracking per market state
- Automatic strategy adaptation
- ML model retraining on new data

---

## Installation

### 1. Prerequisites

- Python 3.8+
- Deriv account (for API token)
- Terminal/CLI access

### 2. Setup

```bash
cd intelligent_trading_agent

# Create virtual environment (if not exists)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Deriv API token
# Get token from: https://app.deriv.com/account/api-token
nano .env
```

**Required .env variables:**

```
DERIV_API_TOKEN=your_api_token_here
DERIV_APP_ID=1089
SYMBOL=R_100
STAKE=1.0
MIN_CONFIDENCE=0.60
MAX_DAILY_LOSS=10.0
MAX_CONSEC_LOSSES=3
```

---

## Running the Agent

### Option 1: Using Quick Start Script (Recommended)

```bash
cd intelligent_trading_agent
bash run_agent.sh
```

This will:

1. Start the Trading Agent
2. Start the Dashboard Server
3. Open http://localhost:5000 automatically

### Option 2: Manual Start (Two Terminals)

**Terminal 1 - Trading Agent:**

```bash
cd intelligent_trading_agent
source venv/bin/activate
python3 agent.py
```

**Terminal 2 - Dashboard Server:**

```bash
cd intelligent_trading_agent
source venv/bin/activate
python3 dashboard_server.py
```

Then open browser to: **http://localhost:5000**

---

## Dashboard Features

### 📊 Real-Time Metrics

- **Daily P&L** - Total profit/loss with win/loss count
- **Win Rate** - Percentage of winning trades
- **Drawdown** - Current and max drawdown percentage
- **Market State** - Current market conditions (trending, ranging, volatile, etc.)
- **Active Strategy** - Current trading strategy with confidence

### 🧠 Decision Engine Signals

Three independent signals shown with confidence levels:

1. **ML Model** - Machine learning prediction (50% weight)
2. **Pattern Recognition** - Chart pattern signals (30% weight)
3. **Indicators** - Technical indicator signals (20% weight)

**Trade Signal** = Ensemble vote of all three signals

### 📍 Multi-Market Opportunities

Live scanner showing:

- Top opportunities by score (0-100)
- Market health per symbol
- Recommended strategy for each
- Pattern confirmation count

### 📈 Recent Trades

- Direction (UP/DOWN)
- Symbol
- Win/Loss status
- P&L amount

### 📊 P&L Chart

Cumulative profit/loss over time with trend visualization.

### 🎮 Control Panel

- **Pause Trading** - Temporarily halt new trades
- **Resume Trading** - Resume after pause
- **Reset Daily Stats** - Clear today's metrics
- **Stop Agent** - Shutdown gracefully

---

## Decision Engine: How It Works

### Ensemble Approach

The agent doesn't rely on just one signal. Instead, it uses THREE independent analysis engines:

```
┌─────────────────────┬──────────────────────┬─────────────────────┐
│   ML PREDICTION     │  PATTERN RECOGNITION │ TECHNICAL INDICATORS│
│  (50% weight)       │  (30% weight)        │  (20% weight)       │
│                     │                      │                     │
│ • Neural net model  │ • Head & Shoulders   │ • RSI (Oversold?)   │
│ • Trained on data   │ • Double Top/Bottom  │ • MACD (Momentum?)  │
│ • Price prediction  │ • Triangles          │ • Bollinger Bands   │
│ • 85% confidence    │ • Flags              │ • Breakout signal   │
└─────────────────────┴──────────────────────┴─────────────────────┘
                            ↓↓↓
                    CONFIDENCE SCORING
                            ↓↓↓
┌─────────────────────────────────────────────────────────────────┐
│  ENSEMBLE DECISION ENGINE                                       │
│                                                                 │
│  Calculate weighted consensus:                                  │
│  • If all 3 agree: +15% confidence boost                       │
│  • If 2/3 agree: Normal confidence                             │
│  • If <2 agree: Reject signal or lower confidence              │
│                                                                 │
│  Final signal: BUY (direction + confidence %)                  │
└─────────────────────────────────────────────────────────────────┘
```

### Confidence Scoring

**Factors that affect confidence:**

- Market health (must be >50/100)
- Winning streak (boosts confidence up to +15%)
- Recent loss streak (reduces confidence by 10% per loss)
- Agreement between signals (+15% boost if all 3 agree)
- Market state (trending: +20%, ranging: -10%, volatile: -15%)

### Example Trade Decision

```
Scenario: R_100 pair at 3:00 PM

ML Prediction:    UP with 85% confidence
Pattern Signal:   Double Bottom (Bullish) with 75% confidence
Indicator Signal: RSI 25 (Oversold) UP signal with 70% confidence
Market Health:    75/100 (Good)
Recent Performance: 2 wins in a row
Market State:     Ranging (stable)

Decision Engine:
→ All 3 signals agree on UP direction
→ Ensemble confidence: (0.85×0.5 + 0.75×0.3 + 0.70×0.2) × 1.15 = 83%
→ Winning streak boost: +5% = 88%
→ Final signal: BUY UP @ 88% confidence ✓ TRADE EXECUTED

Position Size: $1.00 (base stake)
Duration: 5 minutes
```

---

## P&L Tracking

### How Profits & Losses Are Calculated

1. **Trade Entry**: Agent buys contract with stake amount
2. **Trade Execution**: Contract is held for duration (default 5 min)
3. **Trade Settlement**: Deriv API returns contract result
4. **P&L Recording**:
   - **WIN**: Profit = Payout - Stake (usually 1.8x-2.0x stake)
   - **LOSS**: Loss = Stake (full amount lost)

### Dashboard P&L Display

```
Daily P&L: +$23.46
├─ Gross Profit (wins): $45.00
├─ Gross Loss (losses): $-21.54
└─ Net P&L: +$23.46

Cumulative:
├─ Trade 1: -$0.90 (loss)
├─ Trade 2: +$1.10 (win)
├─ Trade 3: +$2.05 (win)
└─ Running Total: +$2.25 ←shown on chart

Win Rate: 66.7% (2W/1L)
Max Drawdown: 15.2%
```

### Real-Time Updates

- Dashboard updates **every 2 seconds**
- P&L recalculated after each trade settles
- Chart shows cumulative P&L progression
- Historical data persists in `dashboard_state.json`

---

## Technical Indicators

The agent analyzes 50+ technical indicators:

### Momentum Indicators

- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Momentum (rate of change)
- Stochastic Oscillator

### Volatility Indicators

- Bollinger Bands
- ATR (Average True Range)
- Keltner Channels
- Standard Deviation

### Trend Indicators

- Moving Averages (SMA, EMA)
- ADX (Average Directional Index)
- MACD Trend
- Slope of MA

### Volume Indicators

- Volume SMA
- Volume Ratio
- On-Balance Volume (OBV)

### Pattern Recognition (8 Patterns)

1. Head & Shoulders (bearish reversal)
2. Double Top (bearish reversal)
3. Double Bottom (bullish reversal)
4. Triangle (consolidation breakout)
5. Flag (continuation pattern)
6. Wedge (converging pattern)
7. Support/Resistance (structural levels)
8. Breakout (above/below key levels)

---

## Risk Management

### Position Sizing

- **Base Stake**: $1.00 (configurable)
- **Dynamic Multiplier**: 0.25x - 2.0x based on:
  - Market volatility (high vol → lower stake)
  - Win rate (losing streak → lower stake)
  - Confidence level (high confidence → higher stake)

### Daily Limits

- **Max Daily Loss**: $10.00 (pauses trading if reached)
- **Consecutive Loss Limit**: 3 trades (pauses after 3 losses)
- **Max Drawdown**: 20% (stops trading if exceeded)

### Confidence Thresholds

- **Minimum**: 0.60 (60%) - Won't trade below this
- **High**: 0.75 (75%) - Increases position size
- **Ultra**: 0.85 (85%) - Maximum position size

---

## Running Examples

### Example 1: Basic Startup

```bash
cd intelligent_trading_agent
source venv/bin/activate
python3 agent.py
```

**Expected Output:**

```
INFO: Initialized IntelligentTradingAgent: agent_20260518_130000
INFO: Subsystems loaded:
  - Market Analyzer
  - Pattern Recognition
  - ML Predictor
  - Decision Engine (ML + Patterns + Indicators)
  - Risk Manager
...
INFO: Connected to Deriv WebSocket
INFO: Monitoring symbols: ['R_100', 'R_50', 'R_25', 'EURUSD', 'AUDNZD']
```

### Example 2: With Dashboard

**Terminal 1:**

```bash
python3 agent.py
```

**Terminal 2:**

```bash
python3 dashboard_server.py
# Open: http://localhost:5000
```

**Dashboard shows:**

- Real-time P&L: +$12.34
- Win Rate: 65%
- 5 live market opportunities
- Recent 10 trades with results
- Decision engine signals active

---

## Troubleshooting

### "Market State: unknown, Health: 65.0"

- Agent is still collecting price data
- Wait 1-2 minutes for indicator calculation
- Needs 100+ price ticks to detect patterns

### "Daily P&L: $0.00"

- No trades executed yet
- Check minimum confidence threshold
- Verify market health is above 50

### "Trading Paused"

- Daily loss limit reached
- Consecutive losses limit exceeded
- Drawdown exceeded 20%
- Check dashboard for reason
- Use "Resume Trading" button to continue (after review!)

### Dashboard not loading

- Ensure `dashboard_server.py` is running
- Check http://localhost:5000 in browser
- Verify Python and Flask are installed: `pip list | grep Flask`

### Connection errors

- Verify DERIV_API_TOKEN in .env is valid
- Check internet connection
- Deriv API may be temporarily unavailable
- Use demo account first for testing

---

## Strategy Details

### Higher/Lower (Default for ranging markets)

- Predicts if price will be higher or lower at expiry
- Best in calm, ranging markets
- Low risk, lower returns

### Rise/Fall

- Predicts if price will rise or fall
- Good for trending markets
- Medium risk, medium returns

### Accumulator

- Accumulators increase payout for consecutive correct predictions
- Best in strong trending markets
- Higher risk, higher potential returns

---

## Performance Optimization

### For Backtesting

Use `enhanced_demo.py` to test on synthetic data:

```bash
python3 enhanced_demo.py
```

### For Paper Trading

1. Create Deriv **demo account** (virtual money)
2. Get demo account API token
3. Set `DERIV_APP_ID` to demo app
4. Run agent normally

### For Live Trading

1. Start with **$1 stakes** in .env
2. Run for 24-48 hours and verify performance
3. If win rate > 55%: increase to $5
4. If win rate > 60%: scale to $10-25
5. Monitor daily and adjust risk parameters

---

## File Structure

```
intelligent_trading_agent/
├── agent.py                    # Main agent orchestrator
├── decision_engine.py          # ML + Pattern + Indicator ensemble
├── market_analyzer.py          # Market state detection
├── strategy_selector.py        # Strategy matching
├── learning_system.py          # Continuous learning
├── risk_manager.py            # Risk controls
├── ml_predictor.py            # ML model training
├── deriv_client.py            # Deriv API client
│
├── features/
│   ├── indicators.py          # 50+ technical indicators
│   └── pattern_recognition.py # 8 chart patterns
│
├── multi_market_monitor.py    # Multi-symbol scanning
├── logger.py                  # Logging system
├── config.py                  # Configuration
│
├── dashboard.html             # Web UI (beautiful!)
├── dashboard_server.py        # Flask server
├── run_agent.sh              # Quick start script
│
├── requirements.txt           # Dependencies
├── .env.example              # Environment template
└── models/                    # Saved ML models
```

---

## Next Steps

1. ✅ Get API token from Deriv
2. ✅ Setup .env file
3. ✅ Run `run_agent.sh`
4. ✅ Open http://localhost:5000
5. ✅ Monitor trades in dashboard
6. ✅ Wait 24h to evaluate performance
7. ✅ Adjust risk parameters if needed
8. ✅ Scale up if profitable

---

## Support

For issues:

1. Check logs in `logs/` directory
2. Review `dashboard_state.json` for current state
3. Check `models/performance_metrics.json` for statistics
4. Review this documentation

Happy trading! 🚀
