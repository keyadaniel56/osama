# Stake Amount Fix - Deriv Minimum Compliance

## Issue Fixed
The bot's adaptive risk reduction could reduce stake below Deriv's minimum of $0.35, causing invalid trades.

## Changes Made

### 1. Added Deriv Minimum Stake Constant ✅
**Location:** `config.py`

```python
MIN_STAKE_AMOUNT = 0.35  # Deriv minimum stake
```

### 2. Enforced Minimum in Position Size Calculation ✅
**Location:** `risk_manager.py` - `calculate_position_size()`

```python
# Use base stake with only the adaptive stake multiplier
position_size = self.base_stake * self.stake_multiplier

# Enforce Deriv minimum stake
position_size = max(position_size, MIN_STAKE_AMOUNT)

# Round to 2 decimal places
position_size = round(position_size, 2)
```

### 3. Updated Consecutive Loss Handling ✅
**Location:** `risk_manager.py` - `_check_pause_conditions()`

Instead of reducing stake by 20% repeatedly (which could go below $0.35), the bot now:
- Sets stake to exactly $0.35 when hitting consecutive loss limit
- Increases confidence threshold to be more selective

```python
# Set stake to minimum instead of reducing further
self.stake_multiplier = MIN_STAKE_AMOUNT / self.base_stake
```

---

## Stake Behavior Now

### Normal Trading (No Losses):
```
Stake: $1.00 (your configured BASE_STAKE)
```

### After Consecutive Losses:
```
Loss 1: $1.00 (no change yet)
Loss 2: $1.00 (no change yet)
Loss 3: $0.35 (minimum enforced)
Loss 4: $0.35 (stays at minimum)
```

### After Wins (Recovery):
```
Win 1: $0.39 (10% increase from $0.35)
Win 2: $0.43
Win 3: $0.47
Win 4: $0.52
...continues until back to $1.00
```

---

## Validation

### Minimum Stake Check:
✅ **Always ≥ $0.35** - Enforced in `calculate_position_size()`

### Maximum Stake Check:
✅ **Starts at $1.00** - Your configured BASE_STAKE

### Adaptive Behavior:
✅ **Reduces on losses** - But never below $0.35
✅ **Recovers on wins** - Gradually back to $1.00

---

## Configuration

You can adjust these values in `.env` or `config.py`:

```bash
# .env
STAKE=1.0                    # Your base stake amount
```

```python
# config.py (hardcoded)
MIN_STAKE_AMOUNT = 0.35      # Deriv minimum (don't change)
```

---

## Examples

### Example 1: Starting Fresh
```
Trade #1: $1.00 (base stake)
Trade #2: $1.00 (base stake)
Trade #3: $1.00 (base stake)
```

### Example 2: Losing Streak
```
Trade #1: $1.00 → LOSS
Trade #2: $1.00 → LOSS
Trade #3: $1.00 → LOSS (consecutive limit reached)
Trade #4: $0.35 → (minimum enforced)
Trade #5: $0.35 → WIN
Trade #6: $0.39 → (recovering)
```

### Example 3: Mixed Results
```
Trade #1: $1.00 → WIN
Trade #2: $1.00 → LOSS
Trade #3: $1.00 → LOSS
Trade #4: $1.00 → LOSS (consecutive limit)
Trade #5: $0.35 → WIN (minimum)
Trade #6: $0.39 → WIN (recovering)
Trade #7: $0.43 → WIN
Trade #8: $0.47 → LOSS
Trade #9: $0.47 → WIN
Trade #10: $0.52 → (continues recovering)
```

---

## Why This Matters

### Before Fix:
- Stake could go: $1.00 → $0.80 → $0.64 → $0.51 → $0.41 → $0.33 → **$0.26** ❌
- **$0.26 < $0.35** = Invalid trade rejected by Deriv

### After Fix:
- Stake goes: $1.00 → $1.00 → $1.00 → **$0.35** ✅
- **$0.35 ≥ $0.35** = Valid trade accepted by Deriv

---

## Summary

✅ **Minimum stake enforced** - Never goes below $0.35
✅ **Deriv compliant** - All trades will be accepted
✅ **Adaptive risk still works** - Reduces to minimum on losses
✅ **Recovery mechanism** - Gradually increases back to base stake
✅ **Simple and predictable** - Easy to understand behavior

The bot will now always place valid trades that meet Deriv's minimum stake requirement!
