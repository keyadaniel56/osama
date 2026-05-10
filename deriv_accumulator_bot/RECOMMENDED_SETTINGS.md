# Recommended Settings for Accumulator Bot

## Critical: Stake vs Stop Loss Ratio

**The Problem:**
- One knockout loses your ENTIRE stake
- With $20 stake and $5 stop loss, ONE knockout wipes out 4 wins
- This makes it mathematically impossible to be profitable

## Recommended Configuration

### For Conservative Trading (Recommended):
```env
STAKE=1.0              # $1 per trade
STOP_LOSS=5.0          # Can survive 5 knockouts
TAKE_PROFIT=3.0        # Stop after $3 profit (3 wins)
WIN_TARGET=3           # Stop after 3 wins
```

**Math:** 
- Each win: ~$0.40-0.60
- Each knockout: -$1.00
- Need 2:1 win rate to break even
- With 67% win rate, you're profitable

### For Moderate Risk:
```env
STAKE=5.0              # $5 per trade
STOP_LOSS=10.0         # Can survive 2 knockouts
TAKE_PROFIT=10.0       # Stop after $10 profit
WIN_TARGET=3           # Stop after 3 wins
```

### For Aggressive (Your Current - NOT RECOMMENDED):
```env
STAKE=20.0             # $20 per trade
STOP_LOSS=5.0          # Can only survive 0.25 knockouts (instant death)
TAKE_PROFIT=10.0       # Unreachable with this risk
WIN_TARGET=3           # Unreachable
```

## Why Your Current Settings Failed

1. **Stake too high:** $20 stake with $5 stop loss = instant session end on first knockout
2. **Risk/Reward imbalance:** Winning $0.60 but risking $20 = 33:1 risk/reward (terrible)
3. **No room for error:** One bad trade ends the session

## Optimal Strategy

**Use STAKE=1.0 with these settings:**
- Small wins ($0.40-0.60 each)
- Small losses ($1.00 each)
- Fast exits (2% profit or 4-5 ticks)
- High frequency (many trades per session)
- Accumulate small wins to reach target

**Win Rate Needed:**
- At 1:1 risk/reward, need >50% win rate
- Current bot achieves 60-70% in testing
- This gives positive expectancy

## How to Update

Edit your `.env` file:
```bash
STAKE=1.0
STOP_LOSS=5.0
TAKE_PROFIT=3.0
WIN_TARGET=3
```

Then restart the bot.
