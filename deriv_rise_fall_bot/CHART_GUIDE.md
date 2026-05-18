# 📊 Live Chart Dashboard Guide

## What You Get

A real-time web dashboard that shows:

1. **Live Price Chart** - Candlestick chart with 1-minute candles
2. **Order Blocks** - Bullish (green) and bearish (red) zones marked on chart
3. **Support/Resistance** - Key price levels shown as dashed lines
4. **Market Structure** - Current trend (HH+HL, LH+LL, mixed, ranging)
5. **Multi-Timeframe Analysis** - 1m, 5m, 15m trend alignment
6. **Live Signals** - Current trade signal with confidence %
7. **Trading Stats** - Win rate, P&L, total trades

## How to Use

### Step 1: Start the Bot
```bash
cd deriv_rise_fall_bot
python smc_bot.py
```

The bot will automatically start the dashboard server on port 8765.

### Step 2: Open the Dashboard
Open `chart_dashboard.html` in your web browser (Chrome, Firefox, Safari, etc.)

You can:
- Double-click the file
- Or drag it into your browser
- Or right-click → Open With → Browser

### Step 3: Watch the Analysis

The dashboard updates in real-time showing:

- **Green boxes** = Bullish order blocks (price likely to bounce up)
- **Red boxes** = Bearish order blocks (price likely to bounce down)
- **Green dashed lines** = Support zones (price floor)
- **Red dashed lines** = Resistance zones (price ceiling)

## What the Indicators Mean

### Market Structure
- **HH+HL** (Higher Highs + Higher Lows) = Strong uptrend
- **LH+LL** (Lower Highs + Lower Lows) = Strong downtrend
- **Mixed** = Choppy, no clear direction
- **Ranging** = Sideways movement (bot won't trade)

### MTF Trend Alignment
- **strong_up** = All timeframes bullish (best for RISE)
- **strong_down** = All timeframes bearish (best for FALL)
- **moderate_up/down** = Some timeframes aligned
- **mixed** = Conflicting signals (bot waits)

### Signal Confidence
- **90%+** = Very high probability setup
- **85-89%** = High probability
- **75-84%** = Good probability
- **<75%** = Bot won't trade

## Understanding the Bot's Logic

The bot looks for:

1. **Clear trend** (not ranging)
2. **Order block nearby** (institutional buying/selling zone)
3. **Support/resistance confirmation**
4. **Multiple timeframes aligned**
5. **High confidence** (75%+ normally, 85-90% after losses)

## Troubleshooting

**Dashboard shows "Disconnected"**
- Make sure the bot is running
- Check that port 8765 is not blocked
- Refresh the browser page

**No data showing**
- Wait 2-3 minutes for the bot to collect enough data
- The bot needs 50+ ticks before analysis starts

**Chart not updating**
- Check browser console for errors (F12)
- Make sure WebSocket connection is active
- Try refreshing the page

## Tips

- Keep the dashboard open while bot is running to see live analysis
- Watch how order blocks form and get tested
- Notice how the bot waits for ranging markets to end
- See confidence increase when all timeframes align
- Learn which setups have highest win rate

The dashboard helps you understand WHY the bot makes each trade decision!
