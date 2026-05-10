# Deriv Accumulator Bot

Trades Deriv accumulator contracts using volatility-based entry timing.

## Strategy

- Enters only when volatility is low, market is trending (Hurst > 0.5), and entropy is calm
- Sells after a target number of ticks to lock in profit
- Sells early if accumulated profit hits 15%
- Cools down after knockouts before re-entering
- Stops trading when session take profit or stop loss is hit

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API token
```

## Config (.env)

| Variable | Default | Description |
|---|---|---|
| `DERIV_API_TOKEN` | — | Your Deriv API token |
| `DERIV_APP_ID` | 1089 | App ID |
| `SYMBOL` | R_10 | R_10 recommended (lowest vol) |
| `STAKE` | 1.0 | Stake per trade in USD |
| `GROWTH_RATE` | 0.01 | 0.01=1%, 0.02=2% ... 0.05=5% |
| `TAKE_PROFIT` | 10.0 | Stop trading after this session profit |
| `STOP_LOSS` | 5.0 | Stop trading after this session loss |
| `TARGET_TICKS` | 20 | Sell after this many ticks in trade |

## Run

```bash
python bot.py
```

## Symbol Recommendation

| Symbol | Volatility | Recommended |
|---|---|---|
| R_10 | Lowest | ✅ Best for accumulators |
| R_25 | Low | ✅ Good |
| R_50 | Medium | ⚠️ Use 1% growth only |
| R_75 | High | ❌ Avoid |
| R_100 | Highest | ❌ Avoid |
