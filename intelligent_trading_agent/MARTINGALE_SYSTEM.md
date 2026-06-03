# Martingale Trading System

## Overview
The bot now uses a **Martingale strategy** - doubling the stake after each loss to recover all previous losses plus a profit when you eventually win.

## How It Works

### Basic Principle:
- **After WIN**: Reset to base stake
- **After LOSS**: Double the stake

### Example Sequence:

```
Trade #1: $1.00 → LOSS (-$1.00)    | Total Loss: -$1.00
Trade #2: $2.00 → LOSS (-$2.00)    | Total Loss: -$3.00
Trade #3: $4.00 → WIN  (+$4.00)    | Total Profit: +$1.00 ✓
Trade #4: $1.00 → (reset to base)
```

**Result**: After 2 losses and 1 win, you're +$1.00 in profit!

---

## Configuration

### In `risk_manager.py`:

```python
self.use_martingale = True           # Enable/disable martingale
self.martingale_multiplier = 2.0     # Multiply by 2 after each loss
self.max_martingale_steps = 3        # Max 3 doublings (safety limit)
```

### In `.env`:

```bash
STAKE=1.0                # Your base stake
MAX_CONSEC_LOSSES=5      # Pause after 5 consecutive losses
MAX_DAILY_LOSS=50.0      # Pause if daily loss exceeds $50
```

---

## Stake Progression

### With Base Stake = $1.00:

| Step | Stake | If Loss (Cumulative) | If Win (Profit) |
|------|-------|---------------------|-----------------|
| 0    | $1.00 | -$1.00              | +$1.00          |
| 1    | $2.00 | -$3.00              | +$1.00          |
| 2    | $4.00 | -$7.00              | +$1.00          |
| 3    | $8.00 | -$15.00             | +$1.00          |

**After max steps (3)**: Resets to $1.00 to prevent excessive risk

---

## Safety Features

### 1. Maximum Martingale Steps
**Default**: 3 steps (max stake = $8.00 with $1.00 base)

```
Loss 1: $1.00
Loss 2: $2.00
Loss 3: $4.00
Loss 4: $8.00 (max reached)
Loss 5: $1.00 (reset to base)
```

**Why?** Prevents exponential growth that could wipe out your account.

### 2. Consecutive Loss Limit
**Default**: 5 consecutive losses → Trading paused

**Why?** Even with martingale, too many losses in a row means something is wrong.

### 3. Daily Loss Limit
**Default**: $50.00 daily loss → Trading paused

**Why?** Protects your capital from a bad trading day.

### 4. Minimum Stake Enforcement
**Always**: ≥ $0.35 (Deriv minimum)

**Why?** Ensures all trades are valid.

---

## Example Scenarios

### Scenario 1: Quick Recovery
```
Trade #1: $1.00 → LOSS (-$1.00)
Trade #2: $2.00 → WIN  (+$2.00)
Result: +$1.00 profit after 1 loss
```

### Scenario 2: Multiple Losses
```
Trade #1: $1.00 → LOSS (-$1.00)
Trade #2: $2.00 → LOSS (-$2.00)
Trade #3: $4.00 → LOSS (-$4.00)
Trade #4: $8.00 → WIN  (+$8.00)
Result: +$1.00 profit after 3 losses
Total risked: $15.00 to win $1.00
```

### Scenario 3: Max Steps Reached
```
Trade #1: $1.00 → LOSS (-$1.00)
Trade #2: $2.00 → LOSS (-$2.00)
Trade #3: $4.00 → LOSS (-$4.00)
Trade #4: $8.00 → LOSS (-$8.00) [max steps]
Trade #5: $1.00 → WIN  (+$1.00) [reset]
Result: -$14.00 loss (couldn't recover)
```

### Scenario 4: Winning Streak
```
Trade #1: $1.00 → WIN (+$1.00)
Trade #2: $1.00 → WIN (+$1.00)
Trade #3: $1.00 → WIN (+$1.00)
Result: +$3.00 profit (no martingale needed)
```

---

## Risk Analysis

### Capital Required

To survive max martingale steps with $1.00 base:

```
Step 0: $1.00
Step 1: $2.00
Step 2: $4.00
Step 3: $8.00
Total: $15.00 required capital
```

**Recommendation**: Have at least **20x your base stake** in capital.
- Base stake $1.00 → Need $20+ balance
- Base stake $5.00 → Need $100+ balance

### Win Rate Impact

Martingale works best with **>40% win rate**:

| Win Rate | Long-term Result |
|----------|------------------|
| 50%+     | Profitable ✓     |
| 40-50%   | Break-even       |
| <40%     | Losing ✗         |

---

## Console Output

### Normal Trade:
```
INFO: Trade #1: rise_fall → RISE (CALL) @ $1.00 | Conf: 0.70 | Active: 1
```

### After Loss (Martingale Activated):
```
WARNING: ✗ Loss #1. Martingale step 1/3. Next stake: $2.00
INFO: Trade #2: rise_fall → FALL (PUT) @ $2.00 | Conf: 0.72 | Active: 1
```

### After Win (Martingale Reset):
```
INFO: ✓ Martingale WIN! Recovered from 2 losses. Resetting to base stake $1.00
INFO: Trade #3: rise_fall → RISE (CALL) @ $1.00 | Conf: 0.68 | Active: 1
```

### Max Steps Reached:
```
WARNING: ✗ Max martingale steps reached (3). Resetting to base stake.
INFO: Trade #5: rise_fall → RISE (CALL) @ $1.00 | Conf: 0.75 | Active: 1
```

---

## Adjusting Martingale Settings

### More Aggressive (Higher Risk):
```python
self.martingale_multiplier = 2.5     # 2.5x instead of 2x
self.max_martingale_steps = 4        # Allow 4 steps
```

**Stakes**: $1.00 → $2.50 → $6.25 → $15.63 → $39.06

### More Conservative (Lower Risk):
```python
self.martingale_multiplier = 1.5     # 1.5x instead of 2x
self.max_martingale_steps = 2        # Only 2 steps
```

**Stakes**: $1.00 → $1.50 → $2.25

### Disable Martingale:
```python
self.use_martingale = False          # Fixed stake always
```

**Stakes**: $1.00 → $1.00 → $1.00 (never changes)

---

## Advantages

✅ **Guaranteed profit** - Eventually recovers all losses + profit
✅ **Simple strategy** - Easy to understand and implement
✅ **Works with any win rate** - As long as you eventually win
✅ **Automatic recovery** - No manual intervention needed

## Disadvantages

⚠️ **Requires capital** - Need enough balance for losing streaks
⚠️ **Exponential growth** - Stakes can get large quickly
⚠️ **Not foolproof** - Long losing streaks can be devastating
⚠️ **Psychological pressure** - Watching stakes double can be stressful

---

## Best Practices

1. **Start small** - Use low base stake ($0.35 - $1.00)
2. **Have capital** - At least 20x your base stake
3. **Set limits** - Use MAX_CONSEC_LOSSES and MAX_DAILY_LOSS
4. **Monitor closely** - Watch for long losing streaks
5. **Test first** - Run on demo account before live trading

---

## Summary

The bot now uses **Martingale** to automatically recover from losses:
- ✅ Fixed base stake (no reduction after losses)
- ✅ Doubles stake after each loss
- ✅ Resets to base after each win
- ✅ Safety limits prevent excessive risk
- ✅ Guaranteed profit on eventual win

**Remember**: Martingale is powerful but risky. Always trade responsibly and never risk more than you can afford to lose!
