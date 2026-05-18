# Deriv Rise/Fall ML Trading Bot

An intelligent trading bot for Deriv's Rise/Fall contracts using machine learning and technical analysis.

## Features

- **Machine Learning Predictions**: Uses Random Forest classifier with cross-validation
- **Advanced Technical Analysis**: 20+ features including momentum, volatility, entropy, Hurst exponent
- **Minute-Based Duration**: Trades using minute durations instead of ticks for more stable predictions
- **Martingale Strategy**: Optional martingale for loss recovery (configurable)
- **Risk Management**: Built-in stop loss, take profit, and consecutive loss protection
- **Adaptive Strategy**: Dynamically adjusts confidence thresholds based on performance
- **Market Regime Detection**: Identifies and adapts to different market conditions

## Contract Types

This bot trades **Rise/Fall** contracts:
- **CALL (Rise)**: Predicts price will be higher at expiry
- **PUT (Fall)**: Predicts price will be lower at expiry

Duration is specified in **minutes** (default: 1 minute).

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your API credentials:
```bash
cp .env.example .env
# Edit .env and add your Deriv API token
```

## Configuration

Edit `.env` file:

- `DERIV_API_TOKEN`: Your Deriv API token (get from https://app.deriv.com/account/api-token)
- `DERIV_APP_ID`: App ID (default: 1089)
- `SYMBOL`: Trading symbol (R_100, R_75, R_50, R_25, R_10)
- `STAKE`: Base stake amount in USD
- `DURATION_MINUTES`: Contract duration in minutes (1-60)
- `TAKE_PROFIT`: Stop trading when profit reaches this amount
- `STOP_LOSS`: Stop trading when loss reaches this amount
- `MAX_DAILY_LOSS`: Maximum daily loss limit
- `MAX_CONSEC_LOSSES`: Pause after this many consecutive losses

### Martingale Settings (Optional)

- `ENABLE_MARTINGALE`: Enable/disable martingale strategy (true/false)
- `MARTINGALE_MULTIPLIER`: Stake multiplier after loss (default: 2.0 = double)
- `MAX_MARTINGALE_STEPS`: Maximum consecutive stake increases (default: 3)

**⚠️ Warning:** Martingale increases risk significantly. See [MARTINGALE_GUIDE.md](MARTINGALE_GUIDE.md) for details.

## Usage

Run the bot:
```bash
python bot.py
```

The bot will:
1. Connect to Deriv WebSocket API
2. Collect initial tick data for feature extraction
3. Train the ML model with historical patterns
4. Start making predictions and placing trades
5. Continuously retrain and adapt to market conditions

## How It Works

### Feature Engineering
The bot extracts 20+ features from price data:
- **Momentum**: Short, medium, and long-term price momentum
- **Volatility**: Volatility clustering and standard deviation
- **Autocorrelation**: Price correlation at multiple lags
- **Entropy**: Randomness measure of price movements
- **Mean Reversion**: Distance from moving average
- **Hurst Exponent**: Trend persistence indicator
- **Digit Analysis**: Last digit patterns and biases

### ML Model
- **Algorithm**: Random Forest Classifier
- **Training**: Continuous learning from trade outcomes
- **Validation**: Cross-validation to prevent overfitting
- **Fallback**: Heuristic predictions when model confidence is low

### Trading Logic
1. Collect tick data and extract features
2. Get ML prediction with confidence score
3. Apply risk management filters
4. Check market regime suitability
5. Execute trade if all conditions met
6. Learn from outcome and retrain periodically

## Performance Monitoring

The bot displays real-time statistics:
- Win/Loss ratio and win rate
- Current profit/loss
- Model accuracy (CV score)
- Trade history
- Market regime indicators

## Safety Features

- **Pause on Losses**: Automatically pauses after consecutive losses
- **Take Profit**: Stops trading when target profit reached
- **Stop Loss**: Stops trading when loss limit reached
- **High Entropy Detection**: Skips trading in random market conditions
- **Confidence Thresholds**: Only trades high-confidence predictions
- **Dynamic Adjustment**: Increases requirements after losses
- **Martingale Limits**: Caps maximum stake increases (when enabled)

## Documentation

- **[README.md](README.md)**: Main documentation (you are here)
- **[QUICK_START.md](QUICK_START.md)**: Quick start guide for beginners
- **[MARTINGALE_GUIDE.md](MARTINGALE_GUIDE.md)**: Complete martingale strategy guide

## Tips for Best Results

1. **Start Small**: Use low stake amounts while testing
2. **Monitor Performance**: Watch the first few trades closely
3. **Choose Stable Markets**: R_100 typically has better patterns
4. **Adjust Duration**: Longer durations (2-5 minutes) may be more predictable
5. **Let It Learn**: Model improves after 100+ samples
6. **Respect Limits**: Don't override stop loss/take profit settings

## Disclaimer

Trading involves risk. This bot is for educational purposes. Past performance does not guarantee future results. Only trade with money you can afford to lose.

## License

MIT License
