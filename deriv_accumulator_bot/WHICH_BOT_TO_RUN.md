# Which Bot Should I Run?

## You Have TWO Bots Available:

### 1. **Single Market Bot** (`bot.py`)
- Watches **ONE market only** (default: R_10)
- Waits for that specific market to have good conditions
- Can be slow if that market is choppy

**Run with:**
```bash
python bot.py
```

---

### 2. **Multi-Market Bot** (`multi_market_bot.py`) ⭐ RECOMMENDED
- Watches **5 markets simultaneously** (R_10, R_25, R_50, R_75, R_100)
- Trades whichever market has the best conditions at any moment
- Much faster to find trades (typically 2-3 minutes vs 15-30 minutes)
- Same ultra-defensive strategy as single market bot

**Run with:**
```bash
python multi_market_bot.py
```

**Or use the convenience script:**
```bash
bash run_multi_market.sh
```

---

## Your Recent Issue

You ran:
```bash
python bot.py  # ❌ This is the SINGLE market bot
```

This only watches R_100, which is why you saw:
```
Symbol: R_100 | Growth: 1% | Stake: $20.00
```

To watch **all markets at the same time**, run:
```bash
python multi_market_bot.py  # ✅ This watches 5 markets
```

You'll see output like:
```
Markets: R_10, R_25, R_50, R_75, R_100
Markets: 5/5 ready
Best opportunity: R_25 (score=78.3)
```

---

## Both Bots Use the Same Strategy

- Same entry conditions (low volatility, high consistency, trending)
- Same exit rules (1% profit OR 2 ticks OR emergency at 3 ticks)
- Same risk management
- Same .env configuration

The **only difference** is that multi-market bot monitors multiple markets and picks the best one.

---

## Quick Start

1. Make sure your `.env` file is configured
2. Run: `python multi_market_bot.py`
3. Watch it monitor all 5 markets simultaneously
4. It will automatically trade the market with best conditions
