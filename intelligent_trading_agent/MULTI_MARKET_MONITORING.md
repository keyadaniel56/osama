# Multi-Market Monitoring System

## Overview

The trading agent now actively monitors **multiple markets simultaneously** and automatically switches to the best trading opportunities in real-time.

## Features

### 1. **Simultaneous Market Monitoring**
- Monitors all 5 synthetic indices: `R_100`, `R_75`, `R_50`, `R_25`, `R_10`
- Each market has its own:
  - Market Analyzer (technical indicators, state detection)
  - Strategy Selector (strategy matching)
  - Pattern Recognizer (chart patterns)
  - Performance tracker (win rate, profit/loss)

### 2. **Intelligent Market Switching**
- Scans all markets every **25 ticks** (every ~25 seconds)
- Calculates opportunity score for each market (0-100)
- Automatically switches to better markets when score difference > 10 points
- Preserves context when switching (no data loss)

### 3. **Opportunity Scoring System**

Each market is scored based on:
```
Base Score: 50 points
+ Confidence: up to 20 points (strategy confidence × 20)
+ Health: up to 20 points (market health / 100 × 20)
+ Patterns: up to 10 points (5 points per pattern detected, max 10)
= Total: 0-100 points
```

**Example Scores:**
- Score 90+: Excellent opportunity (high confidence, healthy market, multiple patterns)
- Score 70-89: Good opportunity (decent confidence, stable market)
- Score 50-69: Moderate opportunity (acceptable conditions)
- Score <50: Poor opportunity (low confidence or unhealthy market)

### 4. **Real-Time Market Dashboard**

Every 100 ticks, the agent logs a comprehensive market status:

```
================================================================================
📊 MULTI-MARKET STATUS (Tick 500)
================================================================================
🎯 R_100    | Score:  85.5 | Health:  78.2 | State: trending_up     | Strategy: higher_lower | Opp: ✓ | Patterns: double_bottom, breakout
   R_75     | Score:  72.3 | Health:  65.0 | State: ranging         | Strategy: accumulator  | Opp: ✓ | Patterns: support_resistance
   R_50     | Score:  68.1 | Health:  70.5 | State: volatile        | Strategy: hold         | Opp: ✗ | Patterns: none
   R_25     | Score:  55.0 | Health:  52.0 | State: calm            | Strategy: rise_fall    | Opp: ✓ | Patterns: triangle
   R_10     | Score:  45.2 | Health:  48.0 | State: unknown         | Strategy: hold         | Opp: ✗ | Patterns: none
================================================================================
📈 PERFORMANCE BY MARKET:
  R_100: 5W/2L (71.4%) | Profit: $12.50
  R_75: 3W/3L (50.0%) | Profit: $0.00
  R_50: 2W/1L (66.7%) | Profit: $3.25
================================================================================
```

**Legend:**
- 🎯 = Currently trading this market
- ✓ = Has trading opportunity
- ✗ = No opportunity (conditions not met)

### 5. **Performance Tracking by Market**

The system tracks performance for each market separately:
- Total trades per market
- Win/loss count
- Win rate percentage
- Total profit/loss
- Average profit per trade

This helps identify which markets perform best with your strategy.

### 6. **Market Switching Logic**

The agent switches markets when:
1. A different market has a score **10+ points higher** than current market
2. The new market has an active trading opportunity
3. Market health is acceptable (>50)

**Example:**
```
Current: R_100 (score=65.0)
Scanning: R_75 (score=78.5) ← 13.5 points higher!

🔄 Switching markets: R_100 (score=65.0) → R_75 (score=78.5)
📊 New market: R_75 | State: trending_up | Strategy: higher_lower | Confidence: 0.72
```

### 7. **Pattern Detection Across Markets**

Each market independently detects patterns:
- Head & Shoulders
- Double Top/Bottom
- Triangles
- Flags & Wedges
- Breakouts
- Support/Resistance

The agent can identify which markets are showing bullish/bearish patterns and prioritize them.

## Configuration

### Enable Multi-Market Monitoring

Multi-market monitoring is **automatically enabled** when `AVAILABLE_SYMBOLS` has more than 1 symbol.

In `config.py`:
```python
AVAILABLE_SYMBOLS = ["R_100", "R_75", "R_50", "R_25", "R_10"]  # All 5 markets
DEFAULT_SYMBOL = "R_100"  # Starting market
```

To monitor fewer markets:
```python
AVAILABLE_SYMBOLS = ["R_100", "R_75"]  # Only 2 markets
```

To disable (single market only):
```python
AVAILABLE_SYMBOLS = ["R_100"]  # Single market mode
```

### Adjust Scanning Frequency

In `agent.py`, line ~183:
```python
if self.tick_count % 25 == 0 and self.monitoring_multiple_markets:
    # Scan every 25 ticks (~25 seconds)
```

Change `25` to scan more/less frequently:
- `10` = Every 10 seconds (more aggressive switching)
- `50` = Every 50 seconds (less frequent switching)
- `100` = Every 100 seconds (conservative switching)

### Adjust Switching Threshold

In `agent.py`, line ~186:
```python
if best_opportunity.score > current_score + 10:
    # Switch if new market is 10+ points better
```

Change `10` to adjust sensitivity:
- `5` = Switch more easily (more aggressive)
- `15` = Switch only for much better opportunities (conservative)
- `20` = Very conservative (rarely switch)

## How It Works

### Initialization
1. Agent creates separate analyzers for each symbol in `AVAILABLE_SYMBOLS`
2. Multi-market monitor initializes with all symbols
3. Agent starts on `DEFAULT_SYMBOL`

### During Trading Loop
1. **Update Current Market** (every tick)
   - Feed price to current market's analyzer
   - Update pattern recognizer
   - Update multi-market monitor

2. **Scan All Markets** (every 25 ticks)
   - Build market data for all symbols
   - Calculate opportunity scores
   - Find best opportunity

3. **Switch if Better** (when score difference > 10)
   - Switch to new symbol
   - Update client connection
   - Reset pattern recognizer for new market
   - Log the switch

4. **Log Status** (every 100 ticks)
   - Show all markets with scores
   - Display performance by market
   - Highlight current market

### Trade Execution
- Trades are executed on the **current active market**
- Trade results are recorded for that specific market
- Performance stats are tracked per market

## Benefits

### 1. **Opportunity Maximization**
- Always trading the best available market
- Don't miss opportunities in other markets
- Automatically adapts to changing conditions

### 2. **Risk Diversification**
- Spread trades across multiple markets
- Reduce exposure to single market conditions
- Better overall performance

### 3. **Market Intelligence**
- Learn which markets perform best
- Identify market-specific patterns
- Optimize strategy per market

### 4. **Adaptive Trading**
- Switch away from deteriorating markets
- Follow momentum and trends across markets
- Respond to volatility changes

## Monitoring & Logs

### What to Watch For

**Good Signs:**
```
🔄 Switching markets: R_100 (score=65.0) → R_75 (score=82.5)
✅ Signal confirmed for 5 consecutive ticks (conf=0.75, ensemble=0.78, direction=up)
✓ WIN: Contract 12345 - Profit: $2.50
```

**Warning Signs:**
```
⚠️ All markets below threshold - staying on R_100
📊 No opportunities found across any market
```

### Log Files

- `logs/agent.log` - Main agent activity including market switches
- `logs/decisions.log` - Decision engine output with ensemble signals
- `logs/market_analysis.log` - Market state and health for all symbols
- `logs/trades.log` - Trade execution and results by market

## Performance Analysis

### View Performance by Market

The multi-market status log shows:
```
📈 PERFORMANCE BY MARKET:
  R_100: 5W/2L (71.4%) | Profit: $12.50
  R_75: 3W/3L (50.0%) | Profit: $0.00
  R_50: 2W/1L (66.7%) | Profit: $3.25
```

This helps you:
- Identify best-performing markets
- Avoid underperforming markets
- Optimize symbol selection

### Programmatic Access

```python
# Get all market performance
performance = agent.multi_market_monitor.get_all_performance()

# Get best performing market
best_symbol = agent.multi_market_monitor.get_best_performing_symbol()

# Get current opportunities
opportunities = agent.multi_market_monitor.get_opportunities_by_score(min_score=70.0)

# Get pattern heatmap
patterns = agent.multi_market_monitor.get_pattern_heatmap()
```

## Advanced Features

### Market Filtering

Get markets by condition:
```python
# Get trending markets
trending = agent.multi_market_monitor.get_trending_markets()

# Get ranging markets
ranging = agent.multi_market_monitor.get_ranging_markets()

# Get hottest market (highest volatility)
hottest = agent.multi_market_monitor.get_hottest_market()

# Get calmest market (lowest volatility)
calmest = agent.multi_market_monitor.get_calmest_market()
```

### Pattern-Based Opportunities

Find markets showing specific patterns:
```python
# Get all markets showing double_bottom pattern
opportunities = agent.multi_market_monitor.get_opportunities_by_pattern('double_bottom')
```

### Export Market Report

```python
report = agent.multi_market_monitor.export_market_report()
# Returns comprehensive report with all market data
```

## Troubleshooting

### Issue: Not Switching Markets

**Possible Causes:**
1. Score difference < 10 points
2. All markets have similar scores
3. No opportunities in other markets

**Solution:**
- Lower switching threshold (change `+ 10` to `+ 5`)
- Check market status logs to see scores
- Verify markets have enough data (>20 ticks)

### Issue: Switching Too Frequently

**Possible Causes:**
1. Switching threshold too low
2. Scanning too frequently
3. Markets very volatile

**Solution:**
- Increase switching threshold (change `+ 10` to `+ 15`)
- Reduce scan frequency (change `% 25` to `% 50`)
- Add cooldown between switches

### Issue: Poor Performance on Some Markets

**Possible Causes:**
1. Market characteristics don't match strategy
2. Insufficient data for that market
3. Different volatility patterns

**Solution:**
- Remove underperforming markets from `AVAILABLE_SYMBOLS`
- Adjust strategy weights per market
- Increase warmup period for new markets

## Best Practices

1. **Start with 2-3 markets** - Don't monitor all 5 immediately
2. **Monitor performance** - Check which markets work best
3. **Adjust thresholds** - Fine-tune switching sensitivity
4. **Watch the logs** - Understand why switches happen
5. **Track patterns** - See which patterns appear in which markets
6. **Be patient** - Let the system learn each market's behavior

## Summary

The multi-market monitoring system gives your trading agent:
- 📊 **5x more opportunities** - Monitor 5 markets instead of 1
- 🎯 **Intelligent switching** - Always trade the best market
- 📈 **Better performance** - Diversify across markets
- 🔍 **Market intelligence** - Learn which markets work best
- 🤖 **Fully automated** - No manual intervention needed

The agent now operates like a professional trader scanning multiple markets simultaneously and executing on the best opportunities!
