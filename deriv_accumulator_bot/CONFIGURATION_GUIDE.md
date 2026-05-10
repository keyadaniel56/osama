# Bot Configuration Guide

## How to Change Bot Settings

All bot settings are in the `.env` file. Edit this file to customize behavior.

## Available Settings

### Trading Parameters

**`STAKE=20.0`**
- Amount to risk per trade in USD
- Example: `STAKE=10.0` for $10 per trade
- ⚠️ Lower stakes = less risk but also less profit

**`GROWTH_RATE=0.01`**
- Accumulator growth rate per tick
- `0.01` = 1%, `0.02` = 2%, `0.03` = 3%, etc.
- ⚠️ Higher growth = faster profits BUT closer knockout barrier (more risky)
- **Recommended: Keep at 0.01 (1%)**

### Session Control

**`WIN_TARGET=3`** ⭐ **THIS IS WHAT YOU WANT TO CHANGE**
- Number of winning trades before bot stops
- Current: `3` (stops after 3 wins)
- Examples:
  - `WIN_TARGET=10` - Run until 10 wins
  - `WIN_TARGET=20` - Run until 20 wins
  - `WIN_TARGET=100` - Run for a long session
  - `WIN_TARGET=999` - Run almost indefinitely

**`TAKE_PROFIT=10.0`**
- Stop when session profit reaches this amount (USD)
- Example: `TAKE_PROFIT=50.0` to stop at +$50
- Bot stops when EITHER win target OR take profit is reached

**`STOP_LOSS=5.0`**
- Stop when session loss reaches this amount (USD)
- Example: `STOP_LOSS=100.0` to allow -$100 max loss
- ⚠️ With $20 stake, one loss = -$20, so adjust accordingly

### Advanced Settings

**`TARGET_TICKS=20`**
- Maximum ticks to hold a trade (emergency exit)
- **Don't change this** - bot exits much earlier (1-3 ticks) anyway
- This is just a safety backstop

**`SYMBOL=R_100`**
- Only used by single-market bot (`bot.py`)
- Multi-market bot ignores this (monitors all 5 markets)

**`DERIV_API_TOKEN`** and **`DERIV_APP_ID`**
- Your Deriv API credentials
- Don't share these!

## Example Configurations

### Short Session (Current)
```env
WIN_TARGET=3
TAKE_PROFIT=10.0
STOP_LOSS=5.0
```
**Result:** Stops after 3 wins OR +$10 profit OR -$5 loss

### Medium Session
```env
WIN_TARGET=10
TAKE_PROFIT=50.0
STOP_LOSS=20.0
```
**Result:** Stops after 10 wins OR +$50 profit OR -$20 loss

### Long Session
```env
WIN_TARGET=50
TAKE_PROFIT=200.0
STOP_LOSS=100.0
```
**Result:** Stops after 50 wins OR +$200 profit OR -$100 loss

### Almost Unlimited (Profit/Loss Controlled)
```env
WIN_TARGET=999
TAKE_PROFIT=500.0
STOP_LOSS=200.0
```
**Result:** Runs until +$500 profit OR -$200 loss (win target won't be reached)

## How to Apply Changes

1. Edit `.env` file with your preferred settings
2. Save the file
3. Restart the bot:
   ```bash
   python multi_market_bot.py
   ```

The bot will read the new settings on startup.

## Recommendations

### For Testing (Current Setup)
```env
WIN_TARGET=3
STAKE=20.0
```
- Quick sessions to verify bot works
- Low risk exposure

### For Real Trading
```env
WIN_TARGET=20
STAKE=10.0
TAKE_PROFIT=100.0
STOP_LOSS=50.0
```
- Longer sessions
- Lower stake for safety
- Clear profit/loss limits

### For Aggressive Trading
```env
WIN_TARGET=50
STAKE=20.0
TAKE_PROFIT=500.0
STOP_LOSS=200.0
```
- Long sessions
- Higher stakes
- Larger profit targets
- ⚠️ Higher risk!

## Important Notes

1. **The bot will stop when ANY of these conditions are met:**
   - Win target reached
   - Take profit reached
   - Stop loss hit

2. **With the new safety improvements:**
   - Bot is more selective (higher win rate)
   - Trades less frequently (longer wait times)
   - A 50-win session might take 2-4 hours

3. **Risk Management:**
   - With $20 stake: 1 loss = -$20, 1 win = +$0.20
   - You need ~100 wins to recover from 1 loss
   - Consider lowering stake to $5-10 for longer sessions

4. **Monitor Your Balance:**
   - Set `STOP_LOSS` to protect your account
   - Don't set `WIN_TARGET` so high that you risk your entire balance
   - Example: $1000 balance → max `STOP_LOSS=100` (10% risk)
