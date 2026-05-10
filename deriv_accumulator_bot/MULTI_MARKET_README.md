# Multi-Market Accumulator Bot

## Overview

The multi-market bot monitors **5 synthetic indices simultaneously** and trades whichever market shows the best entry conditions at any moment.

## Markets Monitored

- **R_10** - Volatility 10 Index (1 tick/second)
- **R_25** - Volatility 25 Index (1 tick/second)
- **R_50** - Volatility 50 Index (1 tick/second)
- **R_75** - Volatility 75 Index (1 tick/second)
- **R_100** - Volatility 100 Index (2 ticks/second)

## Key Features

### 1. Parallel Monitoring
- Opens 5 WebSocket connections simultaneously
- Each market has independent volatility analysis
- Tracks conditions in real-time across all markets

### 2. Intelligent Market Selection
- Scores each market based on entry conditions
- Automatically selects the best opportunity
- Factors considered:
  - Volatility level (lower = better)
  - Directional consistency (higher = better)
  - Volatility trend (decreasing = better)
  - Hurst exponent (trending = better)

### 3. Scoring System

Each market gets a score from 0-100:
```
Volatility score:    0-40 points (lower vol = more points)
Consistency score:   0-30 points (higher consistency = more points)
Vol trend score:     0-20 points (decreasing vol = more points)
Hurst score:         0-10 points (higher hurst = more points)
```

The market with the highest score gets the trade.

### 4. Per-Market Cooldowns
- If a market causes a knockout, it goes into cooldown
- Other markets remain available for trading
- Prevents repeatedly trading bad conditions on one market

## Advantages Over Single-Market Bot

| Feature | Single Market | Multi-Market |
|---------|--------------|--------------|
| Trading opportunities | Limited | 5x more |
| Wait time between trades | Long | Much shorter |
| Market selection | Fixed | Dynamic (best conditions) |
| Knockout recovery | Wait for cooldown | Trade other markets |
| Diversification | None | Across 5 indices |

## How It Works

### Startup Phase
```
1. Connect to all 5 markets simultaneously
2. Wait for authorization on each
3. Collect 30 warmup ticks per market
4. Begin monitoring for opportunities
```

### Trading Phase
```
Every 5 seconds:
1. Scan all markets for entry conditions
2. Calculate score for each market
3. Select highest-scoring market
4. Enter trade on that market
5. Exit using same ultra-fast rules
6. Repeat
```

### Example Session
```
Tick 35:  R_100 shows best conditions (score=75) → Enter R_100
Tick 38:  Exit R_100 with +$0.40 profit
Tick 42:  R_25 shows best conditions (score=82) → Enter R_25
Tick 44:  Exit R_25 with +$0.30 profit
Tick 50:  R_50 shows best conditions (score=68) → Enter R_50
Tick 53:  Exit R_50 with +$0.35 profit
Session complete: 3 wins, $1.05 profit ✅
```

## Usage

### Run the Multi-Market Bot

```bash
python multi_market_bot.py
```

### Configuration

Uses the same `.env` file as the single-market bot:

```env
DERIV_API_TOKEN=your_token_here
DERIV_APP_ID=1089
STAKE=1.0
GROWTH_RATE=0.01
TAKE_PROFIT=10.0
STOP_LOSS=5.0
WIN_TARGET=3
```

**Note:** The `SYMBOL` variable is ignored - the bot trades all 5 markets.

## Output Example

```
======================================================================
   MULTI-MARKET ACCUMULATOR BOT
   Markets: R_10, R_25, R_50, R_75, R_100
   Stake: $1.00 | Growth: 1%
   TP: $10.0 | SL: -$5.0 | Win Target: 3
======================================================================
[Bot] Connecting to 5 markets...
[Client] Authorized as VRTC6565689 | Balance: 10000 USD
[Client] Authorized as VRTC6565689 | Balance: 10000 USD
[Client] Authorized as VRTC6565689 | Balance: 10000 USD
[Client] Authorized as VRTC6565689 | Balance: 10000 USD
[Client] Authorized as VRTC6565689 | Balance: 10000 USD
[Bot] All 5 markets connected successfully!
[Bot] Warming up — collecting 30 ticks per market...

[Status] WATCHING | Markets: 5/5 ready | Trades: 0 | Wins: 0 | Losses: 0 | WR: 0% | P&L: +$0.0000
         └─ Best opportunity: R_100 (score=78.5)

[Bot] 🚀 Entering R_100 (score=78.5) | vol=0.00015 | consistency=0.750 | hurst=0.812
[Client] Accumulator started — ID: 313856725468 | Paid: $1.00

[Status] IN TRADE (R_100) | Markets: 5/5 ready | Trades: 0 | Wins: 0 | Losses: 0 | WR: 0% | P&L: +$0.0000
         └─ R_100 tick #2 | P&L: +$0.02

[Bot] 💰 Quick profit (2.0%) on R_100. Selling...
[Bot] ✅ WIN  +$0.02 on R_100 | Session P&L: $0.02 | Trades: 1

[Status] WATCHING | Markets: 5/5 ready | Trades: 1 | Wins: 1 | Losses: 0 | WR: 100% | P&L: +$0.02
         └─ Best opportunity: R_25 (score=85.2)

[Bot] 🚀 Entering R_25 (score=85.2) | vol=0.00012 | consistency=0.800 | hurst=0.875
...
```

## Performance Expectations

### Trade Frequency
- **Single market:** 1-3 trades per 100 ticks
- **Multi-market:** 5-15 trades per 100 ticks (5x more opportunities)

### Session Duration
- **Single market:** 200-500 ticks to complete
- **Multi-market:** 50-150 ticks to complete (much faster)

### Win Rate
- Same as single market: 70-80%
- Better market selection may improve this slightly

## Limitations

### 1. One Trade at a Time
- Bot can only have 1 active trade across all markets
- This is intentional for risk management
- Future version could support multiple simultaneous trades

### 2. API Rate Limits
- Deriv allows multiple connections per account
- No issues expected with 5 markets
- If you see connection errors, reduce number of markets

### 3. Resource Usage
- Uses 5x WebSocket connections
- Minimal CPU/memory impact
- Should run fine on any modern system

## Troubleshooting

### "Only X/5 markets connected"
- Check your internet connection
- Verify API token is valid
- Try reducing number of markets in SYMBOLS list

### "No trades happening"
- All markets may be too volatile
- Wait longer - conditions will improve
- Check that WARMUP_TICKS has passed for all markets

### Frequent knockouts on one market
- That market will go into cooldown automatically
- Bot will trade other markets
- Consider removing problematic market from SYMBOLS list

## Customization

### Change Markets
Edit `SYMBOLS` list in `multi_market_bot.py`:

```python
# Default (all volatility indices)
SYMBOLS = ["R_10", "R_25", "R_50", "R_75", "R_100"]

# Only high-frequency markets
SYMBOLS = ["R_10", "R_25", "R_50"]

# Only R_100 and R_75
SYMBOLS = ["R_75", "R_100"]
```

### Adjust Scoring Weights
Modify `get_entry_score()` in `MarketMonitor` class to change how markets are ranked.

### Add More Markets
You can add other Deriv symbols:
```python
SYMBOLS = ["R_10", "R_25", "R_50", "R_75", "R_100", "BOOM1000", "CRASH1000"]
```

## Comparison: Single vs Multi-Market

### When to Use Single-Market Bot
- Testing a specific market
- Lower resource usage
- Simpler to understand
- Focused strategy

### When to Use Multi-Market Bot
- Maximize trading opportunities
- Faster session completion
- Better market selection
- More consistent activity

## Recommended Setup

For best results with multi-market bot:

```env
STAKE=1.0           # Keep stake low for testing
STOP_LOSS=10.0      # Higher stop loss (more trades = more variance)
TAKE_PROFIT=5.0     # Lower target (faster sessions)
WIN_TARGET=5        # More wins to test across markets
```

This gives you enough trades to see the multi-market advantage while managing risk.
