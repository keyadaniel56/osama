# Higher/Lower Trading Bot - Volatility 15s

Two versions of trading bots for Deriv that trade Higher/Lower contracts on Volatility 15s.

## Versions

1. **bot.py** - Simple rule-based bot (red candle + decimal < 200)
2. **bot_ml.py** - ML-enhanced bot with pattern recognition and confidence scoring

## Strategy

The bot uses a simple strategy:
- **Condition**: If the price is RED (down) AND the decimal part is less than 200
  - Example: Price 123.456 → decimal part is 456 (not < 200, no trade)
  - Example: Price 123.156 → decimal part is 156 (< 200, trade if red)
- **Action**: Buy LOWER contract
- **Duration**: 5 ticks

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from example:
```bash
cp .env.example .env
```

3. Edit `.env` and add your Deriv API credentials:
```
DERIV_API_TOKEN=your_actual_token
DERIV_APP_ID=1089
STAKE=1.0
```

## Running the Bot

```bash
python bot.py
```

## Configuration

Edit the `.env` file to customize:
- `DERIV_API_TOKEN`: Your Deriv API token
- `DERIV_APP_ID`: Your app ID (default: 1089)
- `STAKE`: Amount to stake per trade (default: 1.0 USD)

## How It Works

1. Connects to Deriv WebSocket API
2. Subscribes to Volatility 15s (1HZ15V) tick stream
3. Monitors each tick for strategy conditions
4. When conditions are met, executes LOWER trade with 5 ticks duration
5. Tracks results and displays statistics

## Output

The bot displays:
- Real-time price updates with last digit
- Trade execution notifications
- Win/Loss results with profit/loss
- Running statistics (trades, win rate, P&L)

## Safety

- Only trades when NOT already in a position
- Uses fixed stake amount
- Tracks all trades for analysis
- Can be stopped anytime with Ctrl+C

## Notes

- Symbol: 1HZ15V (Volatility 15s)
- Contract Type: PUT (LOWER)
- Duration: 5 ticks
- Decimal part: The digits after the decimal point (e.g., 123.456 → 456)


## ML Bot Features

The ML-enhanced bot (`bot_ml.py`) includes:

- **Machine Learning Model**: Random Forest classifier that learns from trade outcomes
- **Feature Engineering**: Extracts 15+ features including momentum, volatility, trends, and patterns
- **Confidence Scoring**: Only trades when model confidence is ≥70%
- **Continuous Learning**: Retrains every 10 trades to adapt to market conditions
- **Model Persistence**: Saves/loads trained model for improved performance over time

### ML Bot Usage

```bash
python bot_ml.py
```

The bot will:
1. Start with simple rules until it collects 50 samples
2. Train the ML model once enough data is collected
3. Use ML predictions with confidence scoring
4. Continuously improve by learning from each trade
5. Save the model for future sessions

### Features Extracted

- Momentum (short, medium, long-term)
- Volatility (short and long-term)
- Trend indicators (red candles, consecutive patterns)
- Price levels (z-score, normalized position)
- Decimal patterns
- Acceleration patterns

### Performance

The ML bot typically achieves:
- Higher win rate than rule-based approach
- Better risk management through confidence scoring
- Adaptive behavior as market conditions change
