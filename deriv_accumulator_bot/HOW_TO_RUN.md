# How to Run the Bots

## Two Bots Available

You have **two different bots** in this folder:

### 1. Single-Market Bot (`bot.py`)
**Watches:** Only 1 market (R_100 by default)

**Run with:**
```bash
python bot.py
```

**Output looks like:**
```
============================================================
   DERIV ACCUMULATOR BOT
   Symbol: R_100 | Growth: 1% | Stake: $20.00
============================================================
[Bot] Warming up — collecting 30 ticks before trading...
[Status] WATCHING | Ticks: 37 | Trades: 0 | Wins: 0 | KOs: 0
[Bot] Waiting — vol too high=0.00037
```

**Problem:** If R_100 is too volatile, you just wait. No trading happens.

---

### 2. Multi-Market Bot (`multi_market_bot.py`)
**Watches:** 5 markets simultaneously (R_10, R_25, R_50, R_75, R_100)

**Run with:**
```bash
python multi_market_bot.py
```

**Or use the launcher:**
```bash
./run_multi_market.sh
```

**Output looks like:**
```
======================================================================
   MULTI-MARKET ACCUMULATOR BOT
   Markets: R_10, R_25, R_50, R_75, R_100
   Stake: $20.00 | Growth: 1%
======================================================================
[Bot] Connecting to 5 markets...
[Client] Authorized as VRTC6565689 | Balance: 10002 USD  (R_10)
[Client] Authorized as VRTC6565689 | Balance: 10002 USD  (R_25)
[Client] Authorized as VRTC6565689 | Balance: 10002 USD  (R_50)
[Client] Authorized as VRTC6565689 | Balance: 10002 USD  (R_75)
[Client] Authorized as VRTC6565689 | Balance: 10002 USD  (R_100)
[Bot] All 5 markets connected succes