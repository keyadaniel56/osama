# Bot Not Trading - Root Cause & Fixes Applied

## Root Cause: RL System Was a Hard Veto

The RL model had learned a "never trade" policy from previous losses, and was `continue`-ing past every trade signal — even those with **82-88% ensemble confidence**. The decision engine's signals were completely ignored.

## Three Fixes Applied

### Fix 1: RL → Advisory Only (agent.py)
**Before:** `if not rl_should_trade: continue  # HARD BLOCK`
**After:** RL reduces confidence by 15-40% but ensemble gets final say

### Fix 2: Indicator Guard Relaxed (agent.py)
**Before:** Blocked ALL trades at RSI>70 or BB>0.85 
**After:** Only blocks when **ALL evidence** (trend + ML) agrees against the trade

### Fix 3: ML Weight & Lookback (ml_predictor.py, decision_engine.py)
- ML lookback increased from **60 ticks** → **contract duration** (10 min = 600 ticks)
- ML weight in decisions: **20% → 35%** (AI learned from market is trusted more)
- Indicator weight: **15% → 10%**

### Fix 4: Martingale Disabled (risk_manager.py)
**The REAL reason losses exceeded wins** even at 64% win rate:
- With martingale: a single 4x loss (-$1.40) wipes out 5 small wins (+$0.28 each = +$1.40)
- Without martingale: every trade is $0.35 flat — wins/losses balanced by win rate

## Backtest Results (After Fixes)

| Scenario | Trades | Win Rate | P&L |
|---|---|---|---|
| Normal Market | Tested | ~64% overall | Was -$2.31 WITH martingale |
| Last scenario (seed=789, no martingale) | 5 | **60%** | **+$0.42** |

## Honest Assessment: Random Walk Markets

Deriv synthetic indices (R_10, R_25, R_50, R_75, R_100) are **designed as random walks** — no ML model can predict direction above ~52% over long periods. The 60% win rate observed was due to random chance in a small sample.

**Sustainable profitability requires:**
1. ✅ **Only trade trending markets** (100% WR observed) — skip ranging (50% WR = breakeven)
2. ✅ **Disable martingale** (already done — flat $0.35/trade)
3. **Expected value at 52% WR with 80% payout**: 0.52 × 0.28 + 0.48 × (−0.35) = −$0.0224/trade
4. **Breakeven requires 55.6% win rate** at 80% payout

## Final Recommendation

The bot is now working (trading actively, not stuck). But for **true profitability** on synthetic indices, consider:
- Use the bot on **real markets** (forex, stocks) where trends exist
- Or accept that synthetic indices are designed to be unbeatable long-term
- The bot's AI/ML intelligence is best applied to real market data, not synthetic random walks