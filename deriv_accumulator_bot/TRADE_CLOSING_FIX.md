# Trade Closing Fix

## Problem Identified

The bot was sometimes failing to close the last trade because of a **sell request blocking mechanism** in the client.

### Root Cause

In `client.py`, the `sell_contract()` method had a `_sell_requested` flag that prevented duplicate sell requests:

```python
def sell_contract(self):
    if self._active_contract_id and not self._sell_requested:  # ❌ Blocks retries
        self._sell_requested = True
        # ... send sell request
```

**The Issue:**
1. Bot calls `sell_contract()` → sets `_sell_requested = True`
2. If the sell request fails or gets delayed by the server
3. Bot tries to retry at tick 4+ but `sell_contract()` returns early because `_sell_requested` is already `True`
4. Trade never closes → user has to manually close it

## Solution Implemented

### 1. Added `force_retry` Parameter to `sell_contract()`

```python
def sell_contract(self, force_retry: bool = False):
    """
    Sell the active accumulator contract.
    
    Args:
        force_retry: If True, allows retry even if sell was already requested.
    """
    if self._active_contract_id:
        if force_retry or not self._sell_requested:  # ✅ Allows forced retries
            self._sell_requested = True
            # ... send sell request
```

### 2. Updated Retry Logic in Both Bots

**In `_on_contract_update()` method:**

```python
# If we're past tick 4 and still in trade, force retry
elif self._ticks_in_trade >= 4:
    print(f"[Bot] 🔄 Retry selling at tick {self._ticks_in_trade}")
    self.client.sell_contract(force_retry=True)  # ✅ Force retry
```

### 3. Added Force-Close on Session Completion

New method `_force_close_active_trade()` that:
- Checks if there's an active trade when session ends
- Forces a sell with `force_retry=True`
- Waits 2 seconds for the sell to process

Called when:
- Win target reached
- Take profit hit
- Stop loss hit

## What This Fixes

✅ **Retry attempts now work** - Bot can retry selling even if previous attempt failed  
✅ **Session completion is clean** - Active trades are force-closed when session ends  
✅ **No more stuck trades** - Multiple retry attempts ensure trades close  
✅ **Better reliability** - Handles network delays and server-side issues  

## Testing Recommendations

1. Run the bot and watch for the retry messages:
   - `⚠️ Emergency exit` at tick 3
   - `🔄 Retry selling` at tick 4+
   
2. Verify trades close properly when:
   - Win target is reached
   - Session completes
   - Emergency exit triggers

3. Check that you don't need to manually close trades anymore

## Files Modified

- `deriv_accumulator_bot/client.py` - Added `force_retry` parameter
- `deriv_accumulator_bot/bot.py` - Updated retry logic + force-close method
- `deriv_accumulator_bot/multi_market_bot.py` - Updated retry logic + force-close method
