# Tick Stream Health Monitoring & Auto-Resubscription Fix

## Problem
The bot would appear to "stop" or get "stuck" after running for a while:
- Loop is running (heartbeat logs show iterations increasing)
- Bot is connected and authorized
- Bot receives `proposal_open_contract` messages (contract updates)
- **BUT NO `tick` messages are being received**
- `tick_count` gets stuck at a certain number (e.g., 506)
- Tick history counts stop increasing (e.g., stuck at 494)

### User Symptoms
```
INFO: Decision Engine: UP | Confidence: 80.7% | Market Health: 55.0/100
INFO: 📈 Using rise_fall strategy (trend following) for UP signal
INFO: 🎯 Ensemble decision: UP (conf=0.80) overrides strategy confidence
INFO: Received: proposal_open_contract
INFO: Received: proposal_open_contract
[Bot appears stuck here - no new ticks, no trades]
```

## Root Cause
**Deriv API stops sending tick messages** after some time, but:
- WebSocket connection remains open
- Bot still receives contract updates
- No error messages or disconnection events
- Tick subscription silently dies

This is likely due to:
1. Deriv API subscription timeout (server-side)
2. Network hiccups that drop the subscription but not the connection
3. Deriv API rate limiting or subscription limits

## Solution: Tick Health Monitoring

### 1. Track Last Tick Time
Added tracking of when each symbol last received a tick:

```python
# In DerivClient.__init__
self.last_tick_time: Dict[str, float] = {sym: time.time() for sym in self.symbols}
self.tick_timeout = 30  # seconds - if no tick for 30s, resubscribe
self.subscription_ids: Dict[str, str] = {}  # For resubscription
```

### 2. Update Tick Time on Receipt
Every time a tick is received, update the timestamp:

```python
def _handle_tick(self, data: Dict):
    # ... existing code ...
    
    # Update last tick time for health monitoring
    self.last_tick_time[symbol] = time.time()
    
    # Store subscription ID for potential resubscription
    subscription_id = data.get("subscription", {}).get("id")
    if subscription_id and symbol:
        self.subscription_ids[symbol] = subscription_id
```

### 3. Health Check Method
Added method to check if ticks are flowing:

```python
def check_tick_health(self) -> Dict[str, bool]:
    """
    Check if ticks are flowing for all symbols.
    Returns dict of symbol -> is_healthy (True if ticks received recently).
    """
    current_time = time.time()
    health_status = {}
    
    for symbol in self.symbols:
        last_tick = self.last_tick_time.get(symbol, 0)
        time_since_tick = current_time - last_tick
        is_healthy = time_since_tick < self.tick_timeout
        health_status[symbol] = is_healthy
        
        if not is_healthy and self.connected and self.authorized:
            agent_logger.log_warning(
                f"⚠️ Tick timeout for {symbol}: {time_since_tick:.1f}s since last tick "
                f"(threshold: {self.tick_timeout}s)"
            )
    
    return health_status
```

### 4. Resubscription Method
Added method to resubscribe to tick streams:

```python
def resubscribe_to_ticks(self, symbol: str = None):
    """
    Resubscribe to tick stream for a symbol (or all symbols if None).
    Use this when ticks stop flowing.
    """
    symbols_to_resubscribe = [symbol] if symbol else self.symbols
    
    for sym in symbols_to_resubscribe:
        agent_logger.log_info(f"🔄 Resubscribing to ticks for {sym}...")
        
        # Unsubscribe first if we have a subscription ID
        if sym in self.subscription_ids:
            self._send({
                "forget": self.subscription_ids[sym]
            })
            agent_logger.log_info(f"🔕 Unsubscribed from old tick stream: {sym}")
            del self.subscription_ids[sym]
        
        # Subscribe again
        self._send({
            "ticks": sym,
            "subscribe": 1
        })
        self.last_tick_time[sym] = time.time()
        agent_logger.log_info(f"✅ Resubscribed to ticks: {sym}")
```

### 5. Periodic Health Check in Trading Loop
Added health check every 100 loop iterations (~10 seconds):

```python
# In agent.py _trading_loop()
if loop_iterations % 100 == 0:
    tick_health = self.client.check_tick_health()
    unhealthy_symbols = [sym for sym, healthy in tick_health.items() if not healthy]
    
    if unhealthy_symbols:
        agent_logger.log_warning(
            f"⚠️ Tick stream unhealthy for: {', '.join(unhealthy_symbols)} - Resubscribing..."
        )
        for sym in unhealthy_symbols:
            self.client.resubscribe_to_ticks(sym)
```

## How It Works Now

### Normal Operation:
1. Bot subscribes to tick streams ✅
2. Ticks flow continuously ✅
3. Health check passes (ticks received within 30s) ✅
4. Trading continues normally ✅

### When Ticks Stop:
1. Deriv stops sending ticks (subscription dies) ❌
2. 30 seconds pass with no ticks ⏱️
3. Health check detects timeout ⚠️
4. Bot logs warning and resubscribes 🔄
5. Ticks start flowing again ✅
6. Trading resumes ✅

## Expected Logs

### When Ticks Are Healthy:
```
INFO: 💓 Loop heartbeat: iteration 1000, tick_count=523, active_contracts=1
INFO: Decision Engine: UP | Confidence: 78.0% | Market Health: 65.0/100
INFO: ✅ Trade signal: UP | Ensemble: 78.00%
```

### When Ticks Stop and Recover:
```
INFO: 💓 Loop heartbeat: iteration 1000, tick_count=506, active_contracts=0
WARNING: ⚠️ Tick timeout for R_100: 32.5s since last tick (threshold: 30s)
WARNING: ⚠️ Tick stream unhealthy for: R_100 - Resubscribing...
INFO: 🔄 Resubscribing to ticks for R_100...
INFO: 🔕 Unsubscribed from old tick stream: R_100
INFO: ✅ Resubscribed to ticks: R_100
INFO: 📊 Tick milestone: R_100 has 500 ticks
INFO: Decision Engine: UP | Confidence: 80.0% | Market Health: 70.0/100
```

## Configuration

### Tick Timeout Setting
Default: 30 seconds (configurable in `deriv_client.py`)

```python
self.tick_timeout = 30  # seconds
```

**Adjust based on your needs:**
- **Lower (15-20s)**: Faster detection, more aggressive resubscription
- **Higher (45-60s)**: More tolerant of temporary slowdowns
- **Recommended**: 30s is a good balance

### Health Check Frequency
Default: Every 100 loop iterations (~10 seconds)

```python
if loop_iterations % 100 == 0:
    tick_health = self.client.check_tick_health()
```

**Adjust based on your needs:**
- **More frequent (50)**: Faster detection, more CPU usage
- **Less frequent (200)**: Lower overhead, slower detection
- **Recommended**: 100 is a good balance

## Benefits

1. **Automatic Recovery**: Bot automatically recovers from tick stream failures
2. **No Manual Intervention**: No need to restart the bot when ticks stop
3. **Continuous Trading**: Minimizes downtime and missed opportunities
4. **Clear Diagnostics**: Logs show exactly when and why resubscription happens
5. **Multi-Symbol Support**: Monitors and resubscribes each symbol independently

## Testing

1. **Start the bot** and let it run normally
2. **Wait for tick timeout** (or simulate by blocking network briefly)
3. **Verify logs show**:
   - Tick timeout warning
   - Resubscription attempt
   - Successful resubscription
   - Ticks flowing again
4. **Verify trading resumes** after resubscription

## Files Modified

- `deriv_client.py`:
  - Added `last_tick_time` tracking
  - Added `subscription_ids` storage
  - Added `check_tick_health()` method
  - Added `resubscribe_to_ticks()` method
  - Updated `_handle_tick()` to track timestamps
  - Updated `_subscribe_ticks()` to reset timestamps

- `agent.py`:
  - Added periodic tick health check in `_trading_loop()`
  - Added automatic resubscription when unhealthy

## Related Fixes

This fix builds on previous fixes:
- **BOT_NOT_TRADING_FIX.md**: Fixed ensemble decision logic
- **RECONNECTION_STUCK_FIX.md**: Fixed reconnection handling
- **BOT_STOPS_TRADING_FIX.md**: Fixed unsubscribe from closed contracts

Together, these fixes ensure the bot:
1. ✅ Reconnects after network disconnection
2. ✅ Resumes trading after reconnection
3. ✅ Unsubscribes from closed contracts
4. ✅ Resubscribes when tick stream dies
5. ✅ Places trades when signals are generated

## Next Steps

If the bot still stops after this fix:
1. Check logs for tick timeout warnings
2. Verify resubscription is happening
3. Check if ticks resume after resubscription
4. If ticks don't resume, may be a Deriv API issue
5. Consider adding full WebSocket reconnection as fallback
