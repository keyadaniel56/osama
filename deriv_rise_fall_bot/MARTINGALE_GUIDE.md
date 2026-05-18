# Martingale Strategy Guide

## What is Martingale?

Martingale is a betting strategy where you **double your stake after each loss** to recover previous losses and gain a profit equal to the original stake when you eventually win.

### Example:
```
Trade 1: Stake $1 → LOSS (-$1) | Total: -$1
Trade 2: Stake $2 → LOSS (-$2) | Total: -$3
Trade 3: Stake $4 → WIN (+$4)  | Total: +$1 ✅
```

After 2 losses and 1 win, you're back to +$1 profit (your original stake).

## Configuration

Edit `.env` file:

```bash
# Enable/Disable Martingale
ENABLE_MARTINGALE=true          # Set to 'false' to disable

# Martingale Settings
MARTINGALE_MULTIPLIER=2.0       # Stake multiplier after loss (2.0 = double)
MAX_MARTINGALE_STEPS=3          # Maximum consecutive doublings
```

### Parameters Explained

**ENABLE_MARTINGALE**
- `true`: Martingale is active
- `false`: Fixed stake (no martingale)

**MARTINGALE_MULTIPLIER**
- `2.0`: Double stake after each loss (classic martingale)
- `1.5`: Increase by 50% (conservative)
- `3.0`: Triple stake (aggressive, not recommended)

**MAX_MARTINGALE_STEPS**
- Maximum number of times to increase stake
- After reaching max, resets to base stake
- Prevents unlimited stake growth

## How It Works

### Step-by-Step Example

**Configuration:**
- Base Stake: $1
- Multiplier: 2.0x
- Max Steps: 3

**Trading Sequence:**

```
Step 0: Stake $1.00 → LOSS (-$1.00) | Total: -$1.00
  ↓ Martingale: Increase to $2.00 (Step 1/3)

Step 1: Stake $2.00 → LOSS (-$2.00) | Total: -$3.00
  ↓ Martingale: Increase to $4.00 (Step 2/3)

Step 2: Stake $4.00 → LOSS (-$4.00) | Total: -$7.00
  ↓ Martingale: Increase to $8.00 (Step 3/3)

Step 3: Stake $8.00 → WIN (+$8.00)  | Total: +$1.00 ✅
  ↓ Martingale: Reset to $1.00 (Step 0)

Step 0: Stake $1.00 → (continues...)
```

### If Max Steps Reached

```
Step 3: Stake $8.00 → LOSS (-$8.00) | Total: -$15.00
  ↓ Max steps reached! Reset to $1.00

Step 0: Stake $1.00 → (starts over)
```

## Advantages

✅ **Loss Recovery**: Recovers all previous losses with one win
✅ **Profit Guarantee**: Always profits by base stake amount on win
✅ **Psychological**: Reduces impact of losing streaks
✅ **Automated**: Bot handles stake calculations automatically

## Risks & Warnings

⚠️ **Exponential Growth**: Stakes grow very quickly
- Step 0: $1
- Step 1: $2
- Step 2: $4
- Step 3: $8
- Step 4: $16
- Step 5: $32
- Step 6: $64
- Step 7: $128

⚠️ **Capital Requirements**: Need sufficient balance
- 3 steps with $1 base = $15 total risk
- 5 steps with $1 base = $63 total risk
- 7 steps with $1 base = $255 total risk

⚠️ **Broker Limits**: Deriv has maximum stake limits
- Check your account's max stake per trade
- Bot will fail if stake exceeds limit

⚠️ **Long Losing Streaks**: Can deplete account quickly
- 5 consecutive losses = 31x base stake lost
- 7 consecutive losses = 127x base stake lost

⚠️ **Not a Holy Grail**: Doesn't change win probability
- If win rate < 50%, you'll lose long-term
- Martingale only helps recover short-term losses

## Recommended Settings

### Conservative (Recommended for Beginners)
```bash
STAKE=0.35
ENABLE_MARTINGALE=true
MARTINGALE_MULTIPLIER=2.0
MAX_MARTINGALE_STEPS=2
```
- Max risk: $1.05 (3 trades)
- Suitable for $50+ balance

### Moderate
```bash
STAKE=1.0
ENABLE_MARTINGALE=true
MARTINGALE_MULTIPLIER=2.0
MAX_MARTINGALE_STEPS=3
```
- Max risk: $7.00 (4 trades)
- Suitable for $100+ balance

### Aggressive (High Risk)
```bash
STAKE=1.0
ENABLE_MARTINGALE=true
MARTINGALE_MULTIPLIER=2.0
MAX_MARTINGALE_STEPS=5
```
- Max risk: $31.00 (6 trades)
- Suitable for $500+ balance
- **Not recommended for beginners**

## Safety Tips

### 1. Calculate Maximum Risk
Formula: `Max Risk = Base Stake × (2^(Steps+1) - 1)`

Examples:
- $1 base, 2 steps: $1 × (2³ - 1) = $7
- $1 base, 3 steps: $1 × (2⁴ - 1) = $15
- $1 base, 5 steps: $1 × (2⁶ - 1) = $63

### 2. Set Appropriate Stop Loss
```bash
STOP_LOSS=20.0  # Stop if loss reaches $20
```
Prevents catastrophic losses during bad streaks.

### 3. Use Conservative Max Steps
- Start with 2-3 steps maximum
- Only increase after testing thoroughly
- Never exceed 5 steps unless you have large capital

### 4. Monitor Your Balance
- Ensure balance > 10x max risk
- Example: $15 max risk → need $150+ balance
- Leave buffer for multiple martingale sequences

### 5. Combine with Good Win Rate
- Martingale works best with 55%+ win rate
- If win rate < 50%, disable martingale
- Focus on improving prediction accuracy first

## When to Use Martingale

✅ **Good Scenarios:**
- Win rate consistently > 55%
- Sufficient account balance (10x+ max risk)
- Short-term loss recovery
- Stable market conditions
- Testing with small base stakes

❌ **Bad Scenarios:**
- Win rate < 50%
- Small account balance
- Highly volatile markets
- Long losing streaks common
- Near broker stake limits

## Disabling Martingale

To trade with fixed stakes:

```bash
ENABLE_MARTINGALE=false
```

Bot will use constant `STAKE` amount for all trades.

## Monitoring Martingale

### Bot Output

**During Trade:**
```
🎯 TRADE | RISE | Confidence: 0.75 | Source: ml | Stake: $4.00 | 📈 Martingale Step 2/3
```

**After Loss:**
```
❌ LOSS (Martingale Step 2) | Loss: $4.00 | Total: -$7.00
📈 Martingale: Increasing stake from $4.00 to $8.00 (Step 3/3)
```

**After Win:**
```
✅ WIN (Martingale Step 3) | Profit: $8.00 | Total: +$1.00
🎯 Martingale WIN! Resetting stake from $8.00 to $1.00
```

**Max Steps Reached:**
```
⚠️ Martingale limit reached! Resetting to base stake $1.00
```

### Status Display
```
📊 Status | Trades: 15 | W/L: 10/5 | Win Rate: 66.7% | P&L: $5.50 | 📈 Martingale: Step 2/3
```

## Mathematical Reality

### Win Probability After N Losses

Assuming 50% win rate per trade:

| Losses | Probability | Cumulative Loss |
|--------|-------------|-----------------|
| 1      | 50.0%       | -$1             |
| 2      | 25.0%       | -$3             |
| 3      | 12.5%       | -$7             |
| 4      | 6.25%       | -$15            |
| 5      | 3.13%       | -$31            |
| 6      | 1.56%       | -$63            |
| 7      | 0.78%       | -$127           |

**Key Insight:** Even with 50% win rate, you have 1.56% chance of 6 consecutive losses, which would cost $63 with $1 base stake.

### Expected Value

Martingale **does not change** the expected value of your trades:
- If win rate = 50% and payout = 1:1, EV = 0 (break even)
- If win rate = 55% and payout = 0.95:1, EV = positive
- If win rate = 45% and payout = 0.95:1, EV = negative

Martingale only affects **variance** and **risk of ruin**, not long-term profitability.

## Alternatives to Classic Martingale

### 1. Anti-Martingale (Reverse Martingale)
Increase stake after **wins** instead of losses:
```bash
# Not implemented in this bot
# Increases stake on winning streaks
# Reduces stake after losses
```

### 2. D'Alembert System
Increase stake by fixed amount instead of doubling:
```bash
MARTINGALE_MULTIPLIER=1.5  # Increase by 50% instead of 100%
```

### 3. Fibonacci System
Use Fibonacci sequence for stake progression:
```bash
# Not implemented in this bot
# Sequence: 1, 1, 2, 3, 5, 8, 13...
```

## Conclusion

Martingale is a **powerful but risky** strategy:

✅ **Use it if:**
- You have good win rate (55%+)
- Sufficient capital (10x+ max risk)
- Conservative settings (2-3 steps max)
- Combined with stop loss protection

❌ **Avoid it if:**
- Win rate < 50%
- Limited capital
- Prone to long losing streaks
- Near broker limits

**Remember:** Martingale is a money management strategy, not a trading edge. Focus on improving prediction accuracy first, then use martingale conservatively to manage drawdowns.

---

**Disclaimer:** Martingale carries significant risk of large losses. Only use with money you can afford to lose. Past performance does not guarantee future results.
