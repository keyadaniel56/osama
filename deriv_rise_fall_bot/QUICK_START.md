# Quick Start Guide - Rise/Fall ML Bot

## What This Bot Does

This bot trades **Rise/Fall** contracts on Deriv using machine learning and technical analysis. Unlike the other bots that use tick-based durations, this bot uses **minute-based durations** for more stable predictions.

## Key Differences from Other Bots

| Feature | Rise/Fall Bot | Digit Bot | Accumulator Bot |
|---------|---------------|-----------|-----------------|
| Contract Type | CALL/PUT (Rise/Fall) | DIGITOVER/DIGITUNDER | Accumulator |
| Duration | Minutes (1-60) | Ticks | Continuous |
| Prediction | Price direction | Last digit | Growth rate |
| Best For | Trend following | Pattern recognition | Volatility trading |

## Setup (3 Steps)

### 1. Install Dependencies
```bash
cd deriv_rise_fall_bot
pip install -r requirements.txt
```

### 2. Configure API Token
```bash
cp .env.example .env
# Edit .env and add your Deriv API token
```

Get your API token from: https://app.deriv.com/account/api-token

### 3. Run the Bot
```bash
python bot.py
```

## Configuration Options

Edit `.env` file:

```bash
# Required
DERIV_API_TOKEN=your_token_here

# Trading Settings
SYMBOL=R_100              # R_100, R_75, R_50, R_25, R_10
STAKE=1.0                 # Stake per trade in USD
DURATION_MINUTES=1        # Contract duration (1-60 minutes)

# Risk Management
TAKE_PROFIT=10.0          # Stop when profit reaches this
STOP_LOSS=5.0             # Stop when loss reaches this
MAX_DAILY_LOSS=10.0       # Maximum daily loss
MAX_CONSEC_LOSSES=3       # Pause after N consecutive losses

# Martingale (Optional - see MARTINGALE_GUIDE.md)
ENABLE_MARTINGALE=false   # Set to 'true' to enable
MARTINGALE_MULTIPLIER=2.0 # Stake multiplier after loss
MAX_MARTINGALE_STEPS=3    # Maximum stake increases
```

## How It Works

### 1. Data Collection Phase
- Bot collects 50 ticks of price data
- Extracts 20+ technical features
- Displays: "📥 Collecting data: X/50 ticks"

### 2. Trading Phase
- ML model predicts RISE or FALL
- Checks confidence threshold (60%+)
- Validates signal quality
- Places trade with minute duration
- Displays: "🎯 TRADE | RISE/FALL | Confidence: X.XX"

### 3. Learning Phase
- Records trade outcome
- Adds to training dataset
- Retrains model every 50 trades
- Improves predictions over time

## Understanding the Output

```
🎯 TRADE | RISE | Confidence: 0.75 | Source: ml | Stake: $1.00
```
- **RISE/FALL**: Predicted direction
- **Confidence**: Model certainty (0.60-1.00)
- **Source**: ml (machine learning) or heuristic (technical indicators)
- **Stake**: Amount being risked

```
✅ WIN | Profit: $0.95 | Total: $5.50
```
- Trade won, earned $0.95 profit
- Total profit now $5.50

```
❌ LOSS | Loss: $1.00 | Total: $4.50
```
- Trade lost, lost $1.00
- Total profit now $4.50

## Tips for Success

### 1. Choose the Right Duration
- **1 minute**: Fast trades, more volatile
- **2-3 minutes**: Balanced, recommended for beginners
- **5+ minutes**: Slower, more stable trends

### 2. Select Stable Markets
- **R_100**: Most stable, best for learning
- **R_75**: Moderate volatility
- **R_50/R_25**: Higher volatility, more risk

### 3. Start Small
- Begin with $0.35 or $1 stakes
- Let the bot collect 100+ samples
- Monitor win rate and adjust

### 4. Monitor Performance
- Win rate should be 55%+ for profitability
- If win rate < 50%, consider:
  - Changing duration
  - Switching symbol
  - Adjusting confidence threshold

### 5. Let It Learn
- Model improves after 100+ trades
- First 50 trades use heuristic predictions
- Be patient during learning phase

## Common Issues

### "Authorization failed"
- Check your API token in `.env`
- Ensure token has trading permissions
- Verify token is not expired

### "No signal" messages
- Normal - bot is being selective
- Waits for high-confidence opportunities
- If persistent, try different symbol

### Low win rate initially
- Expected during learning phase
- Model needs 100+ samples to optimize
- Consider longer duration (2-3 minutes)

### Bot pauses frequently
- Triggered by consecutive losses
- Safety feature to prevent drawdown
- Will resume automatically after cooldown

## Advanced Configuration

### Enable Martingale (Advanced Users Only)

Martingale doubles your stake after each loss to recover losses. **High risk!**

```bash
ENABLE_MARTINGALE=true
MARTINGALE_MULTIPLIER=2.0
MAX_MARTINGALE_STEPS=2    # Start with 2 for safety
```

**⚠️ Read [MARTINGALE_GUIDE.md](MARTINGALE_GUIDE.md) before enabling!**

### Adjust Confidence Threshold
In `bot.py`, change:
```python
MIN_CONFIDENCE = 0.60  # Increase to 0.70 for fewer, higher-quality trades
```

### Change Cooldown Period
```python
TRADE_COOLDOWN_TICKS = 10  # Increase for more spacing between trades
```

### Modify Feature Window
In `feature_engine.py`:
```python
self.window = 50  # Increase to 100 for longer-term patterns
```

## Performance Expectations

### Realistic Goals
- **Win Rate**: 55-65% (good)
- **Profit Factor**: 1.2-1.5x (sustainable)
- **Daily Return**: 5-15% of capital (conservative)

### Warning Signs
- Win rate < 45% consistently
- Large consecutive losses (5+)
- Model CV accuracy < 0.55

If you see these, stop and reassess configuration.

## Safety Features

1. **Take Profit**: Auto-stops at profit target
2. **Stop Loss**: Auto-stops at loss limit
3. **Consecutive Loss Pause**: Pauses after N losses
4. **High Entropy Detection**: Skips random markets
5. **Dynamic Confidence**: Increases requirements after losses

## Next Steps

1. Run bot with small stakes ($0.35-$1)
2. Monitor first 20 trades closely
3. Check win rate after 50 trades
4. Adjust duration/symbol if needed
5. Gradually increase stake as confidence grows

## Support

For issues or questions:
1. Check this guide first
2. Review README.md for detailed info
3. Verify configuration in `.env`
4. Check Deriv API status

## Disclaimer

Trading involves risk. This bot is for educational purposes. Past performance does not guarantee future results. Only trade with money you can afford to lose.

---

**Ready to start?** Run `python bot.py` and watch it trade! 🚀
